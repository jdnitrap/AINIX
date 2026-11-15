#!/usr/bin/env python3
"""Channel package lists are grouped without touching the system channel."""

import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ainix_catalog.catalog import (
    CatalogError,
    catalog_path,
    decode_index,
    load_cached,
    refresh,
    stable_channel_name,
    suggest_branch,
)
from ainix_catalog.cli import format_matches, format_summary, run
from ainix_catalog.groups import categorize


CHANNELS = """
{
  channels = {
    "nixos-25.11" = {
      job = "nixos/release-25.11/tested";
      variant = "primary";
      status = "unmaintained";
    };
    "nixos-26.05" = {
      job = "nixos/release-26.05/tested";
      variant = "primary";
      status = "stable";
    };
    "nixos-26.05-small" = {
      job = "nixos/release-26.05-small/tested";
      variant = "small";
      status = "stable";
    };
    "nixos-26.11" = {
      job = "nixos/release-26.11/tested";
      variant = "primary";
      status = "stable";
    };
    "nixos-unstable" = {
      job = "nixos/unstable/tested";
      variant = "primary";
      status = "rolling";
    };
  };
}
"""


def package(attr, description, position, pname="", version="1.0", main="", broken=False, unfree=False, homepage=""):
    meta = {
        "description": description,
        "position": position,
        "broken": broken,
        "unfree": unfree,
    }
    if main:
        meta["mainProgram"] = main
    if homepage:
        meta["homepage"] = homepage
    return {
        "pname": pname or attr,
        "version": version,
        "meta": meta,
    }


INDEX = {
    "version": 2,
    "packages": {
        "firefox": package(
            "firefox",
            "Web browser built from Firefox source tree",
            "pkgs/applications/networking/browsers/firefox/wrapper.nix:238",
            homepage=["https://www.mozilla.org/", ""],
        ),
        "vlc": package(
            "vlc",
            "Cross-platform media player and streaming server",
            "pkgs/by-name/vl/vlc/package.nix:321",
            main="vlc",
            homepage="https://www.videolan.org/vlc/",
        ),
        "lutris": package(
            "lutris",
            "Open gaming platform",
            "pkgs/by-name/lu/lutris/package.nix:10",
            main="lutris",
        ),
        "kitty": package(
            "kitty",
            "A modern terminal emulator",
            "pkgs/by-name/ki/kitty/package.nix:1",
            main="kitty",
        ),
        "qemu": package(
            "qemu",
            "Generic machine emulator and virtualizer",
            "pkgs/by-name/qe/qemu/package.nix:1",
            main="qemu-system-x86_64",
        ),
        "hello-game": package(
            "hello-game",
            "A strategy game",
            "pkgs/by-name/he/hello-game/package.nix:1",
            main="hello-game",
        ),
        "library-game": package(
            "library-game",
            "A strategy game library",
            "pkgs/by-name/li/library-game/package.nix:1",
        ),
        "requests": package(
            "requests",
            "HTTP for humans",
            "pkgs/development/python-modules/requests/default.nix:1",
        ),
        "emacsPackages.magit": package(
            "emacsPackages.magit",
            "Emacs git client",
            "pkgs/applications/editors/emacs/elisp-packages/manual-packages/magit/default.nix:1",
        ),
        "file-roller": package(
            "file-roller",
            "Archive manager for GNOME",
            "pkgs/applications/misc/file-roller/default.nix:1",
        ),
        "systemd": package(
            "systemd",
            "System and service manager",
            "pkgs/os-specific/linux/systemd/default.nix:1",
        ),
        "zeroad": package(
            "0ad",
            "A free, open-source game of ancient warfare",
            "pkgs/games/0ad/default.nix:1",
            pname="0ad",
        ),
        "nginx": package(
            "nginx",
            "A web server",
            "pkgs/by-name/ng/nginx/package.nix:1",
            main="nginx",
        ),
        "steam": package(
            "steam",
            "Digital distribution for games",
            "pkgs/by-name/st/steam/package.nix:1",
            main="steam",
            unfree=True,
            broken=True,
        ),
        "mystery": package(
            "mystery",
            "Does a thing",
            "pkgs/by-name/my/mystery/package.nix:1",
        ),
    },
}


