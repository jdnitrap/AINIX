"""Compare every source and join the pieces that fit. Do not invent a missing piece."""

import os
import re

from ainix_help.plan import Answer, Plan, fill_commands, remember, remember_new
from ainix_help.search import (
    SERVICE_WORDS,
    distinctive,
    plain_bool,
    primary_words,
    search_words,
    setting_terms,
    tokens,
    word_hit,
)


ASSIGN = re.compile(
    r"^\s*([a-zA-Z][A-Za-z0-9]*(\.[A-Za-z0-9_-]+){1,8})\s*=\s*([^;#]+)"
)


def score(hit, ctx):
    text = f"{hit.title}\n{hit.excerpt}".lower()
    points = 0
    for term in ctx.terms:
        if term in hit.title.lower():
            points += 3
        elif term in text:
            points += 1
    if ctx.release and ctx.release in text:
        points += 2
    if hit.source == "your files":
        points += 2
    hit.score = points
    return points


def assignment_rank(item, ctx):
    """Rank by whole tokens. "ssh" matches openssh and does not match endlessh."""
    words = search_words(ctx)
    points = 3 if word_hit(item["option"], words) else 0
    if (
        (ctx.wants_enable or ctx.wants_disable)
        and item["option"].endswith(".enable")
        and word_hit(item["option"], words)
        and not setting_terms(ctx)
    ):
        points += 8
    return points


def assignments(hits):
    found = []
    for hit in hits:
        if hit.source != "your files":
            continue
        match = ASSIGN.match(hit.excerpt.strip())
        if not match:
            continue
        found.append({
            "option": match.group(1),
            "value": match.group(3).strip(),
            "where": hit.title,
            "path": hit.url,
            "excerpt": hit.excerpt.strip(),
        })
    return found


def source_order(source):
    order = {
        "nixos-option": 0,
        "nixpkgs": 1,
        "wiki": 2,
        "release notes": 3,
        "discourse": 4,
        "github nixpkgs": 5,
        "duckduckgo": 6,
        "youtube": 7,
        "github nix": 8,
        "nix help": 9,
    }
    return order.get(source, 10)


def on_topic(hit, focus, ctx):
    blob = f"{hit.title}\n{hit.excerpt}"
    primary = set(primary_words(ctx))
    title = set(tokens(hit.title))
    subject = set(distinctive(ctx.terms))
    if focus and focus in blob:
        # An issue body can mention the option while arguing about something else.
        if hit.source.startswith("github") or hit.source == "discourse":
            return focus in hit.title or bool(title & primary)
        return True
    if hit.source == "wiki" and title and title <= (primary | subject):
        return True
    if hit.source in {"duckduckgo", "youtube"} and (title & primary or ("nixos" in title and title & subject)):
        return True
    return False


LITERAL = re.compile(r"^(?:true|false|null|\d+|\"[^\"]{0,60}\"|'[^']{0,60}')$")


def literal_values(focus, hit):
    if hit.source not in {"your files", "wiki", "discourse"}:
        return []
    found = []
    pattern = re.compile(re.escape(focus) + r"\s*=\s*([^;#\n]+)")
    for match in pattern.finditer(hit.excerpt):
        raw = match.group(1).strip().strip("`").rstrip(".").strip()
        if LITERAL.fullmatch(raw):
            found.append(raw)
    return found


def render_hits(lines, hits, limit):
    seen_url = set()
    per_source = {}
    shown = 0
    for hit in hits:
        key = (hit.source, hit.title, hit.url)
        if key in seen_url or per_source.get(hit.source, 0) >= 2:
            continue
        seen_url.add(key)
        per_source[hit.source] = per_source.get(hit.source, 0) + 1
        lines.append(f"- {hit.source}: {hit.title}")
        if hit.url:
            lines.append(f"  {hit.url}")
        if hit.excerpt:
            lines.append(f"  {hit.excerpt[:320]}")
        shown += 1
        if shown >= limit:
            break
    return shown


