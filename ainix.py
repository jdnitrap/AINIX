#!/usr/bin/env python3
"""
AINIX test branch: local model is the main answer path.
"""

import sys
import argparse
import json
import shutil
from pathlib import Path
from datetime import datetime

VERSION = "0.6.0-test"

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
        # Test branch: model-first by default
        if model_first is None:
            self.model_first = bool(cfg.get("model_first", True))
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

    def show_help(self):
        model = self.knowledge.pick_model() or "none (install ollama + a model)"
        print(f"""AINIX {VERSION} (test)
Local model is the default answer path.
Model: {model}

  ainix "How do I enable ssh?"
  ainix --model gemma2:9b "question"
  ainix --docs-first "question"   # fall back to docs/web

Control stays preview-first. The model does not change the system.
""")

    def show_start(self):
        print("AINIX test: ask in plain language. A local model answers.\n")
        print("Example: ainix \"How do I install a package?\"")

    def uninstall(self):
        paths = [
            Path.home() / ".local" / "bin" / "ainix",
            Path.home() / ".local" / "share" / "ainix",
        ]
        for p in paths:
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                shutil.rmtree(p)
        print("Uninstalled.")

    def cache_clear(self):
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
            print("cleared cache")

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
                print(f"{e.get('time','')}  {e.get('query','')}")
            except json.JSONDecodeError:
                continue

    def handle_help_query(self, query, subject=None):
        search_term = subject or query
        self._record(search_term, "help")

        # Ground the model with a short docs snippet when possible
        docs = self.knowledge.lookup_docs(search_term)
        context = ""
        if docs and "No matching" not in docs:
            context = docs[:800]

        if self.model_first:
            prompt = search_term
            if context:
                prompt = (
                    "Use this Nix context if relevant. Do not invent options.\n\n"
                    + context + "\n\nQuestion: " + search_term
                )
            # Temporarily override by calling ollama with enriched prompt via fallback path
            out = self.knowledge.ollama_fallback(prompt)
            if out:
                print("--- local model ---")
                print(out)
                return
            print("No local model available. Falling back to docs.\n")

        results = self.knowledge.search(search_term)
        if results:
            print(results[0].content.strip())
        if docs and "No matching" not in docs:
            print("\n--- Nix docs ---")
            print(docs)
        web = self.knowledge.web_search(search_term)
        if web:
            print("\n--- web ---")
            print(web)

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
        print("\nPreview never changes the system." if mode == ExecutionMode.PREVIEW else "")

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
        print(f"AINIX {VERSION} — local model answers")
        while True:
            try:
                line = input("ainix> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line or line.lower() in ("quit", "exit"):
                break
            class A: pass
            a = A()
            a.execute = False
            a.yes = False
            self.handle_query(line, a)


def main():
    parser = argparse.ArgumentParser(description="AINIX test: local model first")
    parser.add_argument("query", nargs="*")
    parser.add_argument("--execute", "-x", action="store_true")
    parser.add_argument("--yes", "-y", action="store_true")
    parser.add_argument("--raw", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--history", action="store_true")
    parser.add_argument("--cache-clear", action="store_true")
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--model", metavar="NAME")
    parser.add_argument("--docs-first", action="store_true", help="Skip model, use docs")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--config", metavar="PATH")
    args = parser.parse_args()

    if args.version:
        print(VERSION)
        return

    ainix = AINIX(
        config_path=args.config,
        quiet=args.quiet,
        raw=args.raw,
        model=args.model,
        model_first=False if args.docs_first else None,
    )

    if args.uninstall:
        ainix.uninstall()
        return
    if args.cache_clear:
        ainix.cache_clear()
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
