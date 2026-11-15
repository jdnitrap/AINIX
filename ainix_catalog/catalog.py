"""Pull a NixOS channel package list and keep it in the AINIX cache.

The download is the channel's packages.json.br, which Hydra builds from
nixpkgs at that channel's git revision. It does not run nix-channel and it
does not change the running system.
"""

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from ainix_catalog.groups import CATEGORY_ORDER, categorize


GROUP_VERSION = 2
MAX_DOWNLOAD = 80_000_000
MAX_UNPACKED = 600_000_000
CHANNELS_NIX = "https://raw.githubusercontent.com/NixOS/infra/main/channels.nix"
BRANCHES = ("stable", "unstable")

# Saved row: attr, pname, version, description, homepage, category, broken, unfree
_ROW = 8


class CatalogError(Exception):
    pass


class Package:
    def __init__(self, attr, pname, version, description, homepage, category, broken, unfree):
        self.attr = attr
        self.pname = pname
        self.version = version
        self.description = description
        self.homepage = homepage
        self.category = category if category in CATEGORY_ORDER else "Other"
        self.broken = bool(broken)
        self.unfree = bool(unfree)

    def as_row(self):
        return [
            self.attr,
            self.pname,
            self.version,
            self.description,
            self.homepage,
            self.category,
            1 if self.broken else 0,
            1 if self.unfree else 0,
        ]


class Catalog:
    def __init__(self, branch, channel, revision, fetched_at, packages, group_version=GROUP_VERSION):
        self.branch = branch
        self.channel = channel
        self.revision = revision
        self.fetched_at = fetched_at
        self.group_version = group_version
        self.packages = tuple(sorted(packages, key=lambda package: package.attr.casefold()))
        self.counts = {name: 0 for name in CATEGORY_ORDER}
        self.by_category = {name: [] for name in CATEGORY_ORDER}
        for package in self.packages:
            self.counts[package.category] = self.counts.get(package.category, 0) + 1
            self.by_category.setdefault(package.category, []).append(package)

    def select(self, category="", query="", limit=400):
        chosen = (category or "").strip()
        if chosen and chosen not in CATEGORY_ORDER:
            wanted = chosen.casefold()
            chosen = ""
            for name in CATEGORY_ORDER:
                if name.casefold() == wanted:
                    chosen = name
                    break
            if not chosen:
                raise CatalogError("Unknown group: " + category.strip())
        source = self.by_category.get(chosen, []) if chosen else self.packages
        needle = (query or "").casefold().strip()
        matched = []
        total = 0
        for package in source:
            if needle and not _matches(package, needle):
                continue
            total += 1
            if len(matched) < limit:
                matched.append(package)
        return matched, total


def _matches(package, needle):
    if needle in package.attr.casefold():
        return True
    if needle in package.pname.casefold():
        return True
    return needle in package.description.casefold()


def cache_root():
    override = os.environ.get("AINIX_CATALOG_CACHE", "").strip()
    if override:
        return Path(override)
    return Path.home() / ".cache" / "ainix" / "channels"


def catalog_path(root, branch):
    if branch not in BRANCHES:
        raise CatalogError("Pick stable or unstable.")
    return Path(root) / branch / "catalog.json"


def suggest_branch(version_text):
    """A .pre version is the unstable channel. A release number is stable."""
    if "pre" in (version_text or "").lower():
        return "unstable"
    return "stable"


def stable_channel_name(text):
    """The newest primary channel whose status is stable."""
    import re

    found = []
    pattern = re.compile(r'"(nixos-\d+\.\d+)"\s*=\s*\{(.*?)\n\s*\};', re.S)
    for name, body in pattern.findall(text or ""):
        variant = re.search(r'variant\s*=\s*"primary"', body)
        status = re.search(r'status\s*=\s*"stable"', body)
        if variant and status:
            major, minor = name.removeprefix("nixos-").split(".")
            found.append((int(major), int(minor), name))
    if not found:
        raise CatalogError("No stable NixOS channel is listed.")
    found.sort()
    return found[-1][2]


def channel_urls(channel):
    base = "https://channels.nixos.org/" + channel
    return {
        "revision": base + "/git-revision",
        "packages": base + "/packages.json.br",
    }


def _text(value, limit):
    if isinstance(value, str):
        text = " ".join(value.split())
    elif isinstance(value, list):
        text = ""
        for item in value:
            if isinstance(item, str) and item.strip():
                text = " ".join(item.split())
                break
    else:
        text = ""
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def iter_packages(document):
    if isinstance(document, dict) and isinstance(document.get("packages"), dict):
        raw = document["packages"]
    elif isinstance(document, dict):
        raw = document
    else:
        raise CatalogError("The package list has no packages.")
    for attr, item in raw.items():
        if attr in ("packages", "version") and not isinstance(item, dict):
            continue
        if not isinstance(item, dict):
            continue
        name = str(attr).strip()
        if not name or len(name) > 200:
            continue
        meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
        description = _text(meta.get("description"), 400)
        homepage = _text(meta.get("homepage"), 180)
        position = meta.get("position") or ""
        main = meta.get("mainProgram") or ""
        package = Package(
            attr=name,
            pname=_text(item.get("pname") or name, 120),
            version=_text(item.get("version"), 80),
            description=description,
            homepage=homepage,
            category=categorize(position, name, item.get("pname") or "", description, main),
            broken=meta.get("broken") is True,
            unfree=meta.get("unfree") is True,
        )
        yield package


