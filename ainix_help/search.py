"""Ask every useful source. A source that fails is reported, not skipped silently."""

import json
import os
import re
import subprocess
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
from pathlib import Path

from ainix_help.context import run


UA = "ainix/0.12 (nix-shell; search helper)"


class Hit:
    def __init__(self, source, title, url, excerpt):
        self.source = source
        self.title = title.strip() or source
        self.url = url.strip()
        self.excerpt = clean(excerpt)[:700]


def clean(text):
    text = unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def fetch(url, data=None, timeout=16, headers=None):
    head = {"User-Agent": UA, "Accept": "application/json,text/html"}
    if headers:
        head.update(headers)
    body = data.encode() if isinstance(data, str) else data
    req = urllib.request.Request(url, data=body, headers=head)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read(800_000)
    return raw.decode("utf-8", "replace")


# The word a person types is often not the NixOS option name.
# "ssh" is services.openssh / sshd. The release stays out of the query:
# a version number pulls migration threads ahead of the option itself.
ALIASES = {
    "ssh": ["openssh", "sshd"],
    "sshd": ["openssh"],
    "openssh": ["sshd"],
    "firewall": ["firewall"],
    "printing": ["cups"],
    "cups": ["printing"],
    "sound": ["pipewire"],
    "vpn": ["wireguard", "openvpn"],
}


GENERIC = {
    "enable", "disable", "install", "config", "module", "system", "package",
    "option", "service", "services", "true", "false", "build", "error",
    "failed", "help", "start", "stop", "turn",
}


def distinctive(terms):
    picked = [term for term in terms if term not in GENERIC and len(term) >= 3]
    return picked or [term for term in terms if len(term) >= 3]


def primary_words(ctx):
    words = []
    for term in distinctive(ctx.terms):
        for alias in ALIASES.get(term, []):
            if alias not in words:
                words.append(alias)
    return words


def search_words(ctx):
    words = []
    for term in distinctive(ctx.terms):
        if term not in words:
            words.append(term)
        for alias in ALIASES.get(term, []):
            if alias not in words:
                words.append(alias)
    return words or distinctive(ctx.terms)


def query_text(ctx):
    # One subject word. The wiki ANDs every word, so "openssh sshd" matches nothing.
    # "openssh" stays "openssh". Only a short word such as "ssh" is replaced by its alias.
    for term in distinctive(ctx.terms):
        if term in ALIASES and term != "ssh":
            return "nixos " + term
    words = primary_words(ctx) or distinctive(ctx.terms)
    return " ".join(["nixos"] + words[:1]) or ctx.question


SERVICE_WORDS = {
    "ssh", "openssh", "sshd", "bluetooth", "blueman", "printing", "cups",
    "pulseaudio", "pipewire", "firewall", "sound", "vpn", "wireguard", "openvpn",
}


def setting_terms(ctx):
    """Words that name a setting, after the service name is set aside."""
    return [term for term in distinctive(ctx.terms) if term not in SERVICE_WORDS]


def tokens(text):
    out = []
    for word in re.findall(r"[A-Za-z0-9]+", text or ""):
        pieces = re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+", word)
        if len(pieces) > 1:
            out.extend(piece.lower() for piece in pieces)
        out.append(word.lower())
    return out


def word_hit(text, words):
    """Match a whole token. A short word also matches sshd, and it does not match endlessh."""
    parts = tokens(text)
    have = set(parts)
    for word in words:
        if word in have:
            return True
        if any(part.startswith(word) and 0 < len(part) - len(word) <= 2 for part in parts):
            return True
    return False


def line_matches(line, terms):
    return word_hit(line, distinctive(terms))


def plain_bool(value):
    """The bool inside a plain value or a mkForce / mkDefault / mkIf wrapper."""
    text = (value or "").strip().rstrip(";").strip()
    if text in {"true", "false", "0", "1"}:
        return text
    if re.search(r"\bmk(Force|Default|If|Override|VMOverride|ImageMediaOverride)\b", text):
        match = re.search(r"\b(true|false|0|1)\s*$", text)
        if match:
            return match.group(1)
    return ""


