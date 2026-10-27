#!/usr/bin/env python3
"""
Tests for AINIX help knowledge base.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from help.knowledge_base import HelpKnowledgeBase


def test_knowledge_search():
    kb = HelpKnowledgeBase()

    results = kb.search("install package")
    assert any(r.topic == "nix-package-management" for r in results)
    print("✓ Search finds package management")

    results = kb.search("rebuild")
    assert any(r.topic == "nixos-rebuild" for r in results)
    print("✓ Search finds nixos-rebuild")


def test_knowledge_retrieval():
    kb = HelpKnowledgeBase()

    for topic in ["nixos-rebuild", "nix-package-management", "ainix-usage"]:
        entry = kb.get(topic)
        assert entry is not None
        assert len(entry.content) > 0
        print(f"✓ Retrieved '{topic}'")


def test_list_topics():
    kb = HelpKnowledgeBase()
    topics = kb.list_topics()
    assert "nix-package-management" in topics
    assert "nixos-rebuild" in topics
    print(f"✓ Topics: {topics}")


def run_all_tests():
    print("Running AINIX Help Knowledge Base Tests")
    print("=" * 50)
    test_knowledge_search()
    print()
    test_knowledge_retrieval()
    print()
    test_list_topics()
    print()
    print("=" * 50)
    print("✅ All help knowledge base tests passed!")


if __name__ == "__main__":
    run_all_tests()
