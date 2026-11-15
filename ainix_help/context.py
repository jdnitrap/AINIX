"""Facts about the machine or project the question is about."""

import os
import re
import subprocess


STOP = {
    "the", "and", "for", "how", "do", "does", "did", "can", "what", "why",
    "when", "where", "which", "with", "from", "this", "that", "into", "your",
    "you", "are", "was", "not", "but", "about", "have", "has", "please",
    "help", "want", "need", "just", "its", "it's", "use", "using", "get",
    "nix", "nixos",
}


def run(cmd, timeout=8):
    try:
        done = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return (done.stdout or "") + (done.stderr or "")


def nixos_version():
    text = run(["nixos-version"]).strip().splitlines()
    return text[0].strip() if text else ""


def release_of(version):
    match = re.match(r"(\d+\.\d+)", version)
    return match.group(1) if match else ""


def revision_of(version):
    match = re.search(r"\b([0-9a-f]{7,40})\b", version)
    return match.group(1) if match else ""


def config_root():
    chosen = os.environ.get("AINIX_NIXOS_CONFIG", "").strip()
    if chosen and os.path.isdir(chosen):
        return chosen
    for path in ("/etc/nixos", os.path.expanduser("~/.config/nixos")):
        if os.path.isdir(path):
            return path
    return ""


def nix_path_roots():
    roots = []
    for item in os.environ.get("NIX_PATH", "").split(":"):
        if "=" in item:
            _name, path = item.split("=", 1)
        else:
            path = item
        if path and os.path.isdir(path):
            roots.append(path)
    channels = "/nix/var/nix/profiles/per-user/root/channels"
    if os.path.isdir(channels):
        for name in os.listdir(channels):
            path = os.path.join(channels, name)
            if os.path.isdir(path):
                roots.append(path)
    seen = []
    for path in roots:
        real = os.path.realpath(path)
        if real not in seen:
            seen.append(real)
    return seen


def uses_home_manager(config):
    if not config:
        return False
    for dirpath, _dirs, files in os.walk(config):
        for name in files:
            if not name.endswith(".nix"):
                continue
            path = os.path.join(dirpath, name)
            try:
                text = open(path, encoding="utf-8", errors="replace").read(200_000)
            except OSError:
                continue
            if "home-manager" in text or "home.nix" in text:
                return True
    home = os.path.expanduser("~/.config/home-manager")
    return os.path.isdir(home)


def terms(question):
    words = re.findall(r"[A-Za-z0-9_./-]{3,}", question.lower())
    out = []
    for word in words:
        if word in STOP or word in out:
            continue
        out.append(word)
    return out[:12]


def kind_of(question):
    low = question.lower()
    if any(word in low for word in ("error", "failed", "failure", "traceback", "collision", "attribute")):
        return "fix"
    return "learn"


class Context:
    def __init__(self, question, config=""):
        self.question = question.strip()
        self.version = nixos_version()
        self.release = release_of(self.version)
        self.revision = revision_of(self.version)
        self.config = config or config_root()
        self.nixpkgs = nix_path_roots()
        self.home_manager = uses_home_manager(self.config)
        self.terms = terms(self.question)
        self.kind = kind_of(self.question)
        self.wants_enable = bool(re.search(r"\b(enable|start|turn on)\b", self.question.lower()))
        self.wants_disable = bool(re.search(r"\b(disable|turn off|stop)\b", self.question.lower()))
