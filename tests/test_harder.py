#!/usr/bin/env python3
"""Harder cases: another person's tree, mkForce, tabs, mkMerge, and a flake with two hosts."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import core.nixos_layout as layout_mod
from ainix_help.assemble import assemble
from ainix_help.context import Context
from ainix_help.search import local_files, nix_assignments


def write_config(root, files):
    for name, text in files.items():
        path = Path(root) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def answer(question, root, names):
    ctx = Context(question, config=root)
    hits, note = local_files(ctx)
    return assemble(ctx, hits, [note], names)


def suggested(text):
    return text.split("Suggested change", 1)[-1] if "Suggested change" in text else ""


def test_channel_tree_prefers_the_daemon():
    """A desktop that is not this machine: client file named ssh.nix, daemon behind mkForce."""
    with tempfile.TemporaryDirectory() as root:
        files = {}
        for index in range(40):
            files[f"modules/noise-{index}.nix"] = (
                f"# ssh note {index}\n"
                "services.endlessh.enable = true;\n"
                'boot.extraModprobeConfig = "ssh";\n'
            )
        files["modules/ssh.nix"] = """
{ ... }: {
  programs.ssh.askPassword = "seahorse";
  programs.ssh.startAgent = true;
}
"""
        files["modules/remote.nix"] = """
{ lib, ... }: {
  # services.openssh.enable = true;
  services.openssh = {
    enable = lib.mkForce false;
  };
  networking.firewall.enable = true;
  services.openssh.openFirewall = false;
}
"""
        files["modules/comments.nix"] = '# services.openssh.enable = true;\n'
        files["configuration.nix"] = "{ ... }: {\n  imports = [ ./modules/remote.nix ];\n}\n"
        write_config(root, files)
        text = answer("how do I enable ssh", root, ["services.openssh.enable"])
    change = suggested(text)
    assert "services.openssh.enable = lib.mkForce false;" in text, text
    assert "+ services.openssh.enable = true;" in change, text
    assert "askPassword" not in change, text
    assert "openFirewall" not in change, text
    assert "endlessh" not in text, text
    assert "--flake" not in change, text
    assert "sudo nixos-rebuild dry-build" in change, text
    assert "sudo nixos-rebuild switch" in change, text
    assert "sudo nixos-rebuild boot" in change, text
    assert "-I nixos-config=" in change, text
    assert "Nothing was edited" in text, text
    print("✓ another person's channel tree edits the daemon, not the client file")


def test_explicit_password_setting_can_be_turned_on():
    with tempfile.TemporaryDirectory() as root:
        write_config(root, {
            "hosts/server/ssh.nix": """
{ ... }: {
  services.openssh = {
    enable = false;
    settings = {
      PasswordAuthentication = false;
    };
  };
}
""",
        })
        text = answer(
            "how do I allow password authentication for openssh",
            root,
            ["services.openssh.settings.PasswordAuthentication"],
        )
    change = suggested(text)
    assert "services.openssh.settings.PasswordAuthentication = false;" in text, text
    assert "+ services.openssh.settings.PasswordAuthentication = true;" in change, text
    assert "+ services.openssh.enable = true;" in change, text
    assert "No line needs to change" not in text, text
    print("✓ an explicit password setting that is false is turned on")


def test_tabs_and_mkmerge_still_find_enable():
    sample = """