def line_indent(line):
    width = 0
    for char in line:
        if char == " ":
            width += 1
        elif char == "\t":
            width += 8
        else:
            break
    return width


def opens_block(rest):
    if rest.startswith("{") or rest == "{":
        return True
    # lib.mkMerge [ { enable = ...; } ] still belongs to the option above it.
    if re.search(r"\bmk(Merge|If)\b", rest) and ("{" in rest or rest.rstrip().endswith("[")):
        return True
    return False


ASSIGN_ROOTS = {
    "services", "programs", "hardware", "networking", "security", "boot",
    "nix", "environment", "systemd", "users", "virtualisation",
}


def nix_assignments(lines):
    """Dotted options, including enable inside an attribute set."""
    stack = []
    found = []
    for number, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = line_indent(line)
        while stack and indent <= stack[-1][0]:
            stack.pop()
        match = re.match(r"([A-Za-z_][A-Za-z0-9_-]*(?:\.[A-Za-z0-9_-]+)*)\s*=\s*([^;#]*)", stripped)
        if not match:
            continue
        name, rest = match.group(1), match.group(2).strip()
        # Each stack entry is already the full path of that block.
        prefix = stack[-1][1] if stack else ""
        root = name.split(".", 1)[0]
        full = name if root in ASSIGN_ROOTS or not prefix else prefix + "." + name
        if opens_block(rest):
            stack.append((indent, full))
            continue
        if not full.split(".", 1)[0] in ASSIGN_ROOTS:
            continue
        if not rest or rest.startswith("''") or len(rest) > 120:
            continue
        found.append((number, full, rest.rstrip(), line.strip()))
    return found


def excluded_host_labels(root):
    """Host names in this tree that are not the machine the question is about.

    A shared module has none of those names in its path, so it stays.
    """
    from core.nixos_layout import _host_names, detect

    layout = detect(root)
    selected = (layout.flake_attr or layout.host_name or "").lower()
    if not selected:
        return set()
    labels = {name.lower() for name in layout.flake_names}
    labels.update(name.lower() for name in _host_names(Path(root)))
    labels.discard(selected)
    return labels


def is_other_host(path, root, labels):
    if not labels:
        return False
    parts = set()
    for part in Path(os.path.relpath(path, root)).parts:
        low = part.lower()
        parts.add(low)
        parts.add(os.path.splitext(low)[0])
    return bool(parts & labels)


def keep_related_enable(item, matched):
    """PipeWire lines in the same file explain a PulseAudio question."""
    if item[1] not in {"services.pipewire.enable", "services.pipewire.pulse.enable"}:
        return False
    if plain_bool(item[2]) not in {"true", "false", "0", "1"}:
        return False
    return any("pulseaudio" in tokens(one[1]) for one in matched)


