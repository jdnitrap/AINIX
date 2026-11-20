"""One boolean toggle used to try the Options control."""

import os
import re

from ainix_help.plan import Edit, Plan, commands_from
from ainix_help.search import plain_bool

OPTION = "documentation.nixos.enable"
LINE = re.compile(
    r"^\s*documentation\.nixos\.enable\s*=\s*([^;#]+?)\s*;"
)


def find_documentation_enable(root):
    """The existing assignment, or None when this tree does not set it."""
    if not root or not os.path.isdir(root):
        return None
    root = os.path.realpath(root)
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [name for name in dirs if name not in {".git", "result"}]
        for name in files:
            if not name.endswith(".nix"):
                continue
            path = os.path.join(dirpath, name)
            try:
                lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
            except OSError:
                continue
            for number, line in enumerate(lines, 1):
                match = LINE.match(line)
                if match is None:
                    continue
                value = match.group(1).strip()
                shown = plain_bool(value)
                if shown not in {"true", "false"}:
                    continue
                where = os.path.relpath(path, root) + f":{number}"
                return Edit(path, number, OPTION, shown, value, where)
    return None


def documentation_plan(root, new_value):
    """A plan that flips documentation.nixos.enable, or None when nothing would change."""
    if new_value not in {"true", "false"}:
        return None
    edit = find_documentation_enable(root)
    if edit is None or plain_bool(edit.old_value) == new_value:
        return None
    edit.new_value = new_value
    plan = Plan()
    plan.edits.append(edit)
    from core.nixos_layout import detect

    dry, switch, boot, names, needs_host = commands_from(detect(root))
    plan.dry_build = dry
    plan.switch = switch
    plan.boot = boot
    plan.flake_names = names
    plan.needs_host = needs_host
    return plan
