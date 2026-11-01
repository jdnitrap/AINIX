"""Detect how this NixOS machine is configured.

Works for a single configuration.nix, a split module tree, or a flake.
The config root is /etc/nixos, or AINIX_NIXOS_CONFIG when that is set.
A flake.nix in the current directory is ignored, so a random project
flake is not treated as the system.
"""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import quote


_STOP = {
    "how", "do", "does", "did", "the", "and", "for", "with", "what", "why",
    "where", "when", "who", "can", "enable", "disable", "set", "use", "using",
    "this", "that", "your", "you", "nixos", "nix", "about", "from", "into",
    "please", "help", "show", "tell", "want", "need", "make", "turn",
    "services", "programs", "networking", "environment", "hardware",
    "boot", "security", "system", "default",
}
_SYNONYMS = {
    "ssh": ["openssh"],
    "firewall": ["firewall", "opensnitch"],
    "printer": ["printing", "cups"],
    "printing": ["printing", "cups"],
    "scanner": ["sane", "ipp-usb"],
    "scan": ["sane"],
    "bluetooth": ["bluetooth", "blueman"],
    "sound": ["pipewire", "pulseaudio"],
    "audio": ["pipewire", "pulseaudio"],
    "flatpak": ["flatpak"],
    "update": ["autoupgrade"],
    "upgrade": ["autoupgrade"],
    "package": ["systempackages"],
    "packages": ["systempackages"],
    "install": ["systempackages"],
    "apparmor": ["apparmor"],
    "dns": ["adguard", "nameserver"],
    "adblock": ["adguard"],
    "vpn": ["openvpn", "wireguard"],
    "desktop": ["plasma", "sddm"],
    "plasma": ["plasma"],
    "boot": ["boot.loader", "systemd-boot"],
    "locale": ["i18n."],
    "keyboard": ["xkb"],
    "wifi": ["networkmanager"],
    "network": ["networkmanager"],
}
_OPTION_NAME = re.compile(r"\b([A-Za-z_][\w-]*(?:\.[A-Za-z_][\w-]*)+)\b")

_PACKAGE_NAME = re.compile(r"^[A-Za-z_][\w.+-]*$")
_HOST_NAME = re.compile(r'networking\.hostName\s*=\s*"([^"]+)"')
_PACKAGES_ASSIGN = re.compile(r"environment\.systemPackages\s*=")
_SKIP_DIRS = {".git", "result", ".direnv"}


