#!/usr/bin/env python3
"""
AINIX: AI-Native NixOS Integration
"""

import sys
import argparse
import json
from pathlib import Path
from datetime import datetime

VERSION = "0.4.1"

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
        self.data_dir = Path.home() / ".local" / "share" / "ainix"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = self.data_dir / "history.log"
        self.notes_file = self.data_dir / "notes.txt"

    def show_help(self):
        print(f"""AINIX {VERSION} — local NixOS assistant

Usage:
  ainix help                         this help
  ainix --help                       argparse help
  ainix "How do I install a package?"  ask a question
  ainix install firefox              preview an install
  ainix firefox                      same (bare name)
  ainix code "enable openssh"        generate NixOS snippet
  ainix code "flake for myhost"      generate flake.nix
  ainix code "package mytool not in nixpkgs"
  ainix --note "remember this"       save a note
  ainix --history                    recent queries
  ainix --list                       knowledge topics
  ainix --examples                   short examples
  ainix --version                    version
  ainix                              interactive mode
  man ainix                          man page

Preview is the default. Nothing runs or is written unless you pass --execute.
""")

    def _record(self, query: str, kind: str):
        entry = {"time": datetime.utcnow().isoformat() + "Z", "query": query, "kind": kind}
        with open(self.history_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def show_history(self, n: int = 20):
        if not self.history_file.exists():
            print("No history yet.")
            return
        lines = self.history_file.read_text().strip().splitlines()
        for line in lines[-n:]:
            try:
                e = json.loads(line)
                print(f"{e.get('time','')}  [{e.get('kind','')}]  {e.get('query','')}")
            except json.JSONDecodeError:
                continue

    def detect_style(self) -> str:
        if Path("/etc/nixos/flake.nix").exists() or Path("flake.nix").exists():
            return "flakes"
        return "channels"

    def add_note(self, text: str):
        with open(self.notes_file, "a") as f:
            f.write(text.strip() + "\n")
        print(f"Noted: {text.strip()}")

    def search_notes(self, query: str) -> list:
        if not self.notes_file.exists():
            return []
        q = query.lower()
        return [ln for ln in self.notes_file.read_text().splitlines() if q in ln.lower()]

    def explain_error(self, text: str) -> str:
        t = text.lower()
        tips = []
        if "collision" in t or "already exists" in t:
            tips.append("Package collision: two packages provide the same file. Use priority or remove one.")
        if "attribute" in t and "missing" in t:
            tips.append("Missing attribute: the package or option name is wrong, or it was renamed.")
        if "infinite recursion" in t:
            tips.append("Infinite recursion: an option or overlay refers to itself. Check recent changes.")
        if "hash mismatch" in t:
            tips.append("Hash mismatch: the source changed. Update the hash or clear the cache.")
        if "permission denied" in t:
            tips.append("Permission denied: you may need sudo, or the path is not writable.")
        if "no such file" in t or "not found" in t:
            tips.append("File or package not found. Check the name and that the input is available.")
        if not tips:
            tips.append("No specific pattern matched. Check the full error and recent config changes.")
        tips.append("You can roll back with: sudo nixos-rebuild switch --rollback")
        return "\n".join(f"- {x}" for x in tips)

    def generate_code(self, request: str) -> str:
        r = request.lower().strip()

        if any(w in r for w in ("package", "derivation", "not in nixpkgs", "custom program", "write a program")):
            name = "myprogram"
            for w in request.split():
                if w.isidentifier() and w.lower() not in ("package", "derivation", "a", "the", "program"):
                    name = w
                    break
            return f'''# Custom derivation (not from nixpkgs)
# Save as {name}.nix and use via pkgs.callPackage ./{name}.nix {{}}

{{ lib, stdenv, fetchurl }}:

stdenv.mkDerivation rec {{
  pname = "{name}";
  version = "0.1.0";

  src = fetchurl {{
    url = "https://example.com/{name}-${{version}}.tar.gz";
    hash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
  }};

  installPhase = ''
    mkdir -p $out/bin
  '';

  meta = with lib; {{
    description = "Custom {name}";
    license = licenses.mit;
    platforms = platforms.linux;
  }};
}}
'''

        if "flake" in r:
            return '''# flake.nix
{
  description = "My NixOS config";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  outputs = { self, nixpkgs }: {
    nixosConfigurations.myhost = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      modules = [ ./configuration.nix ];
    };
  };
}
'''

        if "enable" in r or "service" in r:
            return '''# Add to configuration.nix
services.openssh.enable = true;
'''

        if "install" in r or "add package" in r or "systempackages" in r:
            pkg = request.split()[-1] if len(request.split()) > 1 else "firefox"
            return f'''# Add to configuration.nix
environment.systemPackages = with pkgs; [
  {pkg}
];
'''

        ollama = self.knowledge.ollama_fallback(
            "Write a short NixOS configuration.nix snippet for: " + request +
            ". Output only Nix code. Do not invent options."
        )
        if ollama:
            return "# From Ollama (review before use)\n" + ollama

        return f'''# Generic NixOS snippet for: {request}
{{ config, pkgs, ... }}:
{{
  # environment.systemPackages = with pkgs; [ ];
  # services.<name>.enable = true;
}}
'''

    def handle_code(self, request: str):
        self._record(request, "code")
        print("\n--- generated (preview only, not written) ---")
        print(self.generate_code(request))
        print("--- end ---")
        print("This does not change any files.")

    def handle_help_query(self, query: str, subject: str = None):
        if not self.quiet and not self.raw:
            print("\n📚 Help")
            print("-" * 40)
        search_term = subject or query
        self._record(search_term, "help")
        style = self.detect_style()
        if not self.raw:
            print(f"[system] {style}")
        notes = self.search_notes(search_term)
        if notes and not self.raw:
            print("\n[notes]")
            for n in notes[:5]:
                print(f"  {n}")
        if any(w in search_term.lower() for w in ("error", "failed", "collision", "recursion")):
            print("\n[error hint]")
            print(self.explain_error(search_term))
        results = self.knowledge.search(search_term)
        if results and not self.raw:
            top = results[0]
            print(f"\n[local] {top.topic}\n")
            print(top.content.strip())
        docs = self.knowledge.lookup_docs(search_term)
        has_docs = docs and "No matching" not in docs and "not on PATH" not in docs
        if has_docs:
            if not self.raw:
                print("\n--- Nix docs ---")
            print(docs)
        elif not results and not notes:
            ollama = self.knowledge.ollama_fallback(search_term)
            if ollama:
                print("\n--- Ollama (local model) ---")
                print(ollama)
            else:
                print(f"No local knowledge or Nix docs for '{search_term}'.")

    def handle_control_query(self, query: str, subject: str = None,
                             explain: bool = False, dry_run: bool = False,
                             execute: bool = False, yes: bool = False):
        if explain:
            print(self.knowledge.explain_command(query.split()[0] if query.split() else ""))
            return
        if not self.quiet and not self.raw:
            print("\n⚙️  Control")
            print("-" * 40)
        self._record(query, "control")
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
                print("\nPreview never changes the system.")
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
        if query.lower() in ("help", "--help", "-h"):
            self.show_help()
            return
        if query.lower().startswith("code "):
            self.handle_code(query[5:])
            return
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
        print(f"AINIX {VERSION} — type 'help' or empty line to exit")
        print("Preview never changes the system.\n")
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
            if line.lower() == "examples":
                self._examples()
                continue
            if line.lower() == "list":
                print("\n".join(self.knowledge.list_topics()))
                continue
            if line.lower() == "history":
                self.show_history()
                continue
            if line.lower().startswith("note "):
                self.add_note(line[5:])
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
  ainix help
  ainix "How do I install a package?"
  ainix install firefox
  ainix code "enable openssh"
  ainix --history
""".strip())


def main():
    parser = argparse.ArgumentParser(description="AINIX: local NixOS assistant")
    parser.add_argument("query", nargs="*", help="Query or command")
    parser.add_argument("--explain", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", "-x", action="store_true")
    parser.add_argument("--yes", "-y", action="store_true")
    parser.add_argument("--raw", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--examples", action="store_true")
    parser.add_argument("--history", action="store_true")
    parser.add_argument("--note", metavar="TEXT")
    parser.add_argument("--code", metavar="REQUEST")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--config", metavar="PATH")

    args = parser.parse_args()

    if args.version:
        print(VERSION)
        return

    ainix = AINIX(config_path=args.config, quiet=args.quiet, raw=args.raw)

    if args.note:
        ainix.add_note(args.note)
        return
    if args.code:
        ainix.handle_code(args.code)
        return
    if args.examples:
        ainix._examples()
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
