#!/usr/bin/env python3
"""
AINIX: AI-Native NixOS Integration
"""

import sys
import argparse
import json
import shutil
from pathlib import Path
from datetime import datetime

VERSION = "0.6.0"

sys.path.insert(0, str(Path(__file__).parent))

from core.router import QueryRouter, QueryType
from control.executor import SafeExecutor, ExecutionMode
from help.knowledge_base import HelpKnowledgeBase


def load_config(config_path=None):
    paths = []
    if config_path:
        paths.append(Path(config_path))
    paths.append(Path.home() / ".config" / "ainix" / "config.json")
    for p in paths:
        if p.exists():
            try:
                return json.loads(p.read_text())
            except (json.JSONDecodeError, OSError):
                continue
    return {}


class AINIX:
    def __init__(self, config_path=None, quiet=False, raw=False, model=None, model_first=None):
        self.router = QueryRouter()
        self.executor = SafeExecutor(config_path)
        cfg = load_config(config_path)
        chosen = model or cfg.get("model")
        if model_first is None:
            self.model_first = bool(cfg.get("model_first", False))
        else:
            self.model_first = model_first
        self.knowledge = HelpKnowledgeBase(model=chosen)
        self.quiet = quiet
        self.raw = raw
        self.data_dir = Path.home() / ".local" / "share" / "ainix"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = self.data_dir / "history.log"
        self.notes_file = self.data_dir / "notes.txt"
        self.cache_dir = self.data_dir / "cache"

    def show_start(self):
        style = self.detect_style()
        rebuild = "sudo nixos-rebuild switch --flake .#hostname" if style == "flakes" else "sudo nixos-rebuild switch"
        print(f"""AINIX start — first steps on NixOS

Your system looks like: {style}

1. Install a package (permanent)
   Add to configuration.nix:
     environment.systemPackages = with pkgs; [ firefox ];
   Then:
     {rebuild}

   Temporary (this user only):
     nix profile add nixpkgs#firefox

2. Rebuild after any config change
   {rebuild}

3. If something breaks, roll back
   sudo nixos-rebuild switch --rollback
   Or pick an older generation at boot.

4. Ask AINIX next
   ainix "How do I enable ssh?"
   ainix install vim
   ainix help

Preview never changes the system. Nothing runs unless you pass --execute.
""")

    def show_help(self):
        model = self.knowledge.pick_model() or "none"
        mode = "model-first" if self.model_first else "docs-first"
        print(f"""AINIX {VERSION}
Mode:  {mode}
Model: {model}

New here?  ainix start

Or:
  ainix --model-first "question"
  ainix --docs-first "question"

Default is docs-first. Model is optional.
""")

    def uninstall(self):
        paths = [
            Path.home() / ".local" / "bin" / "ainix",
            Path.home() / ".local" / "share" / "ainix",
            Path.home() / ".local" / "share" / "man" / "man1" / "ainix.1",
        ]
        for p in paths:
            if p.is_file():
                p.unlink()
                print(f"removed {p}")
            elif p.is_dir():
                shutil.rmtree(p)
                print(f"removed {p}")
        print("Uninstalled.")

    def cache_clear(self):
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
            print("cleared cache")
        else:
            print("no cache")

    def _record(self, query, kind):
        entry = {"time": datetime.utcnow().isoformat() + "Z", "query": query, "kind": kind}
        with open(self.history_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def show_history(self, n=20):
        if not self.history_file.exists():
            print("No history yet.")
            return
        for line in self.history_file.read_text().strip().splitlines()[-n:]:
            try:
                e = json.loads(line)
                print(f"{e.get('time','')}  [{e.get('kind','')}]  {e.get('query','')}")
            except json.JSONDecodeError:
                continue

    def detect_style(self):
        if Path("/etc/nixos/flake.nix").exists() or Path("flake.nix").exists():
            return "flakes"
        return "channels"

    def add_note(self, text):
        with open(self.notes_file, "a") as f:
            f.write(text.strip() + "\n")
        print(f"Noted: {text.strip()}")

    def handle_help_query(self, query, subject=None):
        search_term = subject or query
        self._record(search_term, "help")
        if not self.raw:
            mode = "model-first" if self.model_first else "docs-first"
            print(f"[{mode}]")

        def show_model():
            out = self.knowledge.ollama_fallback(search_term)
            if out:
                print("\n--- local model ---")
                print(out)
                return True
            return False

        def show_docs_and_web():
            results = self.knowledge.search(search_term)
            if results and not self.raw:
                print(results[0].content.strip())
            docs = self.knowledge.lookup_docs(search_term)
            if docs and "No matching" not in docs:
                print("\n--- Nix docs ---")
                print(docs)
                return True
            web = self.knowledge.web_search(search_term)
            if web:
                print("\n--- web ---")
                print(web)
                return True
            return bool(results)

        if self.model_first:
            got = show_model()
            if not got:
                show_docs_and_web()
        else:
            got = show_docs_and_web()
            if not got:
                show_model()

    def handle_control_query(self, query, subject=None, explain=False,
                             dry_run=False, execute=False, yes=False):
        self._record(query, "control")
        mode = ExecutionMode.EXECUTE if execute else ExecutionMode.PREVIEW
        if mode == ExecutionMode.EXECUTE and not yes:
            ans = input(f"Run {query}? [y/N] ").strip().lower()
            if ans not in ("y", "yes"):
                print("Cancelled.")
                return
        result = self.executor.execute_safe(query, mode=mode)
        print(result.stdout if result.success else result.stderr)

    def _is_bare_package(self, query):
        parts = query.split()
        if len(parts) != 1:
            return False
        word = parts[0].lower()
        return word not in QueryRouter.CONTROL_KEYWORDS and not word.startswith("-")

    def handle_query(self, query, args):
        if query.lower() in ("help", "--help", "-h"):
            self.show_help()
            return
        if query.lower() == "start":
            self.show_start()
            return
        if query.lower() == "uninstall":
            self.uninstall()
            return
        query_type, subject = self.router.classify(query)
        if self._is_bare_package(query):
            query = f"install {query}"
            query_type = QueryType.CONTROL
        if query_type == QueryType.HELP:
            self.handle_help_query(query, subject)
        elif query_type == QueryType.CONTROL:
            self.handle_control_query(query, subject, execute=args.execute, yes=getattr(args, "yes", False))
        else:
            self.handle_help_query(query, subject)

    def interactive(self):
        print(f"AINIX {VERSION}")
        while True:
            try:
                line = input("ainix> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line or line.lower() in ("quit", "exit"):
                break
            if line.lower() == "help":
                self.show_help()
                continue
            if line.lower() == "start":
                self.show_start()
                continue
            class A: pass
            a = A()
            a.execute = False
            a.yes = False
            self.handle_query(line, a)


def main():
    parser = argparse.ArgumentParser(description="AINIX")
    parser.add_argument("query", nargs="*")
    parser.add_argument("--execute", "-x", action="store_true")
    parser.add_argument("--yes", "-y", action="store_true")
    parser.add_argument("--raw", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--history", action="store_true")
    parser.add_argument("--note", metavar="TEXT")
    parser.add_argument("--cache-clear", action="store_true")
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--model", metavar="NAME", help="Ollama model (optional)")
    parser.add_argument("--model-first", action="store_true", help="Ask model first")
    parser.add_argument("--docs-first", action="store_true", help="Docs/web first (default)")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--config", metavar="PATH")
    args = parser.parse_args()

    if args.version:
        print(VERSION)
        return

    model_first = None
    if args.model_first:
        model_first = True
    elif args.docs_first:
        model_first = False

    ainix = AINIX(
        config_path=args.config,
        quiet=args.quiet,
        raw=args.raw,
        model=args.model,
        model_first=model_first,
    )

    if args.uninstall:
        ainix.uninstall()
        return
    if args.cache_clear:
        ainix.cache_clear()
        return
    if args.note:
        ainix.add_note(args.note)
        return
    if args.list:
        print("\n".join(ainix.knowledge.list_topics()))
        return
    if args.history:
        ainix.show_history()
        return
    if not args.query:
        ainix.interactive()
        return
    ainix.handle_query(" ".join(args.query), args)


if __name__ == "__main__":
    main()