@dataclass
class NixOSLayout:
    root: Optional[Path]
    style: str
    host_name: Optional[str] = None
    flake_attr: Optional[str] = None
    flake_names: list = field(default_factory=list)
    packages_files: list = field(default_factory=list)
    note: str = ""

    def packages_label(self) -> str:
        if not self.packages_files:
            if self.root and (self.root / "configuration.nix").exists():
                return str(self.root / "configuration.nix")
            return "configuration.nix"
        if len(self.packages_files) == 1:
            return str(self.packages_files[0])
        main = str(self.packages_files[0])
        others = "\n  ".join(str(path) for path in self.packages_files[1:])
        return f"{main}\n  Also assigned in:\n  {others}"

    def rebuild_command(self) -> str:
        if self.style == "flakes" and self.root is not None:
            if self.flake_attr:
                return f"sudo nixos-rebuild switch --flake {self.root}#{self.flake_attr}"
            if self.flake_names:
                return f"sudo nixos-rebuild switch --flake {self.root}#<name>"
            return f"sudo nixos-rebuild switch --flake {self.root}"
        return "sudo nixos-rebuild switch"

    def dry_build_command(self) -> str:
        return self.rebuild_command().replace("sudo ", "", 1).replace("switch", "dry-build", 1)

    def style_label(self) -> str:
        if self.style == "unknown":
            return "unknown (no /etc/nixos config found)"
        return self.style

    def model_context(self, query: str, prior: str = "") -> str:
        """Facts the local model may use. It does not replace the docs."""
        lines = ["This machine:"]
        lines.append(f"style: {self.style}")
        if self.root:
            lines.append(f"config: {self.root}")
        if self.host_name:
            lines.append(f"host: {self.host_name}")
        if self.packages_files:
            lines.append(f"packages file: {self.packages_files[0]}")
            if len(self.packages_files) > 1:
                lines.append("packages also assigned in: " + ", ".join(str(p) for p in self.packages_files[1:]))
        lines.append(f"rebuild: {self.rebuild_command()}")
        if self.note:
            lines.append(self.note)
        lines.append("Use these paths. Do not invent a different config file or NixOS option.")
        parts = ["\n".join(lines)]
        excerpt = self.excerpt_for(query)
        if excerpt:
            parts.append(excerpt)
        located = self.explain(query)
        if located:
            parts.append(located)
        prior = (prior or "").strip()
        if prior:
            parts.append("Material already found:\n" + prior[:1500])
        return "\n\n".join(parts)

    def explain(self, query: str) -> str:
        """Where a question shows up in this machine's config, plus one official link.

        NixOS documents the same option in the manual, the wiki, and search.
        The paths here are whatever files this machine actually uses.
        """
        if self.root is None or self.style == "unknown":
            return ""
        needles = _needles(query)
        if not needles:
            return ""
        hits = []
        for path in _nix_files(self.root):
            try:
                lines = path.read_text(errors="ignore").splitlines()
            except OSError:
                continue
            for number, line in enumerate(lines, start=1):
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if not _line_matches(stripped, needles):
                    continue
                option = _option_name(stripped)
                hits.append((path, number, stripped, option))
                if len(hits) >= 8:
                    break
            if len(hits) >= 8:
                break
        if not hits:
            return ""
        options = []
        for _path, _number, _stripped, option in hits:
            if option and option not in options:
                options.append(option)
        first_path, first_number, first_line, _first_option = hits[0]
        plain = _plain_words(needles, first_path)
        nxt = f"Next:\n  Edit {first_path}\n  {self.rebuild_command()}"
        exact = ["Exact answer"]
        for path, number, stripped, _option in hits:
            exact.append(f"\n{path}:{number}\n  {stripped}")
        if options:
            exact.append("\nOfficial option page:")
            for option in options[:3]:
                url = "https://search.nixos.org/options?channel=unstable&query=" + quote(option)
                exact.append(f"  {option}\n  {url}")
        exact_text = "\n".join(exact)
        guide = f"In plain words\n{plain}\n\n{nxt}"
        if _is_advanced(query):
            return exact_text + "\n\n" + guide
        return guide + "\n\n" + exact_text

    def excerpt_for(self, query: str) -> str:
        q = query.lower()
        if not self.packages_files:
            return ""
        if not any(word in q for word in ("install", "package", "systempackages")):
            return ""
        return _excerpt_packages(self.packages_files[0])

    def install_preview(self, package: str) -> list:
        main = self.packages_files[0] if self.packages_files else self.packages_label()
        lines = [
            "This would change the system if executed.",
            "",
            "Temporary (this user only):",
            f"  nix profile add nixpkgs#{package}",
            "",
            "Declarative (preferred):",
            f"  Add {package} to environment.systemPackages in:",
            f"  {main}",
        ]
        if len(self.packages_files) > 1:
            lines.append("  Also assigned in:")
            lines.extend(f"  {path}" for path in self.packages_files[1:])
        lines.extend([
            "",
            "  Then:",
            f"  {self.rebuild_command()}",
        ])
        if self.note:
            lines.extend(["", self.note])
        if self.style == "unknown":
            lines.extend([
                "",
                "No NixOS config was found at /etc/nixos.",
                "Set AINIX_NIXOS_CONFIG to the directory that holds it.",
            ])
        lines.extend([
            "",
            "AINIX does not edit that file.",
            "Preview never changes the system.",
            "",
            "Copy-friendly:",
            f"  nix profile add nixpkgs#{package}",
        ])
        return lines


