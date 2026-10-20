#!/usr/bin/env python3
"""
AINIX Help Layer: local knowledge, cached Nix docs, optional Ollama.
"""

import subprocess
import shutil
import json
import hashlib
from pathlib import Path
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
        self.cache_dir = Path.home() / ".local" / "share" / "ainix" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
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
            examples=["nix profile add nixpkgs#firefox"]
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
            examples=["nixos-rebuild switch"]
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

Preview never changes the system.
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
            if entry.topic.replace("-", " ") in q or q in entry.topic:
                score += 8
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

    def _cache_key(self, query: str) -> Path:
        h = hashlib.sha256(query.encode()).hexdigest()[:16]
        return self.cache_dir / f"{h}.txt"

    def _summarize(self, text: str, max_lines: int = 25) -> str:
        lines = text.strip().splitlines()
        if len(lines) <= max_lines:
            return text.strip()
        return "\n".join(lines[:max_lines]) + f"\n... ({len(lines) - max_lines} more lines)"

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
        cache_file = self._cache_key(query)
        if cache_file.exists():
            return cache_file.read_text() + "\n(cached)"

        sections = []
        q = query.strip()

        if "." in q and not q.startswith("http"):
            out = self._run(["nixos-option", q], timeout=10)
            if out:
                sections.append(f"[nixos-option] {q}\n\n{self._summarize(out)}")

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
                sections.append(f"[nix search] {search_term}\n\n{self._summarize(out)}")

        first = q.split()[0] if q.split() else ""
        if first and shutil.which("man"):
            out = self._run(["man", "-P", "cat", first], timeout=5)
            if out:
                sections.append(f"[man] {first}\n\n{self._summarize(out, 15)}")

        if not sections:
            missing = []
            if not shutil.which("nixos-option"):
                missing.append("nixos-option")
            if not shutil.which("nix"):
                missing.append("nix")
            if missing:
                return "Nix docs tools not on PATH: " + ", ".join(missing)
            return "No matching Nix docs found."

        result = "\n\n---\n\n".join(sections)
        cache_file.write_text(result)
        return result

    def ollama_fallback(self, query: str) -> Optional[str]:
        """Optional local model. Returns None if Ollama is unavailable."""
        if not shutil.which("ollama"):
            return None
        prompt = (
            "You are a NixOS assistant. Answer briefly using NixOS conventions. "
            "Do not invent options. If unsure, say so.\n\nQuestion: " + query
        )
        try:
            r = subprocess.run(
                ["ollama", "run", "llama3", prompt],
                capture_output=True, text=True, timeout=60
            )
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except (subprocess.TimeoutExpired, Exception):
            return None
        return None
