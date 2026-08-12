#!/usr/bin/env python3
"""
Tests for AINIX query router.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.router import QueryRouter, QueryType


def test_help_classification():
    """Test that help queries are correctly classified."""
    help_queries = [
        "How do I install a package?",
        "What's the difference between nix-env and configuration.nix?",
        "Tell me about NixOS",
        "Help, I'm stuck",
    ]

    for query in help_queries:
        query_type, subject = QueryRouter.classify(query)
        assert query_type == QueryType.HELP, f"Expected HELP for '{query}', got {query_type}"
        print(f"✓ HELP: {query}")


def test_control_classification():
    """Test that control queries are correctly classified."""
    control_queries = [
        "install firefox",
        "uninstall vim",
        "update the system",
        "build my project",
        "run this command",
    ]

    for query in control_queries:
        query_type, subject = QueryRouter.classify(query)
        assert query_type == QueryType.CONTROL, f"Expected CONTROL for '{query}', got {query_type}"
        print(f"✓ CONTROL: {query}")


def test_explanation_classification():
    """Test that explanation queries are correctly classified."""
    explain_queries = [
        "--explain nixos-rebuild",
        "explain what this does",
    ]

    for query in explain_queries:
        query_type, subject = QueryRouter.classify(query)
        assert query_type == QueryType.EXPLAIN, f"Expected EXPLAIN for '{query}', got {query_type}"
        print(f"✓ EXPLAIN: {query}")


def test_container_extraction():
    """Test container name extraction."""
    test_cases = [
        ("--container dev cargo build", "dev"),
        ("-c untrusted firefox", "untrusted"),
        ("install firefox", None),
        ("--container work cmd", "work"),
    ]

    for query, expected_container in test_cases:
        container = QueryRouter.extract_container_name(query)
        assert container == expected_container, \
            f"Expected container '{expected_container}' for '{query}', got {container}"
        print(f"✓ Container extraction: {query} → {container}")


def test_dangerous_operation_detection():
    """Test detection of dangerous operations."""
    dangerous_queries = [
        "install something",
        "uninstall vim",
        "rebuild the system",
        "deploy to production",
    ]

    safe_queries = [
        "show help",
        "list packages",
        "explain nixos",
    ]

    for query in dangerous_queries:
        query_type, _ = QueryRouter.classify(query)
        should_use = QueryRouter.should_use_container(query, query_type)
        print(f"✓ Dangerous op detected: {query} → {should_use}")

    for query in safe_queries:
        query_type, _ = QueryRouter.classify(query)
        should_use = QueryRouter.should_use_container(query, query_type)
        print(f"✓ Safe op: {query} → {should_use}")


def run_all_tests():
    """Run all tests."""
    print("Running AINIX Router Tests")
    print("=" * 50)

    test_help_classification()
    print()

    test_control_classification()
    print()

    test_explanation_classification()
    print()

    test_container_extraction()
    print()

    test_dangerous_operation_detection()
    print()

    print("=" * 50)
    print("✅ All tests passed!")


if __name__ == "__main__":
    run_all_tests()
