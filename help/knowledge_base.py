#!/usr/bin/env python3
"""
AINIX Help Layer: local knowledge plus real Nix docs.
"""

import subprocess
import shutil
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
        q = query.lower()
        scored: List[Tuple[int, KnowledgeEntry]] = []
        for entry in self.knowledge.values():
            score = 0
            for tag in entry.tags:
                if tag in q:
                    score += 10
                elif q in tag:
                    score += 5
            if entry.topic.replace("-", " ") in q or q in entry.topic:
                score += 8
            if q in entry.content.lower():
                score += 2
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

    def _run(self, cmd: List[str], timeout: int = 15) -> Optional[str]:
        if not shutil.which(cmd[0]):
            return None
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except (subprocess.TimeoutExpired, Exception):
            return None
        return None

    def lookup_docs(self, query: str) -> str:
        """Always consult real Nix docs. Returns a combined text block."""
        sections = []
        q = query.strip()

        # Option path (services.foo.enable, boot.loader..., etc.)
        if "." in q and not q.startswith("http"):
            out = self._run(["nixos-option", q], timeout=10)
            if out:
                sections.append(f"nixos-option {q}\n\n{out[:2000]}")

        # Package search
        # Strip common question words for a cleaner search term
        search_term = q
        for w in ("how", "do", "i", "install", "a", "the", "package", "packages", "what", "is"):
            search_term = search_term.replace(w, " ")
        search_term = " ".join(search_term.split())
        if search_term and len(search_term) < 60:
            out = self._run(
                ["nix", "search", "nixpkgs", search_term, "--no-update-lock-file"],
                timeout=25
            )
            if out:
                sections.append(f"nix search nixpkgs {search_term}\n\n{out[:2000]}")

        # man page for the first word if it looks like a command
        first = q.split()[0] if q.split() else ""
        if first and shutil.which("man"):
            out = self._run(["man", "-P", "cat", first], timeout=5)
            if out:
                sections.append(f"man {first}\n\n{out[:1200]}")

        if not sections:
            missing = []
            if not shutil.which("nixos-option"):
                missing.append("nixos-option")
            if not shutil.which("nix"):
                missing.append("nix")
            if missing:
                return "Nix docs tools not on PATH: " + ", ".join(missing)
            return "No matching Nix docs found."

        return "\n\n---\n\n".join(sections)