def local_files(ctx):
    hits = []
    if not ctx.config or not os.path.isdir(ctx.config):
        return hits, "local files: no NixOS configuration directory"
    words = search_words(ctx)
    others = excluded_host_labels(ctx.config)
    found = []
    for dirpath, dirs, files in os.walk(ctx.config):
        dirs[:] = [name for name in dirs if name not in {".git", "result"}]
        for name in files:
            if not name.endswith(".nix"):
                continue
            path = os.path.join(dirpath, name)
            if is_other_host(path, ctx.config, others):
                continue
            try:
                lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
            except OSError:
                continue
            assignments = nix_assignments(lines)
            matched = [
                item for item in assignments
                if word_hit(item[1], words) or word_hit(item[3], words)
            ]
            if not matched:
                continue
            seen = {item[0] for item in matched}
            for item in assignments:
                if item[0] in seen:
                    continue
                if keep_related_enable(item, matched):
                    matched.append(item)
            base = os.path.splitext(name)[0]
            named = 10 if word_hit(base, words) else 0
            specific = bool(setting_terms(ctx))
            for number, full, value, _raw in matched:
                score = named
                option_matches = word_hit(full, words)
                if option_matches:
                    score += 6
                if full.endswith(".enable") and option_matches:
                    score += 1
                    if (ctx.wants_enable or ctx.wants_disable) and not specific:
                        score += 20
                found.append((score, path, number, f"{full} = {value};"))
    found.sort(key=lambda item: (-item[0], item[1], item[2]))
    for _score, path, number, excerpt in found[:12]:
        hits.append(Hit(
            "your files",
            f"{os.path.relpath(path, ctx.config)}:{number}",
            path,
            excerpt,
        ))
    if hits:
        return hits, f"your files: {len(hits)} lines in {ctx.config}"
    return hits, f"your files: nothing in {ctx.config} matched"


def nix_help(ctx):
    text = run(["nix", "help"], timeout=12)
    if not text.strip():
        return [], "nix help: no output"
    commands = re.findall(r"^ {2,}([a-z][\w-]*)\s{2,}", text, re.M)
    wanted = [cmd for cmd in commands if cmd in ctx.terms]
    excerpt = "\n".join(line for line in text.splitlines() if line.strip())[:700]
    hits = [Hit("nix help", "nix help", "man:nix", excerpt)]
    for cmd in wanted[:2]:
        detail = run(["nix", "help", cmd], timeout=12)
        if detail.strip():
            hits.append(Hit("nix help", f"nix help {cmd}", f"man:nix-{cmd}", detail[:700]))
    rebuild = run(["nixos-rebuild", "--help"], timeout=12)
    if rebuild.strip() and any(word in ctx.question.lower() for word in ("rebuild", "switch", "boot", "generation")):
        hits.append(Hit("nixos-rebuild help", "nixos-rebuild --help", "man:nixos-rebuild", rebuild[:700]))
    return hits, f"nix help: {len(hits)} pages"


def usable_option_text(text):
    body = (text or "").strip()
    if not body or "while evaluating" in body or body.startswith("error:"):
        return ""
    return body


def nixos_option(name):
    text = usable_option_text(run(["nixos-option", name], timeout=20))
    if not text:
        return None
    return Hit("nixos-option", name, f"https://search.nixos.org/options?channel={''}", text[:700])


def option_lookup(ctx, names, release):
    hits = []
    for name in names[:3]:
        hit = nixos_option(name)
        if hit:
            hit.url = f"https://search.nixos.org/options?channel={release}&query={urllib.parse.quote(name)}"
            hits.append(hit)
    note = f"nixos-option: {len(hits)} looked up" if names else "nixos-option: no option name to look up yet"
    return hits, note


def wiki(ctx):
    q = urllib.parse.quote(query_text(ctx))
    url = f"https://wiki.nixos.org/w/rest.php/v1/search/page?q={q}&limit=5"
    payload = json.loads(fetch(url))
    hits = []
    for page in payload.get("pages", [])[:5]:
        key = page.get("key") or ""
        hits.append(Hit(
            "wiki",
            page.get("title") or key,
            "https://wiki.nixos.org/wiki/" + urllib.parse.quote(key.replace(" ", "_")),
            page.get("excerpt") or "",
        ))
    if hits:
        try:
            detail = wiki_block(fetch(hits[0].url + "?action=raw").splitlines(), ctx)
        except Exception:
            detail = ""
        if detail:
            hits[0].excerpt = detail
    return hits, f"wiki: {len(hits)} pages"


