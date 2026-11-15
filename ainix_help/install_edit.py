"""Add one package to environment.systemPackages.

Apply writes that name into the list this machine already uses for packages.
A list of local names, such as a helper module, is left alone.
"""

import os
import re
from pathlib import Path

from ainix_help.plan import Answer, Edit, Plan, fill_commands


_ATTR = re.compile(r"^[A-Za-z_][\w+-]*(?:\.[A-Za-z_][\w+-]*)*$")
_QUESTION = re.compile(
    r"^how do i install\s+(?P<attr>pkgs\.[A-Za-z_][\w+-]*(?:\.[A-Za-z_][\w+-]*)*"
    r"|[A-Za-z_][\w+-]*(?:\.[A-Za-z_][\w+-]*)*)\s*\??$",
    re.IGNORECASE,
)
_ASSIGN = re.compile(r"environment\.systemPackages\s*=")
_HEAD = re.compile(r"\s*(?:with\s+(?P<scope>[A-Za-z_][\w]*)\s*;)?\s*\[")
_TOKEN = re.compile(r"[A-Za-z_][\w+-]*(?:\.[A-Za-z_][\w+-]*)*")
_RHS = re.compile(r"with pkgs; \[ [A-Za-z_][\w+-]*(?:\.[A-Za-z_][\w+-]*)* \]")
_RESERVED = {"with", "inherit", "assert", "let", "in", "if", "then", "else", "or", "rec"}
_SKIP = {".git", "result", ".direnv"}


class PackageList:
    def __init__(self, path, line, scope, entries, body, open_at, close_at, assign_at):
        self.path = path
        self.line = line
        self.scope = scope
        self.entries = entries
        self.body = body
        self.open_at = open_at
        self.close_at = close_at
        self.assign_at = assign_at


def valid_attr(attr):
    if not attr or len(attr) > 200 or _ATTR.fullmatch(attr) is None:
        return False
    return not any(part in _RESERVED for part in attr.split("."))


def install_question(question, config=""):
    """The install plan for "How do I install <package>?", or None."""
    match = _QUESTION.match((question or "").strip())
    if match is None:
        return None
    return install_answer(match.group("attr"), config)


def install_answer(attr, config="", unfree=False, broken=False):
    attr = (attr or "").strip()
    if attr.startswith("pkgs."):
        attr = attr[5:]
    if not valid_attr(attr):
        return Answer(f"Not a package name: {attr}", Plan())
    config = (config or "").strip()
    if config and not os.path.isdir(config):
        return Answer(f"That configuration directory does not exist: {config}", Plan())
    from core.nixos_layout import detect

    layout = detect(config or None)
    root = layout.root if layout.root is not None and layout.root.is_dir() else None
    lists = _lists(root)
    plan = Plan()
    lines = []
    if broken:
        lines.append("The channel marks this package broken.")
    if unfree and not _allows_unfree(root):
        lines.append("This package is unfree. The build needs nixpkgs.config.allowUnfree = true.")
    held = [item for item in lists if _contains(item, attr)]
    if held:
        lines.append(f"{attr} is already in {held[0].path}:{held[0].line}.")
        lines.append("No line needs to change for that.")
        lines.append("")
        lines.append("This is a preview. Nothing was edited and nothing was built.")
        return Answer("\n".join(lines), plan)

    safe = [item for item in lists if _safe(item)]
    lines.append(f"{attr} is not in your package lists.")
    lines.append("")
    lines.append("Suggested change")
    if safe:
        safe.sort(key=lambda item: (-_rank(item), str(item.path), item.line))
        target = safe[0]
        token = attr if target.scope == "pkgs" else "pkgs." + attr
        where = f"{target.path}:{target.line}"
        plan.edits.append(Edit(
            str(target.path), target.line, "environment.systemPackages",
            token, "", where, "package",
        ))
        lines.append(where)
        if target.scope == "pkgs":
            lines.append("That list uses with pkgs, so the name is added on its own.")
        lines.append(f"+ {token}")
        seen = set()
        for item in lists:
            key = str(item.path)
            if key == str(target.path) or key in seen:
                continue
            seen.add(key)
            lines.append(f"Left unchanged: {key}")
    else:
        config_nix = (root / "configuration.nix") if root is not None else None
        path = str(config_nix) if config_nix is not None and config_nix.is_file() else ""
        rhs = f"with pkgs; [ {attr} ]"
        plan.edits.append(Edit(
            path, 0, "environment.systemPackages", rhs, "", path, "package",
        ))
        if path:
            lines.append(path)
            lines.append("No package list there can take a pkgs name, so a new list is added to configuration.nix.")
        else:
            lines.append("No package list can take a pkgs name. Apply asks which file should gain the list.")
        lines.append(f"+ environment.systemPackages = {rhs};")
    lines.extend(fill_commands(plan, layout))
    lines.append("")
    lines.append("This is a preview. Nothing was edited and nothing was built.")
    return Answer("\n".join(lines), plan)