def decode_index(raw):
    if not isinstance(raw, (bytes, bytearray)):
        raise CatalogError("The package list was empty.")
    body = bytes(raw)
    stripped = body.lstrip()
    if not stripped.startswith(b"{") and not stripped.startswith(b"["):
        try:
            import brotli
        except ImportError as exc:
            raise CatalogError(
                "The package list is compressed and brotli is not available. "
                "Start AINIX from its nix-shell."
            ) from exc
        try:
            body = brotli.decompress(body)
        except Exception as exc:
            raise CatalogError("The package list could not be decompressed.") from exc
    if len(body) > MAX_UNPACKED:
        raise CatalogError("The package list is unexpectedly large.")
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise CatalogError("The package list was not valid JSON.") from exc


def _payload(catalog):
    return {
        "group_version": catalog.group_version,
        "branch": catalog.branch,
        "channel": catalog.channel,
        "revision": catalog.revision,
        "fetched_at": catalog.fetched_at,
        "packages": [package.as_row() for package in catalog.packages],
    }


def save_catalog(catalog, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(_payload(catalog), handle, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def load_catalog(path):
    path = Path(path)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    rows = data.get("packages")
    if not isinstance(rows, list):
        return None
    packages = []
    for row in rows:
        if not isinstance(row, list) or len(row) < _ROW:
            continue
        packages.append(
            Package(
                str(row[0]),
                str(row[1]),
                str(row[2]),
                str(row[3]),
                str(row[4]),
                str(row[5]),
                bool(row[6]),
                bool(row[7]),
            )
        )
    return Catalog(
        branch=str(data.get("branch") or ""),
        channel=str(data.get("channel") or ""),
        revision=str(data.get("revision") or ""),
        fetched_at=str(data.get("fetched_at") or ""),
        packages=packages,
        group_version=int(data.get("group_version") or 0),
    )


def load_cached(root, branch):
    return load_catalog(catalog_path(root, branch))


def url_bytes(url, limit=MAX_DOWNLOAD):
    request = urllib.request.Request(url, headers={"User-Agent": "ainix"})
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            chunks = []
            total = 0
            while True:
                block = response.read(256 * 1024)
                if not block:
                    break
                total += len(block)
                if total > limit:
                    raise CatalogError(f"Refusing {url}: it is larger than {limit} bytes.")
                chunks.append(block)
    except CatalogError:
        raise
    except urllib.error.HTTPError as exc:
        raise CatalogError(f"Could not download {url} ({exc.code}).") from exc
    except urllib.error.URLError as exc:
        raise CatalogError(f"Could not download {url} ({exc.reason}).") from exc
    return b"".join(chunks)


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def refresh(branch, root, opener=None, force=False, progress=None):
    if branch not in BRANCHES:
        raise CatalogError("Pick stable or unstable.")
    opener = opener or url_bytes
    root = Path(root)

    def tell(message):
        if progress is not None:
            progress(message)

    if branch == "unstable":
        channel = "nixos-unstable"
    else:
        tell("Looking up the current stable channel…")
        channel = stable_channel_name(opener(CHANNELS_NIX).decode("utf-8", "replace"))
    urls = channel_urls(channel)
    tell(f"Checking {channel}…")
    revision = opener(urls["revision"]).decode("utf-8", "replace").strip()
    if not revision or len(revision) > 80 or any(char.isspace() for char in revision):
        raise CatalogError("The channel revision was not a single commit.")
    path = catalog_path(root, branch)
    cached = load_catalog(path)
    if (
        not force
        and cached is not None
        and cached.revision == revision
        and cached.channel == channel
        and cached.group_version == GROUP_VERSION
    ):
        tell(f"Already have {channel} at {revision[:12]}.")
        return cached
    tell(f"Downloading the {channel} package list…")
    raw = opener(urls["packages"])
    if len(raw) > MAX_DOWNLOAD:
        raise CatalogError("The package list download is unexpectedly large.")
    tell("Grouping packages…")
    document = decode_index(raw)
    packages = tuple(iter_packages(document))
    if not packages:
        raise CatalogError("The package list was empty.")
    catalog = Catalog(
        branch=branch,
        channel=channel,
        revision=revision,
        fetched_at=_now(),
        packages=packages,
    )
    save_catalog(catalog, path)
    tell(f"Saved {len(packages)} packages from {channel}.")
    return catalog