def wiki_block(lines, ctx):
    """Join the enable line inside a matching attrset. Keep the other keys as a caveat."""
    watch = {
        "openFirewall", "PasswordAuthentication", "KbdInteractiveAuthentication",
        "PermitRootLogin", "AllowUsers", "ports",
    }
    words = search_words(ctx)
    for index, line in enumerate(lines):
        match = re.search(r"\b((?:services|programs)\.[A-Za-z0-9_-]+)\s*=\s*\{", line)
        if not match or not word_hit(match.group(1), words):
            continue
        owner = match.group(1)
        depth = line.count("{") - line.count("}")
        enable = None
        siblings = []
        for follow in lines[index + 1:index + 40]:
            assignment = re.match(r"\s*([A-Za-z0-9_]+)\s*=\s*([^;]+);", follow)
            if assignment and assignment.group(1) in watch and assignment.group(1) not in siblings:
                siblings.append(assignment.group(1))
            enable_match = re.match(r"\s*enable\s*=\s*(true|false)\s*;", follow)
            if enable_match and enable is None:
                enable = enable_match.group(1)
            depth += follow.count("{") - follow.count("}")
            if depth <= 0:
                break
        if not enable:
            continue
        text = f"{owner}.enable = {enable};"
        if siblings:
            text += " The same example also sets " + ", ".join(siblings) + "."
            text += " Those settings are separate from enabling the service."
        return text
    return ""


def discourse(ctx):
    q = urllib.parse.quote(query_text(ctx))
    payload = json.loads(fetch(f"https://discourse.nixos.org/search.json?q={q}"))
    topics = {item.get("id"): item for item in payload.get("topics", [])}
    hits = []
    for post in payload.get("posts", [])[:5]:
        topic = topics.get(post.get("topic_id"), {})
        slug = topic.get("slug") or "t"
        number = post.get("topic_id")
        title = topic.get("title") or clean(post.get("blurb") or "")[:80]
        hits.append(Hit(
            "discourse",
            title,
            f"https://discourse.nixos.org/t/{slug}/{number}",
            post.get("blurb") or "",
        ))
    return hits, f"discourse: {len(hits)} posts"


def github(ctx, repo, source):
    words = primary_words(ctx) or distinctive(ctx.terms)
    q = urllib.parse.quote(f"repo:{repo} " + " ".join(words[:1]))
    url = f"https://api.github.com/search/issues?q={q}&per_page=4"
    payload = json.loads(fetch(url, headers={"Accept": "application/vnd.github+json"}))
    hits = []
    for item in payload.get("items", [])[:4]:
        hits.append(Hit(
            source,
            item.get("title") or repo,
            item.get("html_url") or "",
            item.get("body") or "",
        ))
    return hits, f"{source}: {len(hits)} issues"


def file_rank(path, ctx):
    name = os.path.splitext(os.path.basename(path))[0]
    name_tokens = set(tokens(name))
    score = 0
    for term in distinctive(ctx.terms):
        aliases = ALIASES.get(term, [])
        if term in name_tokens and not aliases:
            score += 8
        elif term in name_tokens:
            score += 3
        for alias in aliases:
            if alias in name_tokens:
                score += 12
    if "/modules/" in path.replace("\\", "/"):
        score += 2
    if "/tests/" in path.replace("\\", "/"):
        score -= 8
    return score


def enable_definitions(lines, words):
    """Read an option owner and the enable block under it as one cited fact."""
    owner = None
    found = []
    for index, line in enumerate(lines):
        match = re.search(r"\b((?:services|programs)\.[A-Za-z0-9_-]+)\s*=\s*\{", line)
        if match:
            owner = match.group(1)
        if not owner or not word_hit(owner, words):
            continue
        if not re.match(r"\s*enable\s*=\s*(?:lib\.)?mk(?:Option|EnableOption)\b", line):
            continue
        block = "\n".join(lines[index:index + 12])
        bits = [f"{owner}.enable — lib.mkOption"]
        type_match = re.search(r"type\s*=\s*lib\.types\.(\w+)", block)
        default_match = re.search(r"default\s*=\s*([^;]+);", block)
        if type_match:
            bits.append("type = " + type_match.group(1))
        if default_match:
            bits.append("default = " + default_match.group(1).strip())
        found.append((index + 1, "; ".join(bits)))
        if len(found) >= 2:
            break
    return found