def assemble(ctx, hits, notes, names):
    for hit in hits:
        score(hit, ctx)
    ranked = sorted(hits, key=lambda hit: (-hit.score, hit.source, hit.title))
    strong = [hit for hit in ranked if hit.score >= 2]
    local = sorted(assignments(hits), key=lambda item: (-assignment_rank(item, ctx), item["where"]))
    lines = []
    lines.append(f"Question: {ctx.question}")
    version = ctx.version or "version unknown"
    lines.append(f"Machine: NixOS {version}")
    if ctx.config:
        lines.append(f"Configuration: {ctx.config}")
    lines.append("")
    lines.append("Asked")
    for note in sorted(notes):
        lines.append(f"- {note}")
    lines.append("")

    vague = {
        "attribute", "missing", "rebuild", "failed", "failure", "error",
        "undefined", "variable", "infinite", "recursion", "traceback", "collision",
    }
    rare = [term for term in distinctive(ctx.terms) if term not in vague and term not in SERVICE_WORDS]
    if rare and not any(term in tokens(hit.title + "\n" + hit.excerpt) for hit in hits for term in rare):
        strong = []
        local = []

    if not strong and not local:
        lines.append("No solid match.")
        lines.append("The sources were asked together. Nothing overlapped the question, the version, and the files enough to build a fix.")
        lines.append("")
        lines.append("Best candidate from each source that answered")
        shown = set()
        wanted = distinctive(ctx.terms)
        for hit in ranked:
            if hit.source in shown:
                continue
            blob = f"{hit.title}\n{hit.excerpt}"
            needed = rare or wanted
            if needed and not any(term in tokens(blob) for term in needed):
                continue
            shown.add(hit.source)
            lines.append(f"- {hit.source}: {hit.title}")
            if hit.url:
                lines.append(f"  {hit.url}")
            if hit.excerpt:
                lines.append(f"  {hit.excerpt[:240]}")
        if not shown:
            lines.append("- No source used the words in the question.")
        return Answer("\n".join(lines), Plan())

    lines.append("Brought together")
    focus = choose_focus(local, names, ctx)
    specific = setting_terms(ctx)
    shown_local = local
    if specific and focus:
        need = sum(1 for term in specific if term in tokens(focus))
        shown_local = [
            item for item in local
            if sum(1 for term in specific if term in tokens(item["option"])) >= need
        ]
    used = []
    if shown_local:
        for item in shown_local[:4]:
            lines.append(
                f"- Your files set {item['option']} to {item['value']} in {item['where']}."
            )
            lines.append(f"  {item['path']}")
            used.append(item["option"])
    elif focus:
        lines.append(f"- Your files do not set {focus}.")
    else:
        lines.append("- Your files do not mention this by name.")
    related = [hit for hit in (strong or ranked) if on_topic(hit, focus, ctx)] if focus else []
    others = [hit for hit in related if hit.source != "your files"]
    others.sort(key=lambda hit: (source_order(hit.source), -hit.score, hit.title))

    fix_sources = {"nixos-option", "nixpkgs", "wiki", "release notes"}
    fix_hits = [hit for hit in others if hit.source in fix_sources]
    link_hits = [hit for hit in others if hit.source not in fix_sources]
    wrote = render_hits(lines, fix_hits, 6)
    if focus and not wrote:
        lines.append(f"- No other source described {focus}.")
    if link_hits:
        lines.append("")
        lines.append("Also found")
        render_hits(lines, link_hits, 6)

    conflicts = []
    values = {}
    if focus:
        for hit in related:
            for value in literal_values(focus, hit):
                sources = values.setdefault(value, [])
                if hit.source not in sources:
                    sources.append(hit.source)
    if len(values) > 1:
        conflicts.append((focus, values))

    if conflicts:
        lines.append("")
        lines.append("Disagree")
        for option, values in conflicts:
            parts = [f"{value} ({', '.join(sources)})" for value, sources in values.items()]
            lines.append(f"- {option} is given as " + "; ".join(parts) + ".")
            lines.append("  The file shows the current setting. A different value elsewhere is an example from that source.")
            outside = [value for value, sources in values.items() if any(source != "your files" for source in sources)]
            if len(outside) > 1 and ctx.release:
                lines.append(f"  When those examples disagree with each other, prefer the one that names NixOS {ctx.release}.")

    plan = Plan()
    suggestion = suggest(ctx, local, focus, values if focus else {}, others, plan)
    if suggestion:
        lines.append("")
        lines.append("Suggested change")
        lines.extend(suggestion)

    missing = []
    if not local:
        missing.append("which file should change")
    if not any(hit.source == "nixos-option" for hit in hits):
        missing.append("the option type and default from nixos-option")
    if focus and not values and not suggestion:
        missing.append("an explicit value from the sources")
    if missing:
        lines.append("")
        lines.append("Still missing")
        for item in missing:
            lines.append(f"- {item}")

    lines.append("")
    lines.append("This is a preview. Nothing was edited and nothing was built.")
    return Answer("\n".join(lines), plan)


def choose_focus(local, names, ctx):
    specific = setting_terms(ctx)
    if not specific:
        if local:
            return local[0]["option"]
        return names[0] if names else ""

    def cover(option):
        return sum(1 for term in specific if term in tokens(option))

    best_option = ""
    best_cover = 0
    for option in [item["option"] for item in local] + list(names):
        score = cover(option)
        if score > best_cover:
            best_option = option
            best_cover = score
    return best_option


def wants_on(ctx):
    if ctx.wants_enable:
        return True
    return bool(re.search(r"\b(allow|permit)\b", ctx.question.lower()))


def replacement_for(focus, local):
    if focus != "services.pulseaudio.enable":
        return None
    for name in ("services.pipewire.pulse.enable", "services.pipewire.enable"):
        for item in local:
            if item["option"] == name and plain_bool(item["value"]) in {"true", "1"}:
                return item
    return None


def machine_layout(ctx):
    if not ctx.config or not os.path.isdir(ctx.config):
        return None
    from core.nixos_layout import detect
    return detect(ctx.config)


def build_lines(layout, plan):
    return fill_commands(plan, layout)


