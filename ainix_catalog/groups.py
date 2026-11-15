"""Group a nixpkgs package by its path, its attribute set, then its description."""

import re


CATEGORY_ORDER = (
    "Audio",
    "Video",
    "Graphics",
    "Games",
    "Network",
    "Office",
    "Science",
    "Development",
    "Desktops",
    "System",
    "Utilities",
    "Servers",
    "Shells",
    "Security",
    "Fonts",
    "Themes",
    "Dictionaries",
    "TeX",
    "Typst",
    "Tree-sitter",
    "Python",
    "Haskell",
    "R",
    "Emacs",
    "Vim",
    "Lisp",
    "OCaml",
    "Ruby",
    "Lua",
    "PHP",
    "Perl",
    "Node.js",
    "Go",
    "Erlang and Elixir",
    "Idris",
    "Rocq",
    "Ada",
    "VS Code",
    "Build tools",
    "Programs",
    "Libraries",
    "Other",
)

# Longer prefixes are tried first. The path is the part after pkgs/.
_PATH_RULES = (
    ("applications/editors/emacs/elisp-packages", "Emacs"),
    ("applications/editors/vim/plugins", "Vim"),
    ("applications/editors/vscode/extensions", "VS Code"),
    ("applications/editors/kakoune/plugins", "Development"),
    ("applications/editors/eclipse/plugins", "Development"),
    ("development/python-modules", "Python"),
    ("development/haskell-modules", "Haskell"),
    ("development/r-modules", "R"),
    ("development/lisp-modules", "Lisp"),
    ("development/ocaml-modules", "OCaml"),
    ("development/lua-modules", "Lua"),
    ("development/ruby-modules", "Ruby"),
    ("development/php-packages", "PHP"),
    ("development/perl-packages", "Perl"),
    ("development/beam-modules", "Erlang and Elixir"),
    ("development/cuda-modules", "Development"),
    ("development/idris-modules", "Idris"),
    ("development/rocq-modules", "Rocq"),
    ("development/ada-modules", "Ada"),
    ("development/node-packages", "Node.js"),
    ("development/go-modules", "Go"),
    ("top-level/perl-packages", "Perl"),
    ("top-level/php-packages", "PHP"),
    ("top-level/lua-packages", "Lua"),
    ("top-level/dotnet-packages", "Development"),
    ("build-support/rocq", "Rocq"),
    ("by-name/ty/typst", "Typst"),
    ("by-name/tr/tree-sitter", "Tree-sitter"),
    ("by-name/mp/mpv", "Video"),
    ("by-name/li/libretro", "Games"),
    ("applications/networking", "Network"),
    ("applications/audio", "Audio"),
    ("applications/video", "Video"),
    ("applications/graphics", "Graphics"),
    ("applications/office", "Office"),
    ("applications/science", "Science"),
    ("applications/misc", "Utilities"),
    ("applications/system", "System"),
    ("applications/terminal-emulators", "Utilities"),
    ("applications/window-managers", "Desktops"),
    ("applications/display-managers", "Desktops"),
    ("applications/version-management", "Development"),
    ("applications/editors", "Development"),
    ("applications/blockchains", "Network"),
    ("applications/kde", "Desktops"),
    ("applications/gnome", "Desktops"),
    ("applications/emulators", "Games"),
    ("applications/virtualization", "System"),
    ("applications/radio", "Audio"),
    ("tools/networking", "Network"),
    ("tools/security", "Security"),
    ("tools/system", "System"),
    ("tools/admin", "System"),
    ("tools/backup", "System"),
    ("tools/package-management", "System"),
    ("tools/text", "Utilities"),
    ("tools/misc", "Utilities"),
    ("tools/archivers", "Utilities"),
    ("tools/compression", "Utilities"),
    ("tools/typesetting", "TeX"),
    ("tools/games", "Games"),
    ("tools/inputmethods", "System"),
    ("data/fonts", "Fonts"),
    ("data/themes", "Themes"),
    ("desktops/", "Desktops"),
    ("games/", "Games"),
    ("servers/", "Servers"),
    ("shells/", "Shells"),
    ("development/", "Development"),
    ("os-specific/", "System"),
    ("kde/", "Desktops"),
    ("build-support/", "Build tools"),
    ("stdenv/", "Build tools"),
    ("misc/cups", "System"),
    ("misc/tmux-plugins", "Utilities"),
)

