"""`ainix packages`: list a channel's packages by group."""

import argparse
import sys

from ainix_catalog.catalog import (
    BRANCHES,
    CatalogError,
    cache_root,
    load_cached,
    refresh,
)
from ainix_catalog.groups import CATEGORY_ORDER


def format_summary(catalog):
    lines = [
        f"{catalog.branch}  {catalog.channel}",
        f"nixpkgs {catalog.revision}",
        f"pulled {catalog.fetched_at}",
        "",
    ]
    for name in CATEGORY_ORDER:
        count = catalog.counts.get(name, 0)
        if count:
            lines.append(f"  {name:<20} {count}")
    lines.append(f"  {'Total':<20} {len(catalog.packages)}")
    lines.append("")
    lines.append("Nothing was installed.")
    return "\n".join(lines)


def format_matches(catalog, category, query, limit=40):
    rows, total = catalog.select(category, query, limit)
    lines = []
    for package in rows:
        flags = []
        if package.unfree:
            flags.append("unfree")
        if package.broken:
            flags.append("broken")
        mark = f" ({', '.join(flags)})" if flags else ""
        description = package.description
        if len(description) > 90:
            description = description[:87] + "..."
        lines.append(
            f"{package.attr}  {package.version}  [{package.category}]  {description}{mark}"
        )
    if not lines:
        lines.append("No packages matched.")
    lines.append(f"Showing {len(rows)} of {total}.")
    if len(rows) == 1:
        lines.append(f"Install name: pkgs.{rows[0].attr}")
    lines.append("Nothing was installed.")
    return "\n".join(lines)


def missing_message(branch):
    return (
        f"No package list for {branch} yet.\n"
        "Pull the current channel with:\n"
        f"  ainix packages --branch {branch} --refresh\n"
        "That downloads the package list into the AINIX cache. "
        "It does not change the system channel and it does not install anything."
    )


def run(argv):
    parser = argparse.ArgumentParser(
        prog="ainix packages",
        description="List packages from the current NixOS stable or unstable channel.",
    )
    parser.add_argument("--branch", choices=BRANCHES, default="stable")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--force", action="store_true", help="Download again even when the revision matches.")
    parser.add_argument("--category", default="", help="Group name, such as Games or Network.")
    parser.add_argument("query", nargs="*")
    args = parser.parse_args(argv)
    query = " ".join(args.query).strip()
    root = cache_root()
    try:
        if args.refresh:
            catalog = refresh(args.branch, root, force=args.force, progress=print)
        else:
            catalog = load_cached(root, args.branch)
            if catalog is None:
                print(missing_message(args.branch))
                return
        if args.category or query:
            print(format_matches(catalog, args.category, query))
        else:
            print(format_summary(catalog))
    except CatalogError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
