#!/usr/bin/env python3
"""Hard cases: noise before the real option, PipeWire, a renamed option, a build log."""

import io
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import ainix
from ainix_help.assemble import assemble
from ainix_help.context import Context
from ainix_help.search import Hit, local_files, renamed_facts, usable_option_text
from core.router import QueryRouter, QueryType


class Args:
    execute = False
    yes = False


def write_config(root, files):
    for name, text in files.items():
        path = Path(root) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def ctx_for(question, root):
    ctx = Context(question, config=root)
    return ctx


def test_bluetooth_ignores_apparmor_noise():
    with tempfile.TemporaryDirectory() as root:
        write_config(root, {
            "modules/apparmor.nix": "\n".join(
                [f'  # bluetooth mention {index}' for index in range(8)]
                + ['  network bluetooth,']
            ),
            "modules/bluetooth.nix": "{\n  hardware.bluetooth.enable = true;\n  hardware.bluetooth.powerOnBoot = true;\n}\n",
        })
        ctx = ctx_for("how do I enable bluetooth", root)
        hits, note = local_files(ctx)
        text = assemble(ctx, hits, [note], ["hardware.bluetooth.enable"])
    assert "hardware.bluetooth.enable to true" in text, text
    assert "already true" in text, text
    assert "blueman" not in text, text
    assert "+ " not in text, text
    print("✓ bluetooth keeps the hardware switch")


def test_pulseaudio_does_not_fight_pipewire():
    with tempfile.TemporaryDirectory() as root:
        write_config(root, {
            "modules/sound.nix": """
{
  services.pulseaudio.enable = false;
  services.pipewire = {
    enable = true;
    pulse.enable = true;
  };
}
""",
        })
        ctx = ctx_for("how do I enable pulseaudio", root)
        hits, note = local_files(ctx)
        text = assemble(ctx, hits, [note], ["services.pulseaudio.enable"])
    assert "services.pipewire.pulse.enable" in text, text
    assert "Leave services.pulseaudio.enable = false." in text, text
    assert "+ services.pulseaudio.enable = true;" not in text, text
    print("✓ pulseaudio stays off when PipeWire provides it")


def test_password_auth_uses_the_renamed_option():
    sample = """
    (lib.mkRenamedOptionModule
      [ "services" "openssh" "passwordAuthentication" ]
      [ "services" "openssh" "settings" "PasswordAuthentication" ]
    )
    (lib.mkRenamedOptionModule
      [ "services" "openssh" "challengeResponseAuthentication" ]
      [ "services" "openssh" "kbdInteractiveAuthentication" ]
    )
    PasswordAuthentication = lib.mkOption {
      type = lib.types.nullOr lib.types.bool;
      default = true;
      description = "Specifies whether password authentication is allowed.";
    };
    """.splitlines()
    ctx = Context("how do I allow password authentication for openssh", config="")
    facts = renamed_facts(sample, ctx)
    assert len(facts) == 1, facts
    excerpt = facts[0][1]
    assert "was renamed to services.openssh.settings.PasswordAuthentication" in excerpt, excerpt
    assert "default = true" in excerpt, excerpt
    assert "challengeResponse" not in excerpt
    hits = [
        Hit("your files", "configuration.nix:39", "/etc/nixos/configuration.nix", 'programs.ssh.askPassword = lib.mkForce "${pkgs.seahorse}/libexec/seahorse/ssh-askpass";'),
        Hit("your files", "modules/user-accounts.nix:12", "/etc/nixos/modules/user-accounts.nix", 'users.users.Admin.initialPassword = "changeme";'),
        Hit("your files", "modules/networking.nix:20", "/etc/nixos/modules/networking.nix", "services.openssh.enable = false;"),
        Hit("nixpkgs", "sshd.nix:195", "https://example.com/sshd.nix", excerpt),
    ]
    assert "askPassword" not in assemble(ctx, hits, ["nixpkgs: 1 lines"], ["services.openssh.settings.PasswordAuthentication"]).split("Suggested change")[0]
    text = assemble(ctx, hits, ["nixpkgs: 1 lines"], ["services.openssh.settings.PasswordAuthentication"])
    assert "services.openssh.settings.PasswordAuthentication" in text, text
    assert "No line needs to change" not in text, text
    assert "+ services.openssh.enable = true;" in text, text
    assert "defaults to true" in text, text
    print("✓ password authentication follows the renamed option")


def test_unknown_attribute_is_not_a_fix():
    ctx = Context("error: attribute 'foobarpkg' missing. The nixos rebuild failed", config="")
    text = assemble(
        ctx,
        [Hit("wiki", "Navidrome", "https://example.com/n", "attribute names shown above")],
        ["wiki: 1 pages"],
        [],
    )
    assert "No solid match." in text, text
    assert "Navidrome" not in text, text
    assert "No source used the words in the question." in text, text
    trace = "error: … while evaluating a branch condition\nwhile calling the 'throw' builtin"
    assert usable_option_text(trace) == ""
    assert "Default: true" in usable_option_text("Value: true\nDefault: true\nType: boolean\nDescription: Whether.")
    print("✓ an unknown attribute is not turned into an edit")


def test_rebuild_error_is_searched():
    seen = {}

    def fake_search(ctx):
        seen["question"] = ctx.question
        return [], ["wiki: 0 pages"], []

    import ainix_help.search as search_mod
    original = search_mod.search
    search_mod.search = fake_search
    try:
        buf = io.StringIO()
        with redirect_stdout(buf):
            ainix.AINIX().handle_query(
                "error: attribute 'foobarpkg' missing. The nixos rebuild failed",
                Args(),
            )
        text = buf.getvalue()
    finally:
        search_mod.search = original
    assert seen["question"].startswith("error:"), seen
    assert "Would execute" not in text, text
    assert "No solid match." in text, text
    assert QueryRouter.classify("install firefox")[0] == QueryType.CONTROL
    print("✓ a rebuild error is searched")


if __name__ == "__main__":
    test_bluetooth_ignores_apparmor_noise()
    test_pulseaudio_does_not_fight_pipewire()
    test_password_auth_uses_the_renamed_option()
    test_unknown_attribute_is_not_a_fix()
    test_rebuild_error_is_searched()
    print("hard tests passed")
