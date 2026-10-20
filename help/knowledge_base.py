#!/usr/bin/env python3
"""
AINIX Help Layer: Knowledge base and advisory system.
Falls back to real Nix tools when the local base has no answer.
"""

import subprocess
from typing import Optional, List
from dataclasses import dataclass

@dataclass
class KnowledgeEntry:
    topic: str
    content: str
    tags: List[str]
    related_topics: List[str]
    examples: List[str]

class HelpKnowledgeBase:
    def __init__(self):
        self.knowledge = {}
        self._initialize_core_knowledge()

    def _initialize_core_knowledge(self):
        self.add_entry(
            topic="nixos-rebuild",
            content="""
NixOS uses nixos-rebuild to activate configuration changes.

Main operations:
- build: Build without activating
- switch: Build and activate
- boot: Activate on next boot
- test: Activate temporarily (reverts on reboot)

  sudo nixos-rebuild switch
  sudo nixos-rebuild test
  nixos-rebuild build
            """,
            tags=["nixos", "system", "configuration"],
            related_topics=["nix-rebuild"],
            examples=["nixos-rebuild switch", "nixos-rebuild test"]
        )

        self.add_entry(
            topic="nix-package-management",
            content="""
Ways to manage packages:

1. System packages in configuration.nix
2. nix profile install (per-user)
3. nix shell / nix run (temporary)

Prefer declarative system or home-manager packages for permanence.
            """,
            tags=["packages", "nix", "installation"],
            related_topics=["system-packages"],
            examples=["nix profile install nixpkgs#firefox", "nix shell nixpkgs#git"]
        )

        self.add_entry(
            topic="ainix-usage",
            content="""
AINIX is a local NixOS assistant.

Help:  ainix "How do I install a package?"
Preview: ainix install firefox
Execute: ainix install firefox --execute

Preview is the default. Execute is logged.
            """,
            tags=["ainix", "usage"],
            related_topics=[],
            examples=["ainix install firefox"]
        )

    def add_entry(self, topic, content, tags, related_topics, examples):
        self.knowledge[topic.lower()] = KnowledgeEntry(
            topic=topic, content=content, tags=tags,
            related_topics=related_topics, examples=examples
        )

    def search(self, query: str, limit: int = 3) -> List[KnowledgeEntry]:
        query_lower = query.lower()
        results = []
        for topic, entry in self.knowledge.items():
            if query_lower in topic or any(query_lower in t.lower() for t in entry.tags) or query_lower in entry.content.lower():
                results.append(entry)
        return results[:limit]

    def get(self, topic: str) -> Optional[KnowledgeEntry]:
        return self.knowledge.get(topic.lower())

    def explain_command(self, command: str) -> str:
        for prefix in ("nixos-rebuild", "nix-env", "nix"):
            if command.startswith(prefix):
                entry = self.get(prefix if prefix != "nix" else "nix-package-management")
                if entry:
                    return entry.content
        return "No explanation available."

    def lookup_external(self, query: str) -> Optional[str]:
        """Try real Nix tools for an answer."""
        # Try nixos-option if it looks like an option path
        if "." in query and not query.startswith("http"):
            try:
                r = subprocess.run(
                    ["nixos-option", query],
                    capture_output=True, text=True, timeout=15
                )
                if r.returncode == 0 and r.stdout.strip():
                    return f"nixos-option {query}:\n\n{r.stdout[:2000]}"
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

        # Try nix search for package-like queries
        try:
            r = subprocess.run(
                ["nix", "search", "nixpkgs", query, "--no-update-lock-file"],
                capture_output=True, text=True, timeout=30
            )
            if r.returncode == 0 and r.stdout.strip():
                return f"nix search nixpkgs {query}:\n\n{r.stdout[:2000]}"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        return None