def openssh_daemon_off(local, focus):
    if not focus.startswith("services.openssh.") or focus == "services.openssh.enable":
        return None
    daemon = next((item for item in local if item["option"] == "services.openssh.enable"), None)
    if daemon and plain_bool(daemon["value"]) in {"false", "0"}:
        return daemon
    return None


def daemon_lines(local, focus, plan=None):
    daemon = openssh_daemon_off(local, focus)
    if daemon is None:
        return []
    remember(plan, daemon, "true")
    return [
        daemon["where"],
        f"- {daemon['excerpt']}",
        "+ services.openssh.enable = true;",
        "The daemon is off, so the password setting would not be reached.",
    ]


def stated_default(focus, support):
    for hit in support:
        blob = f"{hit.title}\n{hit.excerpt}"
        if focus not in blob and hit.title != focus:
            continue
        match = re.search(r"(?:Default:\s*|default = )(true|false)", blob)
        if match:
            return match.group(1)
    return ""


def wants_flip(ctx, focus):
    return ctx.wants_enable or ctx.wants_disable or focus.endswith(".enable") or bool(setting_terms(ctx))


def desired_value(ctx, focus, value):
    if not wants_flip(ctx, focus):
        return None
    if wants_on(ctx) and value in {"false", "0"}:
        return "true"
    if ctx.wants_disable and value in {"true", "1"}:
        return "false"
    return None


def reason_lines(focus, desired, values, support):
    agreed = desired in values
    described = any(
        hit.source == "nixos-option" and focus in f"{hit.title}\n{hit.excerpt}"
        for hit in support
    )
    if agreed:
        return ["That value appears in another source as well."]
    if described:
        return ["nixos-option documents this name. The other sources did not print this exact value, so the value follows the question."]
    return ["No other source stated this value. It is only the direction of the question."]


def suggest(ctx, local, focus, values, support, plan):
    if not focus:
        return []
    layout = machine_layout(ctx)
    other = replacement_for(focus, local)
    if other and wants_on(ctx):
        shown = plain_bool(other["value"]) or other["value"]
        return [
            other["where"],
            f"{other['option']} is {shown}.",
            "PipeWire is already providing PulseAudio on this machine.",
            "Leave services.pulseaudio.enable = false.",
        ]
    same = [item for item in local if item["option"] == focus]
    if len(same) > 1:
        return several_places(ctx, local, same, focus, values, support, layout, plan)
    current = same[0] if same else None
    if current is None:
        return missing_option(ctx, local, focus, support, layout, plan)
    value = plain_bool(current["value"]) or current["value"]
    desired = desired_value(ctx, focus, plain_bool(current["value"]))
    if desired is None:
        return [
            f"{focus} is already {value} in {current['where']}.",
            "No line needs to change for that.",
        ]
    lines = [
        f"{current['where']}",
        f"- {current['excerpt']}",
        f"+ {focus} = {desired};",
    ]
    remember(plan, current, desired)
    lines.extend(reason_lines(focus, desired, values, support))
    lines.extend(daemon_lines(local, focus, plan))
    lines.extend(build_lines(layout, plan))
    return lines


def several_places(ctx, local, same, focus, values, support, layout, plan):
    parsed = [plain_bool(item["value"]) or item["value"] for item in same]
    lines = ["This option is set in more than one place."]
    for item in same:
        lines.append(f"- {item['where']}: {item['excerpt']}")
    if len(set(parsed)) > 1:
        lines.append("Those values disagree. No line is suggested until the host is known.")
        lines.extend(build_lines(layout, plan))
        return lines
    desired = desired_value(ctx, focus, plain_bool(same[0]["value"]))
    if desired is None:
        lines.append(f"{focus} is already {parsed[0]} in each of those files.")
        lines.append("No line needs to change for that.")
        return lines
    lines.append(f"+ {focus} = {desired};")
    lines.append("The same change belongs in each of those files.")
    for item in same:
        remember(plan, item, desired)
    lines.extend(reason_lines(focus, desired, values, support))
    lines.extend(daemon_lines(local, focus, plan))
    lines.extend(build_lines(layout, plan))
    return lines


def missing_option(ctx, local, focus, support, layout=None, plan=None):
    if layout is None:
        layout = machine_layout(ctx)
    lines = [f"{focus} is not set in your files."]
    rename = next((hit.excerpt for hit in support if "was renamed to " + focus in hit.excerpt), "")
    if rename:
        lines.append(rename.split(";")[0] + ".")
    default = stated_default(focus, support)
    lines.extend(daemon_lines(local, focus, plan))
    added = False
    if default == "true" and wants_on(ctx):
        lines.append(f"{focus} defaults to true, so allowing it needs no extra line once the daemon is on.")
    elif default == "false" and wants_on(ctx):
        lines.append(f"+ {focus} = true;")
        lines.append("That default is false. The value follows the question.")
        remember_new(plan, focus, "true")
        added = True
    elif wants_on(ctx):
        lines.append(f"+ {focus} = true;")
        lines.append("No source stated this value. It is only the direction of the question.")
        remember_new(plan, focus, "true")
        added = True
    if added or any(line.startswith("+ ") for line in lines):
        lines.extend(build_lines(layout, plan))
    return lines
