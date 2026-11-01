#!/usr/bin/env python3
"""Tests for NixOS layout detection."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.nixos_layout import detect, valid_package_name


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def test_channels_single_file(tmp):
    _write(tmp / "configuration.nix", '''
    { ... }: {
      networking.hostName = "desk";
      environment.systemPackages = with pkgs; [ vim ];
    }
    ''')
    layout = detect(tmp)
    assert layout.style == "channels"
    assert layout.host_name == "desk"
    assert layout.packages_files == [tmp / "configuration.nix"]
    assert layout.rebuild_command() == "sudo nixos-rebuild switch"
    preview = "\n".join(layout.install_preview("firefox"))
    assert "configuration.nix" in preview
    assert "nix profile add nixpkgs#firefox" in preview
    assert "sudo nixos-rebuild switch" in preview
    print("✓ channels single file")


def test_channels_modules(tmp):
    _write(tmp / "configuration.nix", '''
    { ... }: {
      imports = [ ./modules/packages.nix ];
      networking.hostName = "Asus";
    }
    ''')
    _write(tmp / "modules" / "packages.nix", '''
    { pkgs, ... }: {
      environment.systemPackages = with pkgs; [ git ];
    }
    ''')
    _write(tmp / "modules" / "network.nix", '''
    { ... }: { networking.networkmanager.enable = true; }
    ''')
    layout = detect(tmp)
    assert layout.style == "channels"
    assert layout.host_name == "Asus"
    assert layout.packages_files == [tmp / "modules" / "packages.nix"]
    preview = "\n".join(layout.install_preview("firefox"))
    assert str(tmp / "modules" / "packages.nix") in preview
    assert "configuration.nix" not in preview.split("environment.systemPackages")[-1]
    print("✓ channels module tree")


def test_flake_one_host(tmp):
    _write(tmp / "flake.nix", '''
    {
      outputs = { self, nixpkgs }: {
        nixosConfigurations.laptop = nixpkgs.lib.nixosSystem {
          modules = [ ./configuration.nix ];
        };
      };
    }
    ''')
    _write(tmp / "configuration.nix", '''
    { pkgs, ... }: {
      networking.hostName = "laptop";
      environment.systemPackages = with pkgs; [ vim ];
    }
    ''')
    layout = detect(tmp)
    assert layout.style == "flakes"
    assert layout.flake_attr == "laptop"
    assert layout.rebuild_command() == f"sudo nixos-rebuild switch --flake {tmp}#laptop"
    assert "dry-build" in layout.dry_build_command()
    assert "sudo" not in layout.dry_build_command()
    print("✓ flake with one host")


def test_flake_matches_hostname(tmp):
    _write(tmp / "flake.nix", '''
    {
      outputs = inputs: {
        nixosConfigurations = {
          work = inputs.nixpkgs.lib.nixosSystem { modules = []; };
          asus = inputs.nixpkgs.lib.nixosSystem { modules = []; };
        };
      };
    }
    ''')
    _write(tmp / "hosts" / "asus.nix", 'networking.hostName = "Asus";\n')
    _write(tmp / "hosts" / "work.nix", '''
    { pkgs, ... }: { environment.systemPackages = with pkgs; [ git ]; }
    ''')
    layout = detect(tmp)
    assert layout.flake_attr == "asus"
    assert "#asus" in layout.rebuild_command()
    assert layout.packages_files == [tmp / "hosts" / "work.nix"]
    print("✓ flake attr follows hostName")


def test_flake_lists_names_when_ambiguous(tmp):
    _write(tmp / "flake.nix", '''
    {
      nixosConfigurations = {
        alpha = { };
        beta = { };
      };
    }
    ''')
    layout = detect(tmp)
    assert layout.flake_attr is None
    assert "alpha" in layout.note and "beta" in layout.note
    assert "#<name>" in layout.rebuild_command()
    print("✓ ambiguous flake names are listed")


def test_main_package_list_comes_first(tmp):
    _write(tmp / "configuration.nix", "{ ... }: { imports = [ ./modules/packages.nix ./modules/desktop.nix ]; }")
    _write(tmp / "modules" / "packages.nix", """
    { pkgs, ... }: {
      environment.systemPackages = with pkgs; [
        git
        firefox
      ];
    }
    """)
    _write(tmp / "modules" / "desktop.nix", """
    { pkgs, ... }: {
      environment.systemPackages = [
        (pkgs.makeDesktopItem { name = "example"; })
      ];
    }
    """)
    layout = detect(tmp)
    assert layout.packages_files[0] == tmp / "modules" / "packages.nix"
    preview = "\n".join(layout.install_preview("vim"))
    assert "Also assigned in:" in preview
    assert preview.index("packages.nix") < preview.index("desktop.nix")
    print("✓ main package list is listed first")


def test_model_context_uses_this_machine(tmp):
    _write(tmp / "configuration.nix", "{ ... }: { imports = [ ./packages.nix ]; networking.hostName = \"desk\"; }")
    body = "\n".join(
        ["{ pkgs, ... }: {", "  environment.systemPackages = with pkgs; ["]
        + [f"    pkg{i}" for i in range(50)]
        + ["  ];", "}"]
    )
    _write(tmp / "packages.nix", body + "\n  hashedPassword = \"secret-value\";\n")
    layout = detect(tmp)
    context = layout.model_context("how do I install a package?", "nix search said hello")
    assert f"config: {tmp}" in context
    assert "style: channels" in context
    assert "sudo nixos-rebuild switch" in context
    assert "packages.nix" in context
    assert "environment.systemPackages" in context
    assert "excerpt truncated" in context
    assert "secret-value" not in context
    assert "nix search said hello" in context
    assert layout.excerpt_for("what is a generation") == ""
    print("✓ model context is this machine and stays short")


def test_explain_finds_the_file_this_machine_uses(tmp):
    _write(tmp / "configuration.nix", "{ ... }: { imports = [ ./roles/remote.nix ./roles/print.nix ]; }")
    _write(tmp / "roles" / "remote.nix", "{ ... }: {\n  services.openssh.enable = false;\n}\n")
    _write(tmp / "roles" / "print.nix", "{ ... }: {\n  services.printing.enable = true;\n}\n")
    layout = detect(tmp)
    ssh = layout.explain("how do I enable ssh")
    assert ssh.index("In plain words") < ssh.index("Exact answer")
    assert "Edit " in ssh and "nixos-rebuild switch" in ssh
    assert str(tmp / "roles" / "remote.nix") in ssh
    assert "services.openssh.enable = false" in ssh
    assert "search.nixos.org/options" in ssh
    assert "services.openssh.enable" in ssh
    assert "print.nix" not in ssh
    advanced = layout.explain("services.openssh.enable default")
    assert advanced.index("Exact answer") < advanced.index("In plain words")
    printing = layout.explain("where is the printer")
    assert "print.nix" in printing
    assert "remote.nix" not in printing
    print("✓ explain follows this machine's files")


def test_package_name():
    assert valid_package_name("firefox")
    assert valid_package_name("kdePackages.kate")
    assert not valid_package_name("firefox;rm")
    assert not valid_package_name("../etc")
    print("✓ package names")


def run_all_tests():
    import tempfile
    print("Running AINIX layout tests")
    print("=" * 50)
    cases = [
        test_channels_single_file,
        test_channels_modules,
        test_flake_one_host,
        test_flake_matches_hostname,
        test_flake_lists_names_when_ambiguous,
        test_main_package_list_comes_first,
        test_model_context_uses_this_machine,
        test_explain_finds_the_file_this_machine_uses,
    ]
    for case in cases:
        with tempfile.TemporaryDirectory() as directory:
            case(Path(directory))
        print()
    test_package_name()
    print()
    print("=" * 50)
    print("All layout tests passed")


if __name__ == "__main__":
    run_all_tests()
