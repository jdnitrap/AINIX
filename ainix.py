#!/usr/bin/env python3
"""
AINIX: AI-Native NixOS Integration
Main CLI interface combining Help and Control layers.
"""

import sys
import argparse
from pathlib import Path

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent))

from core.router import QueryRouter, QueryType
from control.executor import SafeExecutor, ExecutionMode
from help.knowledge_base import HelpKnowledgeBase


class AINIX:
    """Main AINIX system combining Help and Control."""

    def __init__(self, config_path=None):
        self.router = QueryRouter()
        self.executor = SafeExecutor(config_path)
        self.knowledge = HelpKnowledgeBase()

    def handle_help_query(self, query: str, subject: str = None):
        """Handle a help/advisory query."""
        print("📚 Help System")
        print("-" * 40)

        # Search knowledge base
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
        else:
            # Fallback: try command explanation
            print(f"📝 No direct knowledge found for '{search_term}'")
            print("\nTrying command explanation...")
            explanation = self.knowledge.explain_command(search_term.lower())
            if explanation and "No explanation" not in explanation:
                print(explanation)
            else:
                print("\n⚠️  No explanation available.")
                print("Consider:")
                print("  1. Checking the NixOS manual: https://nixos.org/manual/")
                print("  2. Asking 'nix --help'")
                print("  3. Using 'nix search <term>' to find packages")

    def handle_control_query(
        self,
        query: str,
        subject: str = None,
        explain: bool = False,
        dry_run: bool = False,
        execute: bool = False
    ):
        """Handle a control/execution query."""
        if explain:
            print("🔍 EXPLANATION MODE")
            print("-" * 40)
            print(f"Command: {query}")
            explanation = self.knowledge.explain_command(query.split()[0] if query.split() else "")
            print(explanation)
            return

        print("⚙️  Control System")
        print("-" * 40)

        # Determine execution mode
        if dry_run:
            mode = ExecutionMode.DRY_RUN
        elif execute:
            mode = ExecutionMode.EXECUTE
        else:
            mode = ExecutionMode.PREVIEW

        # Execute safely
        print(f"📋 Executing: {query}")

        result = self.executor.execute_safe(query, mode=mode)

        if result.success:
            print(f"\n✅ {result.mode.value.upper()}")
            print(result.stdout)
        else:
            print(f"\n❌ FAILED")
            print(result.stderr)

        # If in preview mode, offer to execute
        if mode == ExecutionMode.PREVIEW and result.success:
            print("\n" + "-" * 40)
            print("To execute, use: --execute or -x")

    def handle_query(self, query: str, args: argparse.Namespace):
        """Route and handle a user query."""
        # Check if --explain flag is explicitly set
        if args.explain:
            query_type = QueryType.EXPLAIN
            subject = None
        else:
            # Remove control flags from query for routing
            clean_query = query
            for flag in ['--execute', '-x', '--dry-run', '--explain']:
                clean_query = clean_query.replace(flag, '').strip()

            # Classify query
            query_type, subject = self.router.classify(clean_query)

        print(f"\n🤖 AINIX - Query Type: {query_type.value}")
        print("=" * 40)

        # Clean query for processing
        clean_query = query
        for flag in ['--execute', '-x', '--dry-run', '--explain']:
            clean_query = clean_query.replace(flag, '').strip()

        if query_type == QueryType.HELP:
            self.handle_help_query(clean_query, subject)

        elif query_type == QueryType.EXPLAIN:
            self.handle_control_query(
                clean_query,
                subject,
                explain=True
            )

        elif query_type == QueryType.CONTROL:
            self.handle_control_query(
                clean_query,
                subject,
                explain=False,
                dry_run=args.dry_run,
                execute=args.execute
            )

        else:
            print("❓ UNKNOWN QUERY TYPE")
            print("-" * 40)
            print("Could not determine if this is a help or control query.")
            print("Try:")
            print("  ainix 'How do I install X?'    (for help)")
            print("  ainix install X                (for control)")
            print("  ainix --explain command        (for explanation)")


def main():
    parser = argparse.ArgumentParser(
        description="AINIX: AI-Native NixOS Integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ainix "How do I install Rust?"
  ainix install firefox
  ainix --explain nixos-rebuild
  ainix --dry-run update
  ainix install firefox --execute
        """
    )

    parser.add_argument("query", nargs="+", help="Query or command to execute")
    parser.add_argument(
        "--explain",
        action="store_true",
        help="Show detailed explanation of command"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate execution without running"
    )
    parser.add_argument(
        "--execute", "-x",
        action="store_true",
        help="Execute without preview (dangerous - use with caution)"
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        help="Path to AINIX configuration file"
    )

    args = parser.parse_args()

    # Join query parts
    query = " ".join(args.query)

    # Initialize AINIX
    ainix = AINIX(config_path=args.config)

    # Handle query
    ainix.handle_query(query, args)


if __name__ == "__main__":
    main()