_PATH_RULES = tuple(sorted(_PATH_RULES, key=lambda item: len(item[0]), reverse=True))

# Dotted attribute sets whose directory does not say which group they belong to.
_ATTR_EXACT = {
    "rPackages": "R",
    "haskellPackages": "Haskell",
    "emacsPackages": "Emacs",
    "sbclPackages": "Lisp",
    "vimPlugins": "Vim",
    "texlivePackages": "TeX",
    "typstPackages": "Typst",
    "tree-sitter-grammars": "Tree-sitter",
    "hunspellDicts": "Dictionaries",
    "skkDictionaries": "Dictionaries",
    "nerd-fonts": "Fonts",
    "maple-mono": "Fonts",
    "linuxKernel": "System",
    "libretro": "Games",
    "mpvScripts": "Video",
    "vscode-extensions": "VS Code",
    "cudaPackages": "Development",
    "rocqPackages": "Rocq",
    "idrisPackages": "Idris",
    "nodePackages": "Node.js",
    "beamPackages": "Erlang and Elixir",
    "perlPackages": "Perl",
    "perl5Packages": "Perl",
    "tmuxPlugins": "Utilities",
    "yaziPlugins": "Utilities",
    "openbaoPlugins": "Security",
    "netboxPlugins": "Servers",
    "papermcServers": "Games",
    "minecraftServers": "Games",
    "optifinePackages": "Games",
    "dwarf-fortress-packages": "Games",
    "nixos-artwork": "Themes",
    "unixtools": "System",
    "ibus-engines": "System",
    "azure-cli-extensions": "Development",
    "lixPackageSets": "Development",
    "dotnetPackages": "Development",
    "llvmPackages": "Development",
}

# First match wins. These stay specific so a library is not filed as an application.
# "for the GNOME desktop environment" is an application that runs there, not the desktop itself.
_WINDOW_MANAGER = re.compile(r"\bwindow manager\b", re.I)
_DESKTOP_ENV = re.compile(r"\bdesktop environment\b", re.I)
_FOR_A_DESKTOP = re.compile(r"\bfor the\b.{0,48}\bdesktop environment\b", re.I)

_KEYWORDS = (
    ("Servers", re.compile(r"\b(web server|http server|mail server)\b", re.I)),
    (
        "System",
        re.compile(
            r"\b(file manager|system monitor|partition manager|boot ?loader|terminal emulator|virtual machine|virtualizer|hypervisor)\b",
            re.I,
        ),
    ),
    (
        "Games",
        re.compile(
            r"\b(video games?|game engine|game launcher|gaming platform|gaming|digital distribution platform)\b",
            re.I,
        ),
    ),
    (
        "Network",
        re.compile(
            r"\b(web browser|browser|mail client|email client|e-mail client|irc client|torrent client|bittorrent|vpn client|vpn|network manager|network configuration|ssh protocol|protocol analyzer|messenger|text chat)\b",
            re.I,
        ),
    ),
    (
        "Video",
        re.compile(r"\b(media player|video player|video editor|screen recorder|video converter)\b", re.I),
    ),
    (
        "Audio",
        re.compile(r"\b(audio player|music player|audio editor|sound editor|synthesizer|digital audio)\b", re.I),
    ),
    (
        "Graphics",
        re.compile(
            r"\b(image editor|image manipulation|photo editor|painting application|vector graphics|vector editor|3d editor|3d creation)\b",
            re.I,
        ),
    ),
    (
        "Office",
        re.compile(r"\b(office suite|word processor|spreadsheet|pdf reader|note-taking|note taking)\b", re.I),
    ),
    ("Science", re.compile(r"\b(scientific calculator|computer algebra|astronomy)\b", re.I)),
    (
        "Development",
        re.compile(r"\b(text editor|integrated development|version control|source control)\b", re.I),
    ),
    ("Security", re.compile(r"\b(password manager|encryption tool)\b", re.I)),
    (
        "Utilities",
        re.compile(r"\b(archive manager|clipboard manager|screenshot tool|\bcalculator\b)\b", re.I),
    ),
)

