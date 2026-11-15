#!/usr/bin/env python3
"""The window's answers, without opening a display."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ainix_gui.answer import answer_question
from ainix_help.search import Hit


def test_question_uses_the_chosen_directory():
    with tempfile.TemporaryDirectory() as root:
        nix = Path(root) / "remote.nix"
        nix.write_text("{ ... }: {\n  services.openssh.enable = false;\n}\n")

        def fake_search(ctx):
            assert ctx.config == root, ctx.config
            assert ctx.question == "how do I enable ssh?"
            hit = Hit(
                "your files",
                "remote.nix:2",
                str(nix),
                "services.openssh.enable = false;",
            )
            return [hit], ["your files: 1 lines"], ["services.openssh.enable"]

        import ainix_help.search as search_mod
        original = search_mod.search
        search_mod.search = fake_search
        try:
            text = answer_question("how do I enable ssh?", root)
        finally:
            search_mod.search = original
    assert "services.openssh.enable = false" in text, text
    assert "+ services.openssh.enable = true;" in text, text
    assert "Nothing was edited" in text, text
    assert "Would execute" not in text, text
    print("✓ the window asks the chosen configuration")


def test_missing_directory_is_not_searched():
    text = answer_question("how do I enable ssh", "/tmp/ainix-no-such-config")
    assert "does not exist" in text, text
    print("✓ a missing configuration directory is reported")


def test_install_and_rebuild_stay_previews():
    with tempfile.TemporaryDirectory() as root:
        flake = Path(root) / "flake.nix"
        flake.write_text(
            "{\n"
            "  outputs = { self, nixpkgs }: {\n"
            "    nixosConfigurations.ainix-gui-host = nixpkgs.lib.nixosSystem {\n"
            "      modules = [ ./configuration.nix ];\n"
            "    };\n"
            "  };\n"
            "}\n"
        )
        (Path(root) / "configuration.nix").write_text(
            '{ ... }: { networking.hostName = "ainix-gui-host"; }\n'
        )
        install = answer_question("install firefox", root)
        rebuild = answer_question("rebuild", root)
    assert "nix profile add nixpkgs#firefox" in install, install
    assert "Preview never changes the system." in install, install
    assert f"--flake {root}#ainix-gui-host" in rebuild, rebuild
    assert "nixos-rebuild boot" in rebuild.plan.boot
    assert "Trying dry-build" not in rebuild, rebuild
    assert "Would execute" not in rebuild, rebuild
    print("✓ install and rebuild stay previews in the window")


def test_install_question_can_be_applied():
    from ainix_help.install_edit import install_question

    with tempfile.TemporaryDirectory() as root:
        (Path(root) / "configuration.nix").write_text("{ ... }: {\n}\n")
        (Path(root) / "packages.nix").write_text(
            "{ ... }: {\n  environment.systemPackages = with pkgs; [\n    git\n  ];\n}\n"
        )
        text = answer_question("How do I install firefox?", root)
    assert text.plan.edits and text.plan.edits[0].new_value == "firefox", text
    assert "Nothing was edited" in text
    assert install_question("How do I install a package?", root) is None
    print("✓ an install question proposes the package list")


def test_command_word_is_not_a_search():
    text = answer_question("enable ssh", "")
    assert "Would execute" in text, text
    assert "Phrase it as a question" in text, text
    print("✓ a command word stays a preview")


if __name__ == "__main__":
    test_question_uses_the_chosen_directory()
    test_missing_directory_is_not_searched()
    test_install_and_rebuild_stay_previews()
    test_install_question_can_be_applied()
    test_command_word_is_not_a_search()
    print("gui answer tests passed")
