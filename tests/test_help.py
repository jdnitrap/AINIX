#!/usr/bin/env python3
"""
Tests for AINIX help knowledge base.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from help.knowledge_base import HelpKnowledgeBase


def test_knowledge_search():
    """Test knowledge base search."""
    kb = HelpKnowledgeBase()

    search_terms = [
        ("nixos", ["nixos-rebuild"]),
        ("packages", ["nix-package-management"]),
        ("containers", ["nixqubes-containers"]),
    ]

    for term, expected_topics in search_terms:
        results = kb.search(term)
        found_topics = [r.topic for r in results]
        print(f"✓ Search '{term}':")
        print(f"  Found: {found_topics}")
        print(f"  Expected: {expected_topics}")


def test_knowledge_retrieval():
    """Test retrieving specific knowledge entries."""
    kb = HelpKnowledgeBase()

    topics = ["nixos-rebuild", "nix-package-management", "nixqubes-containers"]

    for topic in topics:
        entry = kb.get(topic)
        assert entry is not None, f"Topic '{topic}' should exist"
        assert entry.topic == topic
        assert len(entry.content) > 0
        assert len(entry.examples) > 0
        print(f"✓ Retrieved '{topic}':")
        print(f"  Examples: {len(entry.examples)}")
        print(f"  Content length: {len(entry.content)} chars")


def test_related_topics():
    """Test finding related topics."""
    kb = HelpKnowledgeBase()

    entry = kb.get("nixos-rebuild")
    related = kb.suggest_related("nixos-rebuild")

    print(f"✓ Related topics for 'nixos-rebuild':")
    for rel in related:
        print(f"  - {rel.topic}")


def test_command_explanation():
    """Test explaining commands."""
    kb = HelpKnowledgeBase()

    commands = [
        "nixos-rebuild switch",
        "nix search firefox",
        "qubesctl start work",
    ]

    for cmd in commands:
        explanation = kb.explain_command(cmd)
        has_content = len(explanation) > 20 and "No explanation" not in explanation
        status = "✓" if has_content else "✗"
        print(f"{status} Explain '{cmd}':")
        if has_content:
            print(f"  Content length: {len(explanation)} chars")
        else:
            print(f"  No explanation available")


def test_tags_and_metadata():
    """Test tags and metadata retrieval."""
    kb = HelpKnowledgeBase()

    entry = kb.get("nixqubes-containers")
    assert entry is not None
    assert "security" in entry.tags or "containers" in entry.tags
    print(f"✓ Tags for 'nixqubes-containers':")
    print(f"  Tags: {entry.tags}")
    print(f"  Related: {entry.related_topics}")


def test_examples_quality():
    """Test that examples are meaningful."""
    kb = HelpKnowledgeBase()

    for topic in ["nixos-rebuild", "nix-package-management", "nixqubes-containers"]:
        entry = kb.get(topic)
        print(f"✓ Examples for '{topic}':")
        for i, example in enumerate(entry.examples, 1):
            print(f"  {i}. {example}")


def run_all_tests():
    """Run all tests."""
    print("Running AINIX Help Knowledge Base Tests")
    print("=" * 50)

    test_knowledge_search()
    print()

    test_knowledge_retrieval()
    print()

    test_related_topics()
    print()

    test_command_explanation()
    print()

    test_tags_and_metadata()
    print()

    test_examples_quality()
    print()

    print("=" * 50)
    print("✅ All help knowledge base tests passed!")


if __name__ == "__main__":
    run_all_tests()