_GAME_WORD = re.compile(r"\bgames?\b", re.I)
_FONT = re.compile(r"\b(fonts?|typeface)\b", re.I)
_THEME = re.compile(r"\b(icon theme|cursor theme|sound theme)\b", re.I)
_DICTIONARY = re.compile(r"\b(dictionary|spell ?checker)\b", re.I)
_SYSTEM_LEFT = re.compile(r"\b(firmware|kernel module|printer driver)\b", re.I)
_DEV_LEFT = re.compile(r"\b(compiler|interpreter|debugger|linter)\b", re.I)
_LIBRARY = re.compile(r"\b(library|bindings?)\b", re.I)


def pkgs_rel(position):
    """Return the path after pkgs/, without a trailing :line."""
    if not position:
        return ""
    text = str(position).split(":", 1)[0].replace("\\", "/")
    marker = "pkgs/"
    index = text.find(marker)
    if index < 0:
        return ""
    return text[index + len(marker):]


def path_category(position):
    rel = pkgs_rel(position)
    if not rel:
        return ""
    for prefix, category in _PATH_RULES:
        if rel.startswith(prefix):
            return category
    return ""


def attr_category(attr):
    """Group a dotted name such as python313Packages.requests or texlivePackages.foo."""
    if not attr or "." not in attr:
        return ""
    head = attr.split(".", 1)[0]
    found = _ATTR_EXACT.get(head)
    if found:
        return found
    if head.startswith("python") and head.endswith("Packages"):
        return "Python"
    if head.startswith("rubyPackages"):
        return "Ruby"
    if head.startswith("lua") and head.endswith("Packages"):
        return "Lua"
    if head.startswith("php") and (head.endswith("Extensions") or head.endswith("Packages")):
        return "PHP"
    if head.startswith("ocamlPackages"):
        return "OCaml"
    if head.startswith("llvmPackages"):
        return "Development"
    if head.startswith("haskell"):
        return "Haskell"
    return ""


def keyword_category(text, main_program=False):
    haystack = text or ""
    if _WINDOW_MANAGER.search(haystack):
        return "Desktops"
    if _DESKTOP_ENV.search(haystack) and not _FOR_A_DESKTOP.search(haystack):
        return "Desktops"
    for category, pattern in _KEYWORDS:
        if pattern.search(haystack):
            return category
    if main_program and _GAME_WORD.search(haystack):
        return "Games"
    return ""


def fallback_category(text, main_program=False):
    """Last pass for packages that are not an application and not a known set."""
    haystack = text or ""
    if _FONT.search(haystack):
        return "Fonts"
    if _THEME.search(haystack):
        return "Themes"
    if _DICTIONARY.search(haystack):
        return "Dictionaries"
    if _SYSTEM_LEFT.search(haystack):
        return "System"
    if _DEV_LEFT.search(haystack):
        return "Development"
    if not main_program and _LIBRARY.search(haystack):
        return "Libraries"
    if main_program:
        return "Programs"
    return "Libraries"


def categorize(position, attr="", pname="", description="", main_program=""):
    found = path_category(position)
    if found:
        return found
    found = attr_category(attr)
    if found:
        return found
    text = " ".join(part for part in (attr, pname, description) if part)
    return keyword_category(text, bool(main_program)) or fallback_category(text, bool(main_program))
