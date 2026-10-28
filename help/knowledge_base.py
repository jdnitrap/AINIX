#!/usr/bin/env python3
"""
AINIX Help Layer: local knowledge, Nix docs, optional web, optional local model.
Hardware-agnostic: no CUDA/ROCm assumptions. Model is optional.
"""

import subprocess
import shutil
import json
import hashlib
import socket
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
    def __init__(self, model: Optional[str] = None):
        self.knowledge = {}
        self.model = model  # explicit override; None = auto or none
        self.cache_dir = Path.home() / ".local" / "share" / "ainix" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._initialize_core_knowledge()

    def _initialize_core_knowledge(self):
        self.add_entry(
            topic="nix-package-management",
            content="""
Ways to install a package:

1. Per-user: nix profile add nixpkgs#firefox
2. Temporary: nix shell nixpkgs#firefox
3. Declarative: environment.systemPackages = with pkgs; [ firefox ];

Preview in AINIX never changes the system.
            """,
            tags=["packages", "install", "package", "nix"],
            related_topics=["nixos-rebuild"],
            examples=["nix profile add nixpkgs#firefox"]
        )
        self.add_entry(
            topic="nixos-rebuild",
            content="""
Activate configuration changes:
  sudo nixos-rebuild switch
  sudo nixos-rebuild test
  sudo nixos-rebuild switch --rollback

See changes first:
  ainix rebuild
            """,
            tags=["nixos", "rebuild", "system"],
            related_topics=["nix-package-management", "generations"],
            examples=["nixos-rebuild switch", "ainix rebuild"]
        )
        self.add_entry(
            topic="flakes",
            content="""
Flakes pin inputs and define outputs.

Typical rebuild:
  sudo nixos-rebuild switch --flake .#hostname

Check for a flake:
  ls flake.nix
  or /etc/nixos/flake.nix
            """,
            tags=["flake", "flakes", "nix"],
            related_topics=["nixos-rebuild"],
            examples=["sudo nixos-rebuild switch --flake .#hostname"]
        )
        self.add_entry(
            topic="generations",
            content="""
NixOS keeps previous system generations.

List:
  nixos-rebuild list-generations

Rollback:
  sudo nixos-rebuild switch --rollback

Or select an older generation at the boot menu.
            """,
            tags=["generation", "generations", "rollback"],
            related_topics=["nixos-rebuild"],
            examples=["nixos-rebuild list-generations"]
        )
        self.add_entry(
            topic="home-manager",
            content="""
Home Manager manages user config separately from the system.

Standalone:
  home-manager switch

With a flake:
  home-manager switch --flake .#user@host

AINIX detects common locations:
  ainix home
            """,
            tags=["home", "home-manager", "user"],
            related_topics=["nixos-rebuild"],
            examples=["home-manager switch", "ainix home"]
        )
        self.add_entry(
            topic="ainix-usage",
            content="""
AINIX is a local NixOS assistant.
Help, preview, and optional local model. Model is not required.
Preview never changes the system.

Useful:
  ainix rebuild
  ainix home
            """,
            tags=["ainix", "usage"],
            related_topics=[],
            examples=["ainix help", "ainix start", "ainix rebuild"]
        )

    def add_entry(self, topic, content, tags, related_topics, examples):
        self.knowledge[topic.lower()] = KnowledgeEntry(
            topic=topic, content=content, tags=tags,
            related_topics=related_topics, examples=examples
        )

    def search(self, query: str, limit: int = 3) -> List[KnowledgeEntry]:
        q = query.lower()
        scored = []
        for entry in self.knowledge.values():
            score = 0
            for tag in entry.tags:
                if tag in q:
                    score += 10
            if entry.topic == "nix-package-management" and any(
                w in q for w in ("install", "package")
            ):
                score += 15
            if score > 0:
                scored.append((score, entry))
        scored.sort(key=lambda x: -x[0])
        return [e for _, e in scored[:limit]]

    def list_topics(self) -> List[str]:
        return sorted(self.knowledge.keys())

    def get(self, topic: str):
        return self.knowledge.get(topic.lower())

    def explain_command(self, command: str) -> str:
        for prefix in ("nixos-rebuild", "nix"):
            if command.startswith(prefix):
                entry = self.get(prefix if prefix != "nix" else "nix-package-management")
                if entry:
                    return entry.content
        return "No explanation available."

    def is_online(self) -> bool:
        try:
            socket.create_connection(("1.1.1.1", 53), timeout=2)
            return True
        except OSError:
            return False

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
        cache_file = self.cache_dir / (hashlib.sha256(query.encode()).hexdigest()[:16] + ".txt")
        if cache_file.exists():
            return cache_file.read_text() + "\n(cached)"

        sections = []
        q = query.strip()
        if "." in q and not q.startswith("http"):
            out = self._run(["nixos-option", q], timeout=10)
            if out:
                sections.append(f"[nixos-option] {q}\n\n{out[:1500]}")

        search_term = q
        for w in ("how", "do", "i", "install", "a", "the", "package", "what", "is"):
            search_term = search_term.replace(w, " ")
        search_term = " ".join(search_term.split())
        if search_term and len(search_term) < 60:
            out = self._run(["nix", "search", "nixpkgs", search_term, "--no-update-lock-file"], timeout=25)
            if out:
                sections.append(f"[nix search] {search_term}\n\n{out[:1500]}")

        if not sections:
            return "No matching Nix docs found."
        result = "\n\n---\n\n".join(sections)
        cache_file.write_text(result)
        return result

    def web_search(self, query: str) -> Optional[str]:
        """Search the web if online. Returns snippets or None."""
        if not self.is_online():
            return None
        if not shutil.which("curl"):
            return None
        # DuckDuckGo HTML lite — no API key
        url = "https://html.duckduckgo.com/html/?q=" + query.replace(" ", "+") + "+nixos"
        try:
            r = subprocess.run(
                ["curl", "-fsSL", "-A", "AINIX", url],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode != 0 or not r.stdout:
                return None
            # Crude extract of result snippets
            lines = []
            for line in r.stdout.splitlines():
                if "result__snippet" in line or "result__a" in line:
                    text = line.split(">", 1)[-1].split("<", 1)[0].strip()
                    if text and len(text) > 20:
                        lines.append(text)
                if len(lines) >= 5:
                    break
            if lines:
                return "\n".join(f"- {t}" for t in lines)
        except (subprocess.TimeoutExpired, Exception):
            return None
        return None

    def list_ollama_models(self) -> List[str]:
        if not shutil.which("ollama"):
            return []
        out = self._run(["ollama", "list"], timeout=10)
        if not out:
            return []
        models = []
        for line in out.splitlines()[1:]:
            parts = line.split()
            if parts:
                models.append(parts[0])
        return models

    def pick_model(self) -> Optional[str]:
        """Explicit model, else smallest available, else None."""
        if self.model:
            return self.model
        models = self.list_ollama_models()
        if not models:
            return None
        # Prefer smaller class names if present
        prefer = ("gemma2:2b", "gemma2:9b", "qwen2.5:7b", "llama3.2", "llama3.1:8b", "phi3")
        for p in prefer:
            for m in models:
                if p in m:
                    return m
        return models[0]

    def ollama_fallback(self, query: str) -> Optional[str]:
        """Optional local model. No GPU assumptions. Returns None if unavailable."""
        model = self.pick_model()
        if not model or not shutil.which("ollama"):
            return None
        prompt = (
            "You are a NixOS assistant. Answer briefly. "
            "Do not invent options. If unsure, say so.\n\nQuestion: " + query
        )
        try:
            r = subprocess.run(
                ["ollama", "run", model, prompt],
                capture_output=True, text=True, timeout=90
            )
            if r.returncode == 0 and r.stdout.strip():
                return f"[{model}]\n{r.stdout.strip()}"
        except (subprocess.TimeoutExpired, Exception):
            return None
        return None