def term_cover(text, ctx):
    wanted = setting_terms(ctx) or distinctive(ctx.terms)
    have = tokens(text)
    count = 0
    for term in wanted:
        if word_hit(" ".join(have), [term]) or term in have:
            count += 1
    return count


def renamed_facts(lines, ctx):
    """A renamed option that matches the setting the question names."""
    text = "\n".join(lines)
    scored = []
    for match in re.finditer(r"mkRenamedOptionModule\s*\[([^\]]+)\]\s*\[([^\]]+)\]", text):
        old = ".".join(re.findall(r'"([^"]+)"', match.group(1)))
        new = ".".join(re.findall(r'"([^"]+)"', match.group(2)))
        if not old or not new or old.endswith(".enable"):
            continue
        cover = term_cover(old + " " + new, ctx)
        if cover == 0:
            continue
        bits = [f"{old} was renamed to {new}"]
        last = new.split(".")[-1]
        block = re.search(re.escape(last) + r"\s*=\s*(?:lib\.)?mkOption\s*\{([^}]*)\}", text)
        if block:
            if re.search(r"types\.bool", block.group(1)):
                bits.append("type = bool")
            default_match = re.search(r"default\s*=\s*([^;]+);", block.group(1))
            if default_match:
                bits.append("default = " + default_match.group(1).strip())
        scored.append((cover, match.start(), "; ".join(bits)))
    if not scored:
        return []
    best = max(item[0] for item in scored)
    return [(text[:start].count("\n") + 1, excerpt) for cover, start, excerpt in scored if cover == best]


def nixpkgs_roots(ctx):
    roots = []
    for root in ctx.nixpkgs:
        for candidate in (root, os.path.join(root, "nixos")):
            if os.path.isdir(os.path.join(candidate, "modules")) or os.path.isdir(os.path.join(candidate, "nixos", "modules")):
                roots.append(candidate)
    seen = []
    for root in roots:
        real = os.path.realpath(root)
        if real not in seen:
            seen.append(real)
    return seen


def nixpkgs_source(ctx):
    words = search_words(ctx)
    if not words:
        return [], "nixpkgs: no search words"
    ranked = []
    roots = nixpkgs_roots(ctx)
    for root in roots:
        module_root = root if os.path.isdir(os.path.join(root, "modules")) else os.path.join(root, "nixos")
        for dirpath, dirs, files in os.walk(module_root):
            dirs[:] = [name for name in dirs if name not in {".git", "result", "doc", "tests"}]
            if dirpath.count(os.sep) - module_root.count(os.sep) > 6:
                dirs.clear()
                continue
            for name in files:
                if not name.endswith(".nix"):
                    continue
                path = os.path.join(dirpath, name)
                rank = file_rank(path, ctx)
                if rank <= 0:
                    continue
                ranked.append((rank, root, path))
    best_file = {}
    for rank, root, path in ranked:
        real = os.path.realpath(path)
        rel = os.path.relpath(path, root)
        current = best_file.get(real)
        if current is None:
            best_file[real] = (rank, root, path, rel)
            continue
        current_rel = current[3]
        better = rel.startswith("nixos/") and not current_rel.startswith("nixos/")
        if better or (rank > current[0] and rel.startswith("nixos/") == current_rel.startswith("nixos/")):
            best_file[real] = (rank, root, path, rel)
    ranked = sorted(best_file.values(), key=lambda item: (-item[0], item[2]))
    hits = []
    rev = ctx.revision or "local"
    if ranked:
        best = ranked[0][0]
        chosen = [item for item in ranked if item[0] >= best - 2][:2]
        for _rank, root, path, rel in chosen:
            try:
                lines = open(path, encoding="utf-8", errors="replace").read(200_000).splitlines()
            except OSError:
                continue
            url = f"https://github.com/NixOS/nixpkgs/blob/{rev}/{rel}"
            facts = renamed_facts(lines, ctx)
            for number, excerpt in facts:
                hits.append(Hit("nixpkgs", f"{rel}:{number}", url, excerpt))
            if not facts:
                for number, excerpt in enable_definitions(lines, words):
                    hits.append(Hit("nixpkgs", f"{rel}:{number}", url, excerpt))
            if not any(hit.url == url for hit in hits):
                for number, line in enumerate(lines, 1):
                    if word_hit(line, primary_words(ctx) or words):
                        hits.append(Hit("nixpkgs", f"{rel}:{number}", url, line.strip()))
                        break
    if hits:
        return hits, f"nixpkgs: {len(hits)} lines at revision {rev}"
    return [Hit(
        "nixpkgs",
        "NixOS/nixpkgs search",
        "https://github.com/NixOS/nixpkgs/search?q=" + urllib.parse.quote(" ".join(words[:4])) + "&type=code",
        f"No matching module in the local nixpkgs checkout. The revision from nixos-version is {rev}.",
    )], f"nixpkgs: local checkout had no match; GitHub search link for {rev}"