def _excerpt_packages(path: Path, limit: int = 40) -> str:
    try:
        text = path.read_text(errors="ignore").splitlines()
    except OSError:
        return ""
    start = None
    for index, line in enumerate(text):
        if "environment.systemPackages" in line and "=" in line:
            start = index
            break
    if start is None:
        return ""
    chunk = []
    depth = 0
    for line in text[start:]:
        if re.search(r"password|secret|token", line, re.I):
            continue
        chunk.append(line)
        depth += line.count("[") + line.count("{") - line.count("]") - line.count("}")
        if len(chunk) >= limit or (len(chunk) > 1 and depth <= 0):
            break
    note = ""
    if start + len(chunk) < len(text):
        note = "\n# excerpt truncated"
    return f"Excerpt of {path}:\n" + "\n".join(chunk) + note


_PLAIN = {
    "openssh": "SSH is a line in the NixOS configuration. The line below is what this machine does today. Change that line, then rebuild.",
    "firewall": "The firewall is a line in the NixOS configuration. The line below is the current setting.",
    "opensnitch": "OpenSnitch is configured in the NixOS files below. Change the file, then rebuild.",
    "printing": "Printing is turned on in the NixOS configuration. The lines below are the current settings.",
    "systempackages": "A permanent package is added to environment.systemPackages in the file below. Then the system is rebuilt. nix profile add affects only this user.",
    "pipewire": "Sound is configured in the NixOS file below.",
    "plasma": "The desktop is selected in the NixOS file below.",
    "networkmanager": "Wi-Fi and wired connections are handled by NetworkManager, set in the file below.",
    "flatpak": "Flatpak is enabled from the NixOS file below.",
    "apparmor": "AppArmor is enabled from the NixOS file below.",
    "adguard": "DNS filtering is configured in the NixOS file below.",
}


def _plain_words(needles: list, path: Path) -> str:
    for needle in needles:
        text = _PLAIN.get(needle.lower().replace("_", ""))
        if text:
            return text
    return f"This setting lives in {path.name}. The line below is the current value. Edit that file, then rebuild."


def _is_advanced(query: str) -> bool:
    q = query.lower()
    if re.search(r"\b[a-z_][\w-]*\.[a-z_][\w.-]*", q):
        return True
    return any(word in q for word in ("default", "mkoption", "module system", "source", "override", "type of"))


def _needles(query: str) -> list:
    words = re.findall(r"[a-z0-9]+", query.lower())
    needles = []
    for word in words:
        if word in _STOP or len(word) < 3:
            continue
        needles.append(word)
        needles.extend(_SYNONYMS.get(word, []))
    unique = []
    for needle in needles:
        if needle not in unique:
            unique.append(needle)
    return unique


def _line_matches(stripped: str, needles: list) -> bool:
    if "=" not in stripped:
        return False
    lhs = stripped.split("=", 1)[0].split('"')[0].split("'")[0]
    segments = [part.lower().replace("_", "") for part in re.findall(r"[A-Za-z_][\w-]*", lhs)]
    if not segments:
        return False
    looking_for_packages = any(needle == "systempackages" for needle in needles)
    if looking_for_packages:
        return "systempackages" in segments
    if "." not in lhs:
        return False
    for needle in needles:
        name = needle.lower().replace("_", "")
        if name in segments:
            return True
        if len(name) >= 6 and any(name in segment for segment in segments):
            return True
    return False


def _option_name(stripped: str) -> str:
    lhs = stripped.split("=", 1)[0].split('"')[0].split("'")[0]
    match = _OPTION_NAME.search(lhs)
    return match.group(1) if match else ""


def valid_package_name(name: str) -> bool:
    return bool(_PACKAGE_NAME.fullmatch(name))


def detect(root: Optional[os.PathLike] = None) -> NixOSLayout:
    if root is not None:
        return _from_root(Path(root))
    env = os.environ.get("AINIX_NIXOS_CONFIG")
    if env:
        return _from_root(Path(env))
    etc = Path("/etc/nixos")
    if (etc / "configuration.nix").is_file() or (etc / "flake.nix").is_file():
        return _from_root(etc)
    return NixOSLayout(root=None, style="unknown")


