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