services.openssh = lib.mkMerge [
\t{
\t\tenable = lib.mkIf isServer false;
\t}
];
""".splitlines()
    found = nix_assignments(sample)
    names = [item[1] for item in found]
    assert names == ["services.openssh.enable"], names
    assert found[0][2] == "lib.mkIf isServer false", found
    with tempfile.TemporaryDirectory() as root:
        write_config(root, {"modules/ssh.nix": "\n".join(sample) + "\n"})
        text = answer("how do I enable ssh", root, ["services.openssh.enable"])
    assert "+ services.openssh.enable = true;" in suggested(text), text
    print("✓ tabs and mkMerge still show the enable line")


def test_pipewire_mkforce_still_blocks_pulseaudio():
    with tempfile.TemporaryDirectory() as root:
        write_config(root, {
            "modules/sound.nix": """
{
  services.pulseaudio.enable = lib.mkDefault false;
  services.pipewire = {
    enable = lib.mkDefault true;
    pulse.enable = lib.mkForce true;
  };
}
""",
        })
        text = answer("how do I enable pulseaudio", root, ["services.pulseaudio.enable"])
    assert "Leave services.pulseaudio.enable = false." in text, text
    assert "+ services.pulseaudio.enable = true;" not in text, text
    print("✓ PipeWire wrapped in mkForce still keeps PulseAudio off")


def test_disable_and_already_on():
    with tempfile.TemporaryDirectory() as root:
        write_config(root, {
            "modules/print.nix": "{ ... }: {\n  services.printing.enable = lib.mkDefault true;\n}\n",
            "modules/bluetooth.nix": "{ ... }: {\n  hardware.bluetooth.enable = lib.mkForce true;\n}\n",
        })
        printing = answer("how do I disable printing", root, ["services.printing.enable"])
        bluetooth = answer("how do I enable bluetooth", root, ["hardware.bluetooth.enable"])
    assert "+ services.printing.enable = false;" in suggested(printing), printing
    assert "already true" in bluetooth, bluetooth
    assert "+ " not in bluetooth, bluetooth
    print("✓ disable flips mkDefault, and mkForce true stays as it is")


def test_flake_server_build_uses_the_host():
    with tempfile.TemporaryDirectory() as root:
        write_config(root, {
            "flake.nix": """
{
  outputs = { self, nixpkgs }: {
    nixosConfigurations.ainix-test-server = nixpkgs.lib.nixosSystem {
      modules = [ ./hosts/ainix-test-server/default.nix ];
    };
  };
}
""",
            "hosts/ainix-test-server/default.nix": """
{ lib, ... }: {
  networking.hostName = "ainix-test-server";
  services.openssh.enable = lib.mkForce false;
}
""",
        })
        for index in range(25):
            write_config(root, {f"modules/extra-{index}.nix": f"# desktop module {index}\n"})
        text = answer("how do I enable ssh", root, ["services.openssh.enable"])
    change = suggested(text)
    assert "+ services.openssh.enable = true;" in change, text
    assert f"--flake {root}#ainix-test-server" in change, text
    assert "dry-build --flake" in change, text
    assert "Nothing was edited" in text, text
    print("✓ a one-host flake server uses --flake")


def test_two_flake_hosts_are_not_mixed():
    files = {
        "flake.nix": """
{
  outputs = { self, nixpkgs }: {
    nixosConfigurations = {
      ainix-test-server = nixpkgs.lib.nixosSystem { modules = []; };
      ainix-test-desktop = nixpkgs.lib.nixosSystem { modules = []; };
    };
  };
}
""",
        "hosts/ainix-test-server/default.nix": """
{ ... }: {
  networking.hostName = "ainix-test-server";
  services.openssh.enable = false;
}
""",
        "hosts/ainix-test-desktop/default.nix": """
{ ... }: {
  networking.hostName = "ainix-test-desktop";
  services.openssh.enable = true;
}
""",
    }
    with tempfile.TemporaryDirectory() as root:
        write_config(root, files)
        original = layout_mod._running_hostname
        layout_mod._running_hostname = lambda: "ainix-test-server"
        try:
            scoped = answer("how do I enable ssh", root, ["services.openssh.enable"])
        finally:
            layout_mod._running_hostname = original
        mixed = answer("how do I enable ssh", root, ["services.openssh.enable"])
    change = suggested(scoped)
    assert "hosts/ainix-test-server/default.nix" in change, scoped
    assert "ainix-test-desktop" not in scoped, scoped
    assert "+ services.openssh.enable = true;" in change, scoped
    assert f"--flake {root}#ainix-test-server" in change, scoped
    assert "No line is suggested" in mixed, mixed
    assert "ainix-test-server" in mixed and "ainix-test-desktop" in mixed, mixed
    assert "+ services.openssh.enable = true;" not in mixed, mixed
    assert "#<name>" in mixed, mixed
    print("✓ two flake hosts stay apart")


def test_shared_module_still_applies_on_a_flake():
    with tempfile.TemporaryDirectory() as root:
        write_config(root, {
            "flake.nix": """
{
  nixosConfigurations = {
    ainix-test-server = { };
    ainix-test-desktop = { };
  };
}
""",
            "modules/ssh.nix": "{ ... }: {\n  services.openssh.enable = false;\n}\n",
        })
        original = layout_mod._running_hostname
        layout_mod._running_hostname = lambda: "ainix-test-server"
        try:
            text = answer("how do I enable ssh", root, ["services.openssh.enable"])
        finally:
            layout_mod._running_hostname = original
    change = suggested(text)
    assert "modules/ssh.nix" in change, text
    assert "+ services.openssh.enable = true;" in change, text
    assert f"--flake {root}#ainix-test-server" in change, text
    print("✓ a shared module still changes on the selected flake host")


if __name__ == "__main__":
    test_channel_tree_prefers_the_daemon()
    test_explicit_password_setting_can_be_turned_on()
    test_tabs_and_mkmerge_still_find_enable()
    test_pipewire_mkforce_still_blocks_pulseaudio()
    test_disable_and_already_on()
    test_flake_server_build_uses_the_host()
    test_two_flake_hosts_are_not_mixed()
    test_shared_module_still_applies_on_a_flake()
    print("harder tests passed")
