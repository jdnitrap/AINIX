#!/usr/bin/env python3
"""
AINIX: AI-Native NixOS Integration
"""

import sys
import argparse
from pathlib import Path

VERSION = "0.2.2"

sys.path.insert(0, str(Path(__file__).parent))

from core.router import QueryRouter, QueryType
from control.executor import SafeExecutor, ExecutionMode
from help.knowledge_base import HelpKnowledgeBase


class AINIX:
    def __init__(self, config_path=None, quiet=False, raw=False):
        self.router = QueryRouter()
        self.executor = SafeExecutor(config_path)
        self.knowledge = HelpKnowledgeBase()
        self.quiet = quiet
        self.raw = raw

    def handle_help_query(self, query: str, subject: str = None):
        if not self.quiet and not self.raw:
            print("\n📚 Help")
            print("-" * 40)

        search_term = subject or query
        results = self.knowledge.search(search_term)

        if results and not self.raw:
            top = results[0]
            print(f"\n{top.topic}\n")
            print(top.content.strip())
            if top.examples:
                print("\nExamples:")
                for ex in top.examples:
                    print(f"  {ex}")
            if len(results) > 1:
                others = ", ".join(e.topic for e in results[1:])
                print(f"\nAlso related: {others}")

        # Always consult Nix docs
        docs = self.knowledge.lookup_docs(search_term)
        if docs and "No matching" not in docs and "not on PATH" not in docs:
            if not self.raw:
                print("\n--- Nix docs ---")
            print(docs)
        elif not results:
            print(f"No local knowledge for '{search_term}'.")
            print(docs or f"Try: nix search nixpkgs {search_term}")

    def handle_control_query(self, query: str, subject: str = None,
                             explain: bool = False, dry_run: bool = False,
                             execute: bool = False, yes: bool = False):
        if explain:
            print(self.knowledge.explain_command(query.split()[0] if query.split() else ""))
            return

        if not self.quiet and not self.raw:
            print("\n⚙️  Control")
            print("-" * 40)

        if dry_run:
            mode = ExecutionMode.DRY_RUN
        elif execute:
            mode = ExecutionMode.EXECUTE
        else:
            mode = ExecutionMode.PREVIEW

        if mode == ExecutionMode.EXECUTE and not yes:
            print(f"About to run: {query}")
            ans = input("Run this? [y/N] ").strip().lower()
            if ans not in ("y", "yes"):
                print("Cancelled.")
                return

        result = self.executor.execute_safe(query, mode=mode)

        if result.success:
            print(result.stdout)
            if mode == ExecutionMode.PREVIEW and not self.raw:
                print("\nTo execute: ainix --execute --yes <command>")
        else:
            print(result.stderr or "Failed")

    def _is_bare_package(self, query: str) -> bool:
        parts = query.split()
        if len(parts) != 1:
            return False
        word = parts[0].lower()
        if word in QueryRouter.CONTROL_KEYWORDS or word in QueryRouter.HELP_KEYWORDS:
            return False
        if word.startswith("-") or "." in word:
            return False
        return True

    def handle_query(self, query: str, args: argparse.Namespace):
        if args.explain:
            query_type = QueryType.EXPLAIN
            subject = None
        else:
            query_type, subject = self.router.classify(query)

        if self._is_bare_package(query) and query_type != QueryType.EXPLAIN:
            query = f"install {query}"
            query_type = QueryType.CONTROL

        if not self.quiet and not self.raw:
            print(f"\nAINIX · {query_type.value}")

        if query_type == QueryType.HELP:
            self.handle_help_query(query, subject)
        elif query_type == QueryType.EXPLAIN:
            self.handle_control_query(query, subject, explain=True)
        elif query_type == QueryType.CONTROL:
            self.handle_control_query(
                query, subject, dry_run=args.dry_run,
                execute=args.execute, yes=getattr(args, "yes", False)
            )
        else:
            self.handle_help_query(query, subject)

    def interactive(self):
        print(f"AINIX {VERSION} — empty line or 'quit' to exit")
        print("Preview never changes the system.\n")
        while True:
            try:
                line = input("ainix> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line or line.lower() in ("quit", "exit"):
                break
            if line.lower() == "examples":
                self._examples()
                continue
            if line.lower() == "list":
                print("\n".join(self.knowledge.list_topics()))
                continue
            class A: pass
            a = A()
            a.explain = False
            a.dry_run = False
            a.execute = False
            a.yes = False
            self.handle_query(line, a)
            print()

    def _examples(self):
        print("""
Examples:
  ainix "How do I install a package?"
  ainix install firefox
  ainix firefox
  ainix "services.openssh.enable"
  ainix --explain nixos-rebuild
  ainix --list
  ainix            (interactive)
""".strip())


def main():
    parser = argparse.ArgumentParser(description="AINIX: local NixOS assistant")
    parser.add_argument("query", nargs="*", help="Query or command")
    parser.add_argument("--explain", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", "-x", action="store_true")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirm on execute")
    parser.add_argument("--raw", action="store_true", help="Answer only")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--list", action="store_true", help="List knowledge topics")
    parser.add_argument("--examples", action="store_true")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--config", metavar="PATH")

    args = parser.parse_args()

    if args.version:
        print(VERSION)
        return

    ainix = AINIX(config_path=args.config, quiet=args.quiet, raw=args.raw)

    if args.examples:
        ainix._examples()
        return

    if args.list:
        print("\n".join(ainix.knowledge.list_topics()))
        return

    if not args.query:
        ainix.interactive()
        return

    query = " ".join(args.query)
    ainix.handle_query(query, args)


if __name__ == "__main__":
    main()
