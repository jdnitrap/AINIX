"""Write the lines Apply confirmed, and run the rebuild Apply confirmed."""

import os
import re
import subprocess
from pathlib import Path

from ainix_help.plan import inside_config, validate_rebuild


class ApplyError(Exception):
    pass


LINE = re.compile(
    r"^(?P<indent>\s*)(?P<name>[A-Za-z_][\w.]*)\s*=\s*(?P<value>[^;#]*?)"
    r"(?P<space>\s*)(?P<semi>;?)(?P<tail>\s*(?:#.*)?)?$"
)


def name_ok(name, option):
    return name == option or option.endswith("." + name)


def rewrite_line(raw, option, new_value, old_value):
    """Replace the value on this line. Keep the indent, the name, and a comment."""
    if new_value not in {"true", "false"}:
        return None
    ending = "\n" if raw.endswith("\n") else ""
    body = raw[:-1] if ending else raw
    match = LINE.match(body)
    if match is None or not name_ok(match.group("name"), option):
        return None
    current = match.group("value").strip()
    if old_value and current != old_value.strip():
        return None
    semi = match.group("semi") or ";"
    rewritten = (
        f"{match.group('indent')}{match.group('name')} = {new_value}{semi}{match.group('tail') or ''}"
    )
    return rewritten + ending


def insert_assignment(text, option, new_value):
    addition = f"  {option} = {new_value};\n"
    lines = text.splitlines(keepends=True)
    for index in range(len(lines) - 1, -1, -1):
        if lines[index].strip() == "}":
            lines.insert(index, addition)
            return "".join(lines)
    if text and not text.endswith("\n"):
        text += "\n"
    return text + addition


def render_file(original, edits):
    packages = [edit for edit in edits if getattr(edit, "kind", "assign") == "package"]
    assigns = [edit for edit in edits if getattr(edit, "kind", "assign") != "package"]
    lines = original.splitlines(keepends=True)
    for edit in sorted((item for item in assigns if item.line), key=lambda item: item.line):
        if edit.line < 1 or edit.line > len(lines):
            raise ApplyError(f"Line {edit.line} is no longer in {edit.where or edit.path}.")
        rewritten = rewrite_line(lines[edit.line - 1], edit.option, edit.new_value, edit.old_value)
        if rewritten is None:
            raise ApplyError(f"The line no longer matches {edit.option} in {edit.where or edit.path}.")
        lines[edit.line - 1] = rewritten
    text = "".join(lines)
    for edit in assigns:
        if edit.line:
            continue
        text = insert_assignment(text, edit.option, edit.new_value)
    for edit in packages:
        if not edit.line:
            from ainix_help.install_edit import fresh_list_rhs

            if not fresh_list_rhs(edit.new_value):
                raise ApplyError("Refusing to write that package list.")
            text = insert_assignment(text, edit.option, edit.new_value)
            continue
        from ainix_help.install_edit import insert_existing_package

        text = insert_existing_package(text, edit)
    return text


def apply_edits(edits, config_root):
    """Write every confirmed edit, or write nothing if one line does not match."""
    if not edits:
        raise ApplyError("There is no line to write.")
    if not config_root or not os.path.isdir(config_root):
        raise ApplyError("The configuration directory is missing.")
    grouped = {}
    for edit in edits:
        if not edit.path:
            raise ApplyError(f"Pick the file that should set {edit.option}.")
        if not inside_config(config_root, edit.path):
            raise ApplyError("That file is outside the configuration directory.")
        if not os.path.isfile(edit.path):
            raise ApplyError(f"That file is missing: {edit.path}")
        grouped.setdefault(os.path.realpath(edit.path), []).append(edit)
    pending = {}
    for path, group in grouped.items():
        original = Path(path).read_text(encoding="utf-8")
        pending[path] = render_file(original, group)
    written = []
    for path, text in pending.items():
        temporary = path + ".ainix-tmp"
        try:
            with open(temporary, "w", encoding="utf-8") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        written.append(path)
    return written


def sudo_needs_password():
    done = subprocess.run(["sudo", "-n", "true"], capture_output=True, text=True)
    return done.returncode != 0


def run_rebuild(command, password, on_line=None):
    """Run one allowlisted nixos-rebuild. password is None when sudo is already cached."""
    parts = validate_rebuild(command)
    if password is None:
        cmd = ["sudo", "-n", *parts]
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    else:
        proc = subprocess.Popen(
            ["sudo", "-S", "-p", "", *parts],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        proc.stdin.write(password + "\n")
        proc.stdin.close()
    chunks = []
    for line in proc.stdout:
        chunks.append(line)
        if on_line is not None:
            on_line(line.rstrip("\n"))
    code = proc.wait()
    return code, "".join(chunks)
