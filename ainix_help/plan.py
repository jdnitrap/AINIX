"""The file edit and the rebuild commands an answer is willing to run."""

import os
import re
from pathlib import Path


class Edit:
    def __init__(self, path, line, option, new_value, old_value, where, kind="assign"):
        self.path = path
        self.line = line
        self.option = option
        self.new_value = new_value
        self.old_value = old_value
        self.where = where
        self.kind = kind


def button_state(plan):
    """Apply edits the configuration. Build can install while an edit is waiting."""
    if plan is None:
        return False, False
    return bool(plan.edits), bool(plan.dry_build)


class Plan:
    def __init__(self):
        self.edits = []
        self.dry_build = ""
        self.switch = ""
        self.boot = ""
        self.flake_names = []
        self.needs_host = False

    def with_host(self, host):
        if not self.needs_host:
            return self.dry_build, self.switch, self.boot
        if not re.fullmatch(r"[A-Za-z_][\w.-]*", host or ""):
            raise ValueError("Pick a host name from the flake.")
        return (
            self.dry_build.replace("#<name>", "#" + host),
            self.switch.replace("#<name>", "#" + host),
            self.boot.replace("#<name>", "#" + host),
        )


class Answer(str):
    """Answer text plus the plan the Apply button may run."""

    def __new__(cls, text, plan=None):
        obj = str.__new__(cls, text)
        obj.plan = plan if plan is not None else Plan()
        return obj


def remember(plan, item, new_value):
    if plan is None or item is None or new_value not in {"true", "false"}:
        return
    where = item.get("where") or ""
    line = 0
    if ":" in where:
        tail = where.rsplit(":", 1)[-1]
        if tail.isdigit():
            line = int(tail)
    plan.edits.append(Edit(
        path=item.get("path") or "",
        line=line,
        option=item["option"],
        new_value=new_value,
        old_value=item.get("value") or "",
        where=where,
    ))


def remember_new(plan, option, new_value):
    if plan is None or new_value not in {"true", "false"}:
        return
    plan.edits.append(Edit("", 0, option, new_value, "", ""))


def commands_from(layout):
    """Dry-build, switch, and boot for this configuration.

    Boot builds the generation the next restart will use and leaves the
    running system as it is. A directory that is not /etc/nixos and not a
    flake is passed with -I nixos-config.
    """
    if layout is not None and layout.style == "flakes" and layout.root is not None:
        switch = layout.rebuild_command()
        dry = switch.replace(" switch", " dry-build", 1)
        boot = switch.replace(" switch", " boot", 1)
        names = list(layout.flake_names)
        return dry, switch, boot, names, "#<name>" in switch
    if layout is not None and layout.root is not None:
        root = Path(layout.root).resolve()
        etc = Path("/etc/nixos")
        etc_real = etc.resolve() if etc.exists() else None
        if etc_real == root:
            pass
        else:
            config_nix = root / "configuration.nix"
            if config_nix.is_file():
                switch = f"sudo nixos-rebuild switch -I nixos-config={config_nix}"
                dry = switch.replace(" switch", " dry-build", 1)
                boot = switch.replace(" switch", " boot", 1)
                return dry, switch, boot, [], False
            # A foreign directory with no flake would otherwise rebuild /etc/nixos.
            return "", "", "", [], False
    return (
        "sudo nixos-rebuild dry-build",
        "sudo nixos-rebuild switch",
        "sudo nixos-rebuild boot",
        [],
        False,
    )


def fill_commands(plan, layout):
    dry, switch, boot, names, needs_host = commands_from(layout)
    plan.dry_build = dry
    plan.switch = switch
    plan.boot = boot
    plan.flake_names = names
    plan.needs_host = needs_host
    if not dry:
        return [
            "No rebuild command is offered. This directory is not /etc/nixos and it has no flake or configuration.nix.",
        ]
    lines = [
        f"Build, when you want it, with: {dry}",
        f"Then, when the dry build succeeds: {switch}",
        f"Or build it for the next boot and leave the running system as it is: {boot}",
    ]
    if layout is not None and layout.note:
        lines.append(layout.note)
    return lines


def _flake_spec(token):
    if token.count("#") != 1:
        return False
    path, name = token.split("#", 1)
    if not path.startswith("/") or not re.fullmatch(r"[A-Za-z_][\w.-]*", name):
        return False
    return ".." not in Path(path).parts


def _config_arg(token):
    prefix = "nixos-config="
    if not token.startswith(prefix):
        return False
    path = token[len(prefix):]
    if not path.startswith("/") or not path.endswith("/configuration.nix"):
        return False
    return ".." not in Path(path).parts


def validate_rebuild(command):
    """Return argv for nixos-rebuild, without sudo. Refuse anything else."""
    import shlex

    parts = shlex.split(command)
    if parts and parts[0] == "sudo":
        parts = parts[1:]
    if len(parts) < 2 or parts[0] != "nixos-rebuild":
        raise ValueError("Refusing to run that command.")
    if parts[1] not in {"dry-build", "switch", "boot"}:
        raise ValueError("Refusing to run that rebuild action.")
    rest = parts[2:]
    if not rest:
        return parts
    if len(rest) == 2 and rest[0] == "--flake" and _flake_spec(rest[1]):
        return parts
    if len(rest) == 2 and rest[0] == "-I" and _config_arg(rest[1]):
        return parts
    raise ValueError("Refusing to run that command.")


def inside_config(config_root, path):
    if not config_root or not path:
        return False
    root = os.path.realpath(config_root)
    target = os.path.realpath(path)
    return target == root or target.startswith(root + os.sep)