def _from_root(root: Path) -> NixOSLayout:
    root = root.expanduser()
    if not root.is_dir():
        return NixOSLayout(root=root, style="unknown", note=f"Config directory does not exist: {root}")

    flake_text = _read(root / "flake.nix")
    names = _flake_config_names(flake_text) if flake_text is not None else []
    has_configuration = (root / "configuration.nix").is_file()

    if names or (flake_text is not None and not has_configuration):
        style = "flakes"
    elif has_configuration or flake_text is None:
        style = "channels" if has_configuration else "unknown"
    else:
        style = "unknown"

    host_names = _host_names(root)
    running = _running_hostname()
    host = None
    if len(host_names) == 1:
        host = host_names[0]
    elif running and any(n.lower() == running.lower() for n in host_names):
        host = next(n for n in host_names if n.lower() == running.lower())
    elif running and not host_names:
        host = running

    attr = _choose_flake_attr(names, host or running)
    note = ""
    if style == "flakes" and names and not attr:
        note = "This flake defines more than one NixOS configuration: " + ", ".join(names) + ". Use the name that matches this machine."

    packages = _packages_files(root) if style != "unknown" else []
    return NixOSLayout(
        root=root,
        style=style,
        host_name=host,
        flake_attr=attr,
        flake_names=names,
        packages_files=packages,
        note=note,
    )


def _read(path: Path):
    if not path.is_file():
        return None
    try:
        return path.read_text(errors="ignore")
    except OSError:
        return None


def _nix_files(root: Path):
    for path in sorted(root.rglob("*.nix")):
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        yield path


def _host_names(root: Path) -> list:
    found = []
    for path in _nix_files(root):
        text = _read(path) or ""
        for name in _HOST_NAME.findall(text):
            if name not in found:
                found.append(name)
    return found


def _running_hostname() -> Optional[str]:
    try:
        name = Path("/etc/hostname").read_text().strip()
    except OSError:
        return None
    return name or None


def _package_score(path: Path) -> int:
    text = _read(path) or ""
    score = 50 if re.search(r"\bwith\s+pkgs\b", text) else 0
    score += len(re.findall(r"(?m)^[ \t]+[A-Za-z_][\w.-]*[ \t]*$", text))
    return score


def _packages_files(root: Path) -> list:
    assigned = []
    for path in _nix_files(root):
        text = _read(path) or ""
        if _PACKAGES_ASSIGN.search(text):
            assigned.append(path)
    assigned.sort(key=lambda path: (-_package_score(path), str(path)))
    return assigned


def _choose_flake_attr(names: list, host: Optional[str]) -> Optional[str]:
    if not names:
        return None
    if len(names) == 1:
        return names[0]
    if host:
        for name in names:
            if name.lower() == host.lower():
                return name
    return None


def _flake_config_names(text: str) -> list:
    names = []

    def add(name: str):
        name = name.strip().strip('"').strip("'")
        if re.fullmatch(r"[A-Za-z_][\w.-]*", name) and name not in names:
            names.append(name)

    for name in re.findall(r"nixosConfigurations\.([A-Za-z_][\w.-]*)", text):
        add(name)
    for name in re.findall(r'nixosConfigurations\s*\.\s*"([^"]+)"', text):
        add(name)

    for match in re.finditer(r"nixosConfigurations\s*=\s*\{", text):
        body, _ = _take_braces(text, match.end() - 1)
        for name in _top_level_keys(body):
            add(name)
    return names


def _take_braces(text: str, open_at: int):
    depth = 0
    i = open_at
    buf = []
    while i < len(text):
        char = text[i]
        if char == "{":
            depth += 1
            if depth > 1:
                buf.append(char)
        elif char == "}":
            depth -= 1
            if depth == 0:
                return "".join(buf), i + 1
            buf.append(char)
        elif depth >= 1:
            buf.append(char)
        i += 1
    return "".join(buf), i


def _top_level_keys(body: str) -> list:
    names = []
    depth = 0
    token = []
    for char in body:
        if char == "{":
            depth += 1
            token = []
            continue
        if char == "}":
            depth = max(0, depth - 1)
            token = []
            continue
        if depth != 0:
            continue
        if char == "=":
            name = "".join(token).strip().strip('"').strip("'")
            if re.fullmatch(r"[A-Za-z_][\w.-]*", name):
                names.append(name)
            token = []
            continue
        if char in ";\n":
            token = []
            continue
        token.append(char)
    return names