def duckduckgo(ctx, source, site=""):
    words = query_text(ctx)
    if site:
        words = f"{words} site:{site}"
    data = urllib.parse.urlencode({"q": words}).encode()
    html = fetch("https://html.duckduckgo.com/html/", data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    hits = []
    for match in re.finditer(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.I | re.S):
        href, title = match.group(1), clean(match.group(2))
        parsed = urllib.parse.urlparse(href)
        query = urllib.parse.parse_qs(parsed.query)
        if "uddg" in query:
            href = query["uddg"][0]
        if not href.startswith("http"):
            continue
        hits.append(Hit(source, title, href, title))
        if len(hits) >= 6:
            break
    kept = []
    for hit in hits:
        blob = f"{hit.title} {hit.url} {hit.excerpt}".lower()
        if "nix" in blob:
            kept.append(hit)
    return kept[:4], f"{source}: {len(kept)} results that mention nix ({len(hits)} before that filter)"


def hydra(ctx):
    low = ctx.question.lower()
    if not any(word in low for word in ("fail", "error", "build", "collision", "hydra")):
        return [], "hydra: not asked, the question is not a build failure"
    q = urllib.parse.quote(" ".join(ctx.terms[:4]))
    html = fetch(f"https://hydra.nixos.org/search?query={q}")
    hits = []
    for match in re.finditer(r'href="(/job/[^"]+)"[^>]*>([^<]+)', html):
        path, title = match.group(1), clean(match.group(2))
        hits.append(Hit("hydra", title, "https://hydra.nixos.org" + path, title))
        if len(hits) >= 3:
            break
    return hits, f"hydra: {len(hits)} jobs"


def release_notes(ctx):
    if not ctx.release:
        return [], "release notes: version unknown"
    name = "rl-" + ctx.release.replace(".", "") + ".md"
    found = []
    for root in ctx.nixpkgs:
        for relative in (
            os.path.join("nixos", "doc", "manual", "release-notes", name),
            os.path.join("doc", "manual", "release-notes", name),
        ):
            path = os.path.join(root, relative)
            if os.path.isfile(path):
                found.append(path)
    hits = []
    for path in found[:1]:
        lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
        for number, line in enumerate(lines, 1):
            if not word_hit(line, search_words(ctx)):
                continue
            hits.append(Hit(
                    "release notes",
                    f"{ctx.release} release notes:{number}",
                    f"https://nixos.org/manual/nixos/stable/release-notes#sec-release-{ctx.release}",
                    line.strip(),
                ))
            if len(hits) >= 4:
                break
    return hits, f"release notes: {len(hits)} lines for {ctx.release}"


def home_manager(ctx):
    if not ctx.home_manager:
        return [], "home-manager: not asked, the configuration does not import it"
    return github(ctx, "nix-community/home-manager", "home-manager")


def safe(label, func):
    try:
        hits, note = func()
        return hits, note
    except Exception as exc:
        return [], f"{label}: failed ({exc.__class__.__name__}: {exc})"


def first_wave(ctx):
    jobs = {
        "your files": lambda: local_files(ctx),
        "nix help": lambda: nix_help(ctx),
        "wiki": lambda: wiki(ctx),
        "discourse": lambda: discourse(ctx),
        "github nixpkgs": lambda: github(ctx, "NixOS/nixpkgs", "github nixpkgs"),
        "github nix": lambda: github(ctx, "NixOS/nix", "github nix"),
        "nixpkgs": lambda: nixpkgs_source(ctx),
        "duckduckgo": lambda: duckduckgo(ctx, "duckduckgo"),
        "release notes": lambda: release_notes(ctx),
        "hydra": lambda: hydra(ctx),
        "home-manager": lambda: home_manager(ctx),
    }
    if ctx.kind == "learn":
        jobs["youtube"] = lambda: duckduckgo(ctx, "youtube", "youtube.com")
    else:
        jobs["youtube"] = lambda: ([], "youtube: not asked, this is a failure question")
    hits = []
    notes = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(safe, name, func): name for name, func in jobs.items()}
        for future in as_completed(futures):
            found, note = future.result()
            hits.extend(found)
            notes.append(note)
    return hits, notes


