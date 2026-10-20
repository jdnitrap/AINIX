#!/usr/bin/env python3
"""
AINIX: AI-Native NixOS Integration
Main CLI interface combining Help and Control layers.
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.router import QueryRouter, QueryType
from control.executor import SafeExecutor, ExecutionMode
from help.knowledge_base import HelpKnowledgeBase


class AINIX:
    def __init__(self, config_path=None):
        self.router = QueryRouter()
        self.executor = SafeExecutor(config_path)
        self.knowledge = HelpKnowledgeBase()

    def handle_help_query(self, query: str, subject: str = None):
        print("📚 Help System")
        print("-" * 40)

        search_term = subject or query
        results = self.knowledge.search(search_term)

        if results:
            for entry in results:
                print(f"\n📖 {entry.topic.upper()}")
                print("-" * 40)
                print(entry.content)
                if entry.examples:
                    print("\n💡 Examples:")
                    for example in entry.examples:
                        print(f"  {example}")
            return

        # Fall back to real Nix tools
        external = self.knowledge.lookup_external(search_term)
        if external:
            print(external)
            return

        print(f"📝 No local or external knowledge found for '{search_term}'")
        print("\nTry:")
        print("  nix search nixpkgs <name>")
        print("  nixos-option <option.path>")
        print("  https://nixos.org/manual/")

    def handle_control_query(self, query: str, subject: str = None,
                             explain: bool = False, dry_run: bool = False,
                             execute: bool = False):
        if explain:
            print("🔍 EXPLANATION MODE")
            print("-" * 40)
            print(f"Command: {query}")
            print(self.knowledge.explain_command(query.split()[0] if query.split() else ""))
            return

        print("⚙️  Control System")
        print("-" * 40)

        if dry_run:
            mode = ExecutionMode.DRY_RUN
        elif execute:
            mode = ExecutionMode.EXECUTE
        else:
            mode = ExecutionMode.PREVIEW

        print(f"📋 {query}")
        result = self.executor.execute_safe(query, mode=mode)

        if result.success:
            print(f"\n✅ {result.mode.value.upper()}")
            print(result.stdout)
        else:
            print(f"\n❌ FAILED")
            print(result.stderr)

        if mode == ExecutionMode.PREVIEW and result.success:
            print("\n" + "-" * 40)
            print("To execute, use: --execute or -x")
            print("Executions are logged to ~/.local/share/ainix/commands.log")

    def handle_query(self, query: str, args: argparse.Namespace):
        if args.explain:
            query_type = QueryType.EXPLAIN
            subject = None
        else:
            clean_query = query
            for flag in ['--execute', '-x', '--dry-run', '--explain']:
                clean_query = clean_query.replace(flag, '').strip()
            query_type, subject = self.router.classify(clean_query)

        print(f"\n🤖 AINIX - Query Type: {query_type.value}")
        print("=" * 40)

        clean_query = query
        for flag in ['--execute', '-x', '--dry-run', '--explain']:
            clean_query = clean_query.replace(flag, '').strip()

        if query_type == QueryType.HELP:
            self.handle_help_query(clean_query, subject)
        elif query_type == QueryType.EXPLAIN:
            self.handle_control_query(clean_query, subject, explain=True)
        elif query_type == QueryType.CONTROL:
            self.handle_control_query(
                clean_query, subject, explain=False,
                dry_run=args.dry_run, execute=args.execute
            )
        else:
            print("❓ UNKNOWN QUERY TYPE")
            print("Try a question (How/What) or a command (install, rebuild, ...)")


def main():
    parser = argparse.ArgumentParser(
        description="AINIX: AI-Native NixOS Integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ainix "How do I install Rust?"
  ainix install firefox
  ainix --explain nixos-rebuild
  ainix install firefox --execute
        """
    )
    parser.add_argument("query", nargs="+", help="Query or command")
    parser.add_argument("--explain", action="store_true", help="Explain a command")
    parser.add_argument("--dry-run", action="store_true", help="Simulate")
    parser.add_argument("--execute", "-x", action="store_true", help="Actually run")
    parser.add_argument("--config", metavar="PATH", help="Config file")

    args = parser.parse_args()
    query = " ".join(args.query)
    ainix = AINIX(config_path=args.config)
    ainix.handle_query(query, args)


if __name__ == "__main__":
    main()
