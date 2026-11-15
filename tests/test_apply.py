#!/usr/bin/env python3
"""Apply writes only the confirmed line. Boot is a separate rebuild action."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ainix_gui.changes import ApplyError, apply_edits, rewrite_line
from ainix_help.assemble import assemble
from ainix_help.context import Context
from ainix_help.plan import Edit, Plan, button_state, validate_rebuild
from ainix_help.search import Hit, local_files


def write_config(root, files):
    for name, text in files.items():
        path = Path(root) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def test_rewrite_keeps_indent_and_comment():
    raw = "    enable = lib.mkForce false; # later\n"
    new = rewrite_line(raw, "services.openssh.enable", "true", "lib.mkForce false")
    assert new == "    enable = true; # later\n", new
    refused = rewrite_line("    openFirewall = false;\n", "services.openssh.enable", "true", "false")
    assert refused is None, refused
    print("✓ a nested line keeps its indent and comment")


def test_apply_writes_only_the_matched_line():
    with tempfile.TemporaryDirectory() as root:
        write_config(root, {
            "configuration.nix": "{ ... }: {\n  imports = [ ./modules/remote.nix ];\n}\n",
            "modules/remote.nix": (
                "{ lib, ... }: {\n"
                "  services.openssh = {\n"
                "    enable = lib.mkForce false;\n"
                "    openFirewall = false;\n"
                "  };\n"
                "  networking.firewall.enable = true;\n"
                "}\n"
            ),
            "modules/other.nix": "{ ... }: {\n  services.printing.enable = true;\n}\n",
        })
        ctx = Context("how do I enable ssh", config=root)
        hits, note = local_files(ctx)
        text = assemble(ctx, hits, [note], ["services.openssh.enable"])
        edits = text.plan.edits
        assert len(edits) == 1, [(edit.path, edit.option, edit.new_value) for edit in edits]
        assert edits[0].new_value == "true"
        assert "nixos-rebuild boot" in text.plan.boot
        assert "nixos-rebuild switch" in text.plan.switch
        assert "nixos-rebuild dry-build" in text.plan.dry_build
        assert "-I nixos-config=" in text.plan.boot
        apply_edits(edits, root)
        remote = (Path(root) / "modules/remote.nix").read_text()
        other = (Path(root) / "modules/other.nix").read_text()
    assert "enable = true;" in remote, remote
    assert "lib.mkForce false" not in remote, remote
    assert "openFirewall = false;" in remote, remote
    assert "networking.firewall.enable = true;" in remote, remote
    assert other == "{ ... }: {\n  services.printing.enable = true;\n}\n", other
    print("✓ Apply changes the one OpenSSH line")


def test_a_mismatch_writes_nothing():
    with tempfile.TemporaryDirectory() as root:
        target = Path(root) / "remote.nix"
        original = "{ ... }: {\n  services.openssh.enable = true;\n}\n"
        target.write_text(original)
        edit = Edit(str(target), 2, "services.openssh.enable", "true", "false", "remote.nix:2")
        try:
            apply_edits([edit], root)
        except ApplyError:
            pass
        else:
            raise AssertionError("a changed line was accepted")
        assert target.read_text() == original
    print("✓ a line that no longer matches is left untouched")


def test_outside_file_is_refused():
    with tempfile.TemporaryDirectory() as root:
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / "remote.nix"
            target.write_text("{ ... }: {\n  services.openssh.enable = false;\n}\n")
            edit = Edit(str(target), 2, "services.openssh.enable", "true", "false", "remote.nix:2")
            try:
                apply_edits([edit], root)
            except ApplyError as exc:
                assert "outside" in str(exc)
            else:
                raise AssertionError("a file outside the configuration was written")
            assert "false" in target.read_text()
    print("✓ a file outside the configuration is refused")


def test_insert_goes_before_the_closing_brace():
    with tempfile.TemporaryDirectory() as root:
        target = Path(root) / "extra.nix"
        target.write_text("{ ... }: {\n  networking.hostName = \"desk\";\n}\n")
        edit = Edit(str(target), 0, "services.openssh.enable", "true", "", str(target))
        apply_edits([edit], root)
        text = target.read_text()
    assert "networking.hostName" in text
    assert text.index("services.openssh.enable = true;") < text.rindex("}")
    print("✓ a missing option is inserted before the closing brace")


def test_already_on_and_disagreement_have_no_edit():
    with tempfile.TemporaryDirectory() as root:
        write_config(root, {
            "modules/bluetooth.nix": "{ ... }: {\n  hardware.bluetooth.enable = true;\n}\n",
            "flake.nix": (
                "{\n  nixosConfigurations = {\n"
                "    ainix-apply-a = { };\n    ainix-apply-b = { };\n  };\n}\n"
            ),
            "hosts/ainix-apply-a/default.nix": (
                "{ ... }: {\n"
                "  networking.hostName = \"ainix-apply-a\";\n"
                "  services.openssh.enable = false;\n"
                "}\n"
            ),
            "hosts/ainix-apply-b/default.nix": (
                "{ ... }: {\n"
                "  networking.hostName = \"ainix-apply-b\";\n"
                "  services.openssh.enable = true;\n"
                "}\n"
            ),
        })
        blue = Context("how do I enable bluetooth", config=root)
        blue_hits, blue_note = local_files(blue)
        blue_text = assemble(blue, blue_hits, [blue_note], ["hardware.bluetooth.enable"])
        assert blue_text.plan.edits == []
        mixed = Context("how do I enable ssh", config=root)
        mixed_hits, mixed_note = local_files(mixed)
        mixed_text = assemble(mixed, mixed_hits, [mixed_note], ["services.openssh.enable"])
    assert mixed_text.plan.edits == [], mixed_text.plan.edits
    assert mixed_text.plan.needs_host
    assert "nixos-rebuild boot" in mixed_text.plan.boot
    assert "#<name>" in mixed_text.plan.boot
    print("✓ an unchanged option and a host disagreement are not edits")


def test_missing_option_waits_for_a_file():
    ctx = Context("how do I enable ssh", config="")
    hit = Hit("wiki", "SSH", "https://example.com/ssh", "services.openssh.enable = true;")
    text = assemble(ctx, [hit], ["wiki: 1 pages"], ["services.openssh.enable"])
    assert text.plan.edits, text
    assert text.plan.edits[0].path == ""
    assert text.plan.edits[0].option == "services.openssh.enable"
    assert "nixos-rebuild boot" in text
    print("✓ a missing option waits for a file")


def test_firefox_is_added_to_the_package_list():
    with tempfile.TemporaryDirectory() as root:
        write_config(root, {
            "configuration.nix": "{ ... }: {\n  imports = [ ./modules/system-packages.nix ./modules/system-filter.nix ];\n}\n",
            "modules/system-packages.nix": (
                "{ ... }: {\n"
                "  environment.systemPackages = with pkgs; [\n"
                "\tgit\n"
                "\tgnome-software\n"
                "\t];\n"
                "}\n"
            ),
            "modules/system-filter.nix": "{ ... }: {\n  environment.systemPackages = [ pkgs.opensnitch-ui ];\n}\n",
            "modules/apparmor-gui.nix": (
                "{ ... }: {\n"
                "  environment.systemPackages = [\n"
                "    app\n"
                "    pkgs.apparmor-utils\n"
                "  ];\n"
                "}\n"
            ),
        })
        from ainix_gui.answer import answer_question

        text = answer_question("How do I install firefox?", root)
        edits = text.plan.edits
        assert len(edits) == 1, text
        assert edits[0].kind == "package"
        assert edits[0].new_value == "firefox"
        assert edits[0].path.endswith("system-packages.nix"), edits[0].path
        assert "Left unchanged" in text
        apply_edits(edits, root)
        packages = (Path(root) / "modules/system-packages.nix").read_text()
        other = (Path(root) / "modules/system-filter.nix").read_text()
        local = (Path(root) / "modules/apparmor-gui.nix").read_text()
        assert "\tfirefox\n" in packages, packages
        assert "\tgit\n" in packages
        assert packages.count("firefox") == 1
        assert other == "{ ... }: {\n  environment.systemPackages = [ pkgs.opensnitch-ui ];\n}\n"
        assert "firefox" not in local
        try:
            apply_edits(edits, root)
        except ApplyError as exc:
            assert "already" in str(exc)
        else:
            raise AssertionError("firefox was added twice")
        assert packages == (Path(root) / "modules/system-packages.nix").read_text()
        command = answer_question("install firefox", root)
    assert "nix profile add nixpkgs#firefox" in command
    assert getattr(command, "plan", None) is None
    print("✓ firefox is added only to the package list")


def test_a_dotted_name_and_a_local_list():
    from ainix_help.install_edit import install_answer

    with tempfile.TemporaryDirectory() as root:
        write_config(root, {
            "configuration.nix": "{ ... }: {\n  networking.hostName = \"desk\";\n}\n",
            "packages.nix": (
                "{ ... }: {\n"
                "  environment.systemPackages = with pkgs; [\n"
                "    git\n"
                "  ];\n"
                "}\n"
            ),
        })
        dotted = install_answer("python313Packages.requests", root)
        assert dotted.plan.edits[0].new_value == "python313Packages.requests", dotted
        apply_edits(dotted.plan.edits, root)
        assert "python313Packages.requests" in (Path(root) / "packages.nix").read_text()

    with tempfile.TemporaryDirectory() as root:
        write_config(root, {
            "configuration.nix": "{ ... }: {\n  networking.hostName = \"desk\";\n}\n",
            "modules/helpers.nix": (
                "{ ... }: {\n"
                "  environment.systemPackages = [\n"
                "    app\n"
                "    backend\n"
                "  ];\n"
                "}\n"
            ),
        })
        text = install_answer("firefox", root)
        assert text.plan.edits[0].line == 0
        assert text.plan.edits[0].new_value == "with pkgs; [ firefox ]"
        apply_edits(text.plan.edits, root)
        config = (Path(root) / "configuration.nix").read_text()
        helper = (Path(root) / "modules/helpers.nix").read_text()
    assert "environment.systemPackages = with pkgs; [ firefox ];" in config, config
    assert "networking.hostName" in config
    assert "firefox" not in helper
    print("✓ a local name list is left alone and a dotted package name is kept")


def test_a_moved_package_list_is_refused():
    with tempfile.TemporaryDirectory() as root:
        target = Path(root) / "packages.nix"
        original = "{ ... }: {\n  environment.systemPackages = with pkgs; [\n    git\n  ];\n}\n"
        target.write_text(original)
        from ainix_help.install_edit import install_answer

        text = install_answer("firefox", root)
        target.write_text("{ ... }: {\n  # moved\n" + original)
        try:
            apply_edits(text.plan.edits, root)
        except ApplyError:
            pass
        else:
            raise AssertionError("a moved list was edited")
        assert "firefox" not in target.read_text()
    print("✓ a package list that moved is left untouched")


def test_an_edit_still_allows_install():
    plan = Plan()
    assert button_state(None) == (False, False)
    assert button_state(plan) == (False, False)
    plan.dry_build = "sudo nixos-rebuild dry-build"
    assert button_state(plan) == (False, True)
    plan.edits.append(Edit("/etc/nixos/modules/system-packages.nix", 11, "environment.systemPackages", "firefox", "", "/etc/nixos/modules/system-packages.nix:11", "package"))
    assert button_state(plan) == (True, True), button_state(plan)
    print("✓ an edit leaves install available")


def test_rebuild_commands_are_allowlisted():
    assert validate_rebuild("sudo nixos-rebuild boot") == ["nixos-rebuild", "boot"]
    flake = validate_rebuild("sudo nixos-rebuild boot --flake /etc/nixos#ainix-test-server")
    assert flake[-2:] == ["--flake", "/etc/nixos#ainix-test-server"]
    config = validate_rebuild("sudo nixos-rebuild dry-build -I nixos-config=/tmp/tree/configuration.nix")
    assert config[2:] == ["-I", "nixos-config=/tmp/tree/configuration.nix"]
    for command in (
        "sudo rm -rf /",
        "nixos-rebuild switch; reboot",
        "sudo nixos-rebuild build",
        "sudo nixos-rebuild boot --flake /etc/nixos#<name>",
        "sudo nixos-rebuild boot --flake /etc/nixos#bad name",
    ):
        try:
            validate_rebuild(command)
        except ValueError:
            continue
        raise AssertionError(command)
    print("✓ only dry-build, switch, and boot are accepted")


if __name__ == "__main__":
    test_rewrite_keeps_indent_and_comment()
    test_apply_writes_only_the_matched_line()
    test_a_mismatch_writes_nothing()
    test_outside_file_is_refused()
    test_insert_goes_before_the_closing_brace()
    test_already_on_and_disagreement_have_no_edit()
    test_missing_option_waits_for_a_file()
    test_firefox_is_added_to_the_package_list()
    test_a_dotted_name_and_a_local_list()
    test_a_moved_package_list_is_refused()
    test_an_edit_still_allows_install()
    test_rebuild_commands_are_allowlisted()
    print("apply tests passed")