OPTION = re.compile(r"\b([a-zA-Z][A-Za-z0-9]*(\.[A-Za-z0-9_-]+){1,8})\b")
ROOTS = {
    "services", "programs", "environment", "boot", "networking", "hardware",
    "security", "users", "systemd", "virtualisation", "nix", "documentation",
    "sound", "fonts", "i18n", "power", "time", "console", "age", "sops",
}


def option_names(hits, ctx):
    """One strong mention in the user's files beats a repeated name in an unrelated issue."""
    primary = set(primary_words(ctx))
    words = search_words(ctx)
    scores = {}
    for hit in hits:
        base = {
            "your files": 20,
            "nixpkgs": 12,
            "wiki": 8,
            "release notes": 8,
            "nixos-option": 8,
        }.get(hit.source, 2)
        for match in OPTION.finditer(hit.title + "\n" + hit.excerpt):
            name = match.group(1).rstrip(".")
            if name.split(".", 1)[0] not in ROOTS:
                continue
            weight = base
            if primary and set(tokens(name)) & primary:
                weight += 6
            elif word_hit(name, words):
                weight += 2
            else:
                weight = 1
            if (ctx.wants_enable or ctx.wants_disable) and name.endswith(".enable"):
                weight += 5
            weight += 4 * sum(1 for term in distinctive(ctx.terms) if term in set(tokens(name)))
            scores[name] = max(scores.get(name, 0), weight)
    ranked = sorted(scores, key=lambda name: (-scores[name], -name.count("."), name))
    if primary and (ctx.wants_enable or ctx.wants_disable):
        preferred = [name for name in ranked if set(tokens(name)) & primary]
        if preferred:
            ranked = preferred
    specific = setting_terms(ctx)
    if specific:
        named = [name for name in ranked if any(term in tokens(name) for term in specific)]
        if named:
            ranked = named
    elif ctx.wants_enable or ctx.wants_disable:
        enable_names = [name for name in ranked if name.endswith(".enable")]
        if enable_names:
            ranked = enable_names
    return ranked[:2]


def search(ctx):
    hits, notes = first_wave(ctx)
    names = option_names(hits, ctx)
    extra, note = safe("nixos-option", lambda: option_lookup(ctx, names, ctx.release or "unstable"))
    hits.extend(extra)
    notes.append(note)
    return hits, notes, names