def test_groups_follow_the_nixpkgs_path_and_the_description():
    assert categorize(
        "pkgs/applications/networking/browsers/firefox/wrapper.nix:238",
        "firefox",
        "firefox",
        "Web browser",
    ) == "Network"
    assert categorize("pkgs/applications/misc/file-roller/default.nix:1") == "Utilities"
    assert categorize("pkgs/applications/system/foo.nix:1") == "System"
    assert categorize("pkgs/games/0ad/default.nix:1") == "Games"
    assert categorize("pkgs/tools/networking/wireguard.nix:1") == "Network"
    assert categorize("pkgs/tools/security/pass.nix:1") == "Security"
    assert categorize("pkgs/servers/http/nginx/default.nix:1") == "Servers"
    assert categorize("pkgs/shells/fish/default.nix:1") == "Shells"
    assert categorize(
        "pkgs/applications/editors/emacs/elisp-packages/manual-packages/magit/default.nix:1",
        "emacsPackages.magit",
    ) == "Emacs"
    assert categorize(
        "pkgs/development/python-modules/requests/default.nix:1",
        "python313Packages.requests",
    ) == "Python"
    assert categorize(
        "pkgs/by-name/vl/vlc/package.nix:1",
        "vlc",
        "vlc",
        "Cross-platform media player",
        "vlc",
    ) == "Video"
    assert categorize(
        "pkgs/by-name/qe/qemu/package.nix:1",
        "qemu",
        "qemu",
        "Generic machine emulator and virtualizer",
        "qemu",
    ) == "System"
    assert categorize(
        "pkgs/by-name/he/hello-game/package.nix:1",
        "hello-game",
        "hello-game",
        "A strategy game",
        "hello-game",
    ) == "Games"
    assert categorize(
        "pkgs/by-name/li/library-game/package.nix:1",
        "library-game",
        "library-game",
        "A strategy game library",
        "",
    ) == "Libraries"
    assert categorize("pkgs/by-name/my/mystery/package.nix:1", "mystery", "mystery", "Does a thing") == "Libraries"
    assert categorize(
        "pkgs/by-name/ri/ripgrep/package.nix:1",
        "ripgrep",
        "ripgrep",
        "A fast search tool",
        "rg",
    ) == "Programs"
    assert categorize(
        "pkgs/top-level/perl-packages.nix:1",
        "perlPackages.ack",
    ) == "Perl"
    assert categorize(
        "pkgs/by-name/ty/typst/packages.nix:1",
        "typstPackages.notes",
    ) == "Typst"
    assert categorize(
        "pkgs/tools/typesetting/tex/default.nix:1",
        "texlivePackages.latex",
    ) == "TeX"
    assert categorize(
        "pkgs/by-name/re/requests/package.nix:1",
        "python313Packages.requests",
    ) == "Python"
    assert categorize(
        "pkgs/data/fonts/nerd-fonts/hack.nix:1",
        "nerd-fonts.hack",
    ) == "Fonts"
    assert categorize(
        "pkgs/by-name/fi/file-roller/package.nix:1",
        "file-roller",
        "file-roller",
        "Archive manager for the GNOME desktop environment",
        "file-roller",
    ) == "Utilities"
    assert categorize(
        "pkgs/by-name/sw/sway/package.nix:1",
        "sway",
        "sway",
        "An i3-compatible tiling window manager",
        "sway",
    ) == "Desktops"
    assert categorize(
        "pkgs/by-name/st/steam/package.nix:1",
        "steam",
        "steam",
        "Digital distribution platform",
        "steam",
    ) == "Games"
    assert categorize(
        "pkgs/by-name/kr/krita/package.nix:1",
        "krita",
        "krita",
        "Free and open source painting application",
        "krita",
    ) == "Graphics"
    assert categorize(
        "pkgs/by-name/di/discord/package.nix:1",
        "discord",
        "discord",
        "All-in-one cross-platform voice and text chat for gamers",
        "discord",
    ) == "Network"
    print("✓ paths and descriptions land in the application groups")


def test_stable_is_the_newest_primary_release():
    assert stable_channel_name(CHANNELS) == "nixos-26.11"
    try:
        stable_channel_name("{ }")
    except CatalogError as exc:
        assert "No stable" in str(exc)
    else:
        raise AssertionError("missing stable channel was accepted")
    assert suggest_branch("26.05.13936.ac588ef1c914") == "stable"
    assert suggest_branch("26.11pre1117658.d4f25a3e5620") == "unstable"
    print("✓ stable is the newest primary channel, and a pre version is unstable")


