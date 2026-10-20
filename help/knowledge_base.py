#!/usr/bin/env python3
"""
AINIX Help Layer: Knowledge base with ranked search and external fallback.
"""

import subprocess
from typing import Optional, List, Tuple
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
            topic="nix-package-management",
            content="""
Ways to install a package:

1. Per-user (temporary / profile):
   nix profile add nixpkgs#firefox

2. Temporary shell:
   nix shell nixpkgs#firefox

3. Declarative (preferred for permanence):
   environment.systemPackages = with pkgs; [ firefox ];
   then: sudo nixos-rebuild switch

Preview in AINIX never changes the system.
            """,
            tags=["packages", "install", "package", "nix", "installation"],
            related_topics=["nixos-rebuild"],
            examples=["nix profile add nixpkgs#firefox", "nix shell nixpkgs#git"]
        )

        self.add_entry(
            topic="nixos-rebuild",
            content="""
Activate configuration changes:

- build: build only
- switch: build and activate
- boot: activate on next boot
- test: temporary (reverts on reboot)

  sudo nixos-rebuild switch
  sudo nixos-rebuild test
            """,
            tags=["nixos", "rebuild", "system", "configuration"],
            related_topics=["nix-package-management"],
            examples=["nixos-rebuild switch", "nixos-rebuild test"]
        )

        self.add_entry(
            topic="generations-rollback",
            content="""
NixOS keeps generations. Rollback with:

  sudo nixos-rebuild switch --rollback

or pick a generation from the boot menu.
            """,
            tags=["rollback", "generation", "generations"],
            related_topics=["nixos-rebuild"],
            examples=["nixos-rebuild switch --rollback"]
        )

        self.add_entry(
            topic="ainix-usage",
            content="""
AINIX is a local NixOS assistant.

Help:    ainix "How do I install a package?"
Preview: ainix install firefox
Execute: ainix install firefox --execute

Preview never changes the system. Execute is logged.
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
        """Ranked search. Specific topics beat generic ones."""
        q = query.lower()
        scored: List[Tuple[int, KnowledgeEntry]] = []

        for entry in self.knowledge.values():
            score = 0
            # Strong: tag exact or contained
            for tag in entry.tags:
                if tag in q:
                    score += 10
                elif q in tag:
                    score += 5
            # Topic name
            if entry.topic.replace("-", " ") in q or q in entry.topic:
                score += 8
            # Content
            if q in entry.content.lower():
                score += 2
            # Prefer package topic for install/package questions
            if entry.topic == "nix-package-management" and any(
                w in q for w in ("install", "package", "packages")
            ):
                score += 15
            if score > 0:
                scored.append((score, entry))

        scored.sort(key=lambda x: -x[0])
        return [e for _, e in scored[:limit]]

    def list_topics(self) -> List[str]:
        return sorted(self.knowledge.keys())

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
        """Try real Nix tools. Returns None if tools missing or nothing found."""
        # Option path
        if "." in query and not query.startswith("http"):
            try:
                r = subprocess.run(
                    ["nixos-option", query],
                    capture_output=True, text=True, timeout=10
                )
                if r.returncode == 0 and r.stdout.strip():
                    return f"nixos-option {query}:\n\n{r.stdout[:1500]}"
            except FileNotFoundError:
                return "nixos-option not found on PATH."
            except subprocess.TimeoutExpired:
                return "nixos-option timed out."

        # Package search
        try:
            r = subprocess.run(
                ["nix", "search", "nixpkgs", query, "--no-update-lock-file"],
                capture_output=True, text=True, timeout=20
            )
            if r.returncode == 0 and r.stdout.strip():
                return f"nix search nixpkgs {query}:\n\n{r.stdout[:1500]}"
        except FileNotFoundError:
            return "nix not found on PATH. You can still run: nix search nixpkgs " + query
        except subprocess.TimeoutExpired:
            return "nix search timed out."

        return None