def insert_existing_package(text, edit):
    """Insert the confirmed package into the list that is still on this line."""
    from ainix_gui.changes import ApplyError

    info = next((item for item in parse_lists(text, "") if item.line == edit.line), None)
    if info is None:
        raise ApplyError(f"The package list is no longer on line {edit.line}.")
    token = (edit.new_value or "").strip()
    if not _safe_token(token):
        raise ApplyError("Refusing to write that package name.")
    attr = token[5:] if token.startswith("pkgs.") else token
    if _contains(info, attr):
        raise ApplyError(f"{attr} is already in that list.")
    return _insert_at(text, info, token)


def parse_lists(text, path):
    found = []
    for match in _ASSIGN.finditer(text):
        head = _HEAD.match(text, match.end())
        if head is None:
            continue
        open_at = head.end() - 1
        if open_at < 0 or text[open_at] != "[":
            continue
        body, close_at = _scan_list(text, open_at)
        if close_at >= len(text) or text[close_at] != "]":
            continue
        found.append(PackageList(
            path=path,
            line=text[:match.start()].count("\n") + 1,
            scope=head.group("scope") or "",
            entries=_entries(body),
            body=body,
            open_at=open_at,
            close_at=close_at,
            assign_at=match.start(),
        ))
    return found


def _lists(root):
    found = []
    if root is None:
        return found
    for path in _nix_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if "environment.systemPackages" not in text:
            continue
        found.extend(parse_lists(text, path))
    return found


def _nix_files(root):
    for path in sorted(Path(root).rglob("*.nix")):
        if any(part in _SKIP for part in path.parts):
            continue
        yield path


def _allows_unfree(root):
    if root is None:
        return False
    for path in _nix_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if re.search(r"allowUnfree\s*=\s*true\s*;", text):
            return True
    return False


def _contains(info, attr):
    prefixed = "pkgs." + attr
    return any(entry == attr or entry == prefixed for entry in info.entries)


def _safe(info):
    return info.scope == "pkgs" or any(entry.startswith("pkgs.") for entry in info.entries)


def _rank(info):
    score = len(info.entries)
    if "package" in Path(info.path).name.lower():
        score += 100
    if info.scope == "pkgs":
        score += 50
    return score


def _safe_token(token):
    if token.startswith("pkgs."):
        return valid_attr(token[5:])
    return valid_attr(token)


def _entries(body):
    no_block = re.sub(r"/\*.*?\*/", " ", body, flags=re.S)
    no_comments = re.sub(r"#[^\n]*", " ", no_block)
    return _TOKEN.findall(no_comments)


def _scan_list(text, open_at):
    i = open_at + 1
    depth = 1
    buf = []
    while i < len(text):
        char = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if char == "#":
            newline = text.find("\n", i)
            if newline < 0:
                buf.append(text[i:])
                return "".join(buf), len(text)
            buf.append(text[i:newline + 1])
            i = newline + 1
            continue
        if char == "/" and nxt == "*":
            end = text.find("*/", i + 2)
            if end < 0:
                buf.append(text[i:])
                return "".join(buf), len(text)
            buf.append(text[i:end + 2])
            i = end + 2
            continue
        if char in "\"'":
            end = i + 1
            while end < len(text):
                if text[end] == "\\":
                    end += 2
                    continue
                if text[end] == char:
                    break
                end += 1
            end = min(end, len(text) - 1)
            buf.append(text[i:end + 1])
            i = end + 1
            continue
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return "".join(buf), i
        buf.append(char)
        i += 1
    return "".join(buf), len(text)


def _insert_at(text, info, token):
    close_at = info.close_at
    line_start = text.rfind("\n", 0, close_at) + 1
    own_line = "\n" in text[info.open_at:close_at] and text[line_start:close_at].strip() == ""
    if own_line:
        indent = _entry_indent(info.body, text, info.assign_at)
        return text[:line_start] + f"{indent}{token}\n" + text[line_start:]
    before = text[close_at - 1] if close_at else ""
    gap = "" if before.isspace() or before == "[" else " "
    return text[:close_at] + gap + token + " " + text[close_at:]


def _entry_indent(body, text, assign_at):
    for line in reversed(body.splitlines()):
        if line.strip() and not line.strip().startswith("#"):
            return re.match(r"[ \t]*", line).group(0)
    line_start = text.rfind("\n", 0, assign_at) + 1
    return re.match(r"[ \t]*", text[line_start:]).group(0) + "  "


def fresh_list_rhs(value):
    return bool(_RHS.fullmatch(value or ""))