def test_refresh_uses_the_chosen_branch_and_caches_it():
    seen = []

    def opener(url):
        seen.append(url)
        if url.endswith("channels.nix"):
            return CHANNELS.encode()
        if url.endswith("/nixos-26.11/git-revision"):
            return b"abc123def456\n"
        if url.endswith("/nixos-unstable/git-revision"):
            return b"fff999\n"
        if url.endswith("packages.json.br"):
            assert "nixos-26.05-small" not in url
            return json.dumps(INDEX).encode()
        raise AssertionError(url)

    with tempfile.TemporaryDirectory() as root:
        catalog = refresh("stable", root, opener=opener)
        assert catalog.channel == "nixos-26.11", catalog.channel
        assert catalog.revision == "abc123def456"
        assert catalog.branch == "stable"
        groups = {item.attr: item.category for item in catalog.packages}
        assert groups["firefox"] == "Network"
        assert groups["vlc"] == "Video"
        assert groups["lutris"] == "Games"
        assert groups["kitty"] == "System"
        assert groups["qemu"] == "System"
        assert groups["requests"] == "Python"
        assert groups["emacsPackages.magit"] == "Emacs"
        assert groups["file-roller"] == "Utilities"
        assert groups["systemd"] == "System"
        assert groups["zeroad"] == "Games"
        assert groups["nginx"] == "Servers"
        assert groups["steam"] == "Games"
        assert groups["mystery"] == "Libraries"
        steam = next(item for item in catalog.packages if item.attr == "steam")
        assert steam.unfree and steam.broken
        firefox = next(item for item in catalog.packages if item.attr == "firefox")
        assert firefox.homepage == "https://www.mozilla.org/"
        downloads = [url for url in seen if url.endswith("packages.json.br")]
        assert len(downloads) == 1
        assert "nixos-26.11" in downloads[0]
        again = refresh("stable", root, opener=opener)
        assert again.revision == "abc123def456"
        assert len([url for url in seen if url.endswith("packages.json.br")]) == 1
        before = len(seen)
        unstable = refresh("unstable", root, opener=opener)
        assert unstable.channel == "nixos-unstable"
        assert unstable.revision == "fff999"
        fresh = seen[before:]
        assert not any(url.endswith("channels.nix") for url in fresh), fresh
        assert any(url.endswith("/nixos-unstable/packages.json.br") for url in fresh)
        saved = load_cached(root, "stable")
        assert saved is not None and saved.counts["Games"] >= 3
        rows, total = saved.select("Games", "", 10)
        assert total >= 3 and all(item.category == "Games" for item in rows)
        text = format_summary(saved)
        assert "nixos-26.11" in text and "Nothing was installed." in text
        one = format_matches(saved, "", "firefox")
        assert "pkgs.firefox" in one and "Nothing was installed." in one
        try:
            catalog_path(root, "../etc")
        except CatalogError:
            pass
        else:
            raise AssertionError("a branch outside stable and unstable was accepted")
    print("✓ refresh reads the chosen channel, groups packages, and caches them")


def test_plain_and_brotli_indexes_decode():
    raw = json.dumps(INDEX).encode()
    decoded = decode_index(raw)
    assert "firefox" in decoded["packages"]
    import brotli
    compressed = brotli.compress(raw)
    assert b"firefox" in json.dumps(decode_index(compressed)).encode()
    print("✓ a plain or brotli package list decodes")


def test_command_does_not_install():
    with tempfile.TemporaryDirectory() as root:
        os.environ["AINIX_CATALOG_CACHE"] = root
        buf = io.StringIO()
        with redirect_stdout(buf):
            run(["--branch", "unstable"])
        text = buf.getvalue()
    assert "No package list for unstable" in text, text
    assert "nix profile" not in text
    assert "--refresh" in text
    print("✓ ainix packages asks before it downloads and does not install")


def test_query_routes_to_the_package_list():
    os.environ["AINIX_CATALOG_CACHE"] = tempfile.mkdtemp(prefix="ainix-packages-")
    from ainix import AINIX

    class Args:
        execute = False
        yes = False

    buf = io.StringIO()
    with redirect_stdout(buf):
        AINIX().handle_query("packages firefox", Args())
    text = buf.getvalue()
    assert "No package list" in text, text
    assert "nix profile add" not in text
    print("✓ the packages command is not an install")


if __name__ == "__main__":
    test_groups_follow_the_nixpkgs_path_and_the_description()
    test_stable_is_the_newest_primary_release()
    test_refresh_uses_the_chosen_branch_and_caches_it()
    test_plain_and_brotli_indexes_decode()
    test_command_does_not_install()
    test_query_routes_to_the_package_list()
    print("catalog tests passed")
