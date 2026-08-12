#!/usr/bin/env python3
"""
AINIX Help Layer: Knowledge base and advisory system.
"""

from typing import Optional, Dict, List
from dataclasses import dataclass

@dataclass
class KnowledgeEntry:
    """A piece of knowledge in the knowledge base."""
    topic: str
    content: str
    tags: List[str]
    related_topics: List[str]
    examples: List[str]

class HelpKnowledgeBase:
    """Knowledge base for NixOS and AINIX topics."""

    def __init__(self):
        self.knowledge = {}
        self._initialize_core_knowledge()

    def _initialize_core_knowledge(self):
        """Initialize core knowledge about NixOS and AINIX."""

        # NixOS Basics
        self.add_entry(
            topic="nixos-rebuild",
            content="""
NixOS uses nixos-rebuild to activate configuration changes.

Main operations:
- build: Build the new configuration without activating
- switch: Build and activate the configuration
- boot: Build but only activate on next boot
- test: Build and activate, but not permanently (reverts on reboot)

Common usage:
  sudo nixos-rebuild switch        # Apply changes
  sudo nixos-rebuild boot          # Apply on next boot
  sudo nixos-rebuild test          # Test changes (revert on reboot)
  nixos-rebuild build              # Just build, don't activate
            """,
            tags=["nixos", "system", "configuration"],
            related_topics=["nix-rebuild", "system-management"],
            examples=[
                "nixos-rebuild switch",
                "nixos-rebuild test",
                "nixos-rebuild boot"
            ]
        )

        # Package Management
        self.add_entry(
            topic="nix-package-management",
            content="""
NixOS provides multiple ways to manage packages:

1. System packages (in configuration.nix):
   environment.systemPackages = [ pkgs.firefox pkgs.git ];

2. Per-user packages (imperative, temporary):
   nix-env -i firefox

3. Nix shell (temporary environment):
   nix shell nixpkgs#firefox

4. Flake packages:
   nix run github:user/repo#package

Best practice: Define packages in configuration.nix for consistency.
            """,
            tags=["packages", "nix", "installation"],
            related_topics=["system-packages", "nix-shell"],
            examples=[
                "environment.systemPackages = with pkgs; [ firefox ];",
                "nix-env -i firefox",
                "nix shell nixpkgs#firefox"
            ]
        )

        # NixQubes Integration
        self.add_entry(
            topic="nixqubes-containers",
            content="""
NixQubes provides isolated containers like Qubes OS:

Available containers:
- net: Handles all networking (auto-starts)
- work: For work applications (Firefox, LibreOffice)
- dev: For development tools (Git, Rust, Node.js)
- untrusted: Ephemeral container for testing

Managing containers:
  qubesctl start <name>     # Start a container
  qubesctl stop <name>      # Stop a container
  qubesctl shell <name>     # Open shell in container
  qubesctl run <name> cmd   # Run command in container

Containers provide security through isolation:
- Work cannot see Dev
- Untrusted is completely isolated
- All internet through Net container
            """,
            tags=["security", "containers", "nixqubes"],
            related_topics=["container-isolation", "network-security"],
            examples=[
                "qubesctl start work",
                "qubesctl shell dev",
                "qubesctl run work firefox"
            ]
        )

        # Configuration Files
        self.add_entry(
            topic="nixos-configuration",
            content="""
Main NixOS configuration file: /etc/nixos/configuration.nix

Structure:
{ config, pkgs, ... }:
{
  # System packages
  environment.systemPackages = [ ... ];

  # User management
  users.users.username = { ... };

  # Services
  services.openssh.enable = true;

  # Networking
  networking.hostname = "myhost";
  networking.interfaces.eth0.useDHCP = true;

  # Boot configuration
  boot.loader.grub.enable = true;

  # Import additional modules
  imports = [ ./hardware-configuration.nix ];
}

After editing, apply changes with:
  sudo nixos-rebuild switch
            """,
            tags=["configuration", "nixos", "system"],
            related_topics=["nixos-rebuild", "modules"],
            examples=[
                "{ config, pkgs, ... }:",
                "environment.systemPackages = with pkgs; [ ... ];",
                "services.openssh.enable = true;"
            ]
        )

        # AINIX Usage
        self.add_entry(
            topic="ainix-usage",
            content="""
AINIX combines help and control into one system.

Usage patterns:

1. Ask for help:
   ainix "How do I install a package?"
   → AINIX explains different methods

2. Execute a command:
   ainix install firefox
   → AINIX shows preview, asks for confirmation, executes safely

3. Get explanation:
   ainix --explain "What does nixos-rebuild switch do?"
   → AINIX provides detailed explanation

4. Use containers:
   ainix --container dev "Build my project"
   → AINIX runs in dev container, isolated from main system

Safety features:
- Preview by default (show what would happen)
- Confirmation required for dangerous operations
- Container execution for isolation
- Rollback support
- Command history tracking
            """,
            tags=["ainix", "usage", "help"],
            related_topics=["help-system", "control-system"],
            examples=[
                "ainix install firefox",
                "ainix 'How do I...?'",
                "ainix --explain command"
            ]
        )

    def add_entry(
        self,
        topic: str,
        content: str,
        tags: List[str],
        related_topics: List[str],
        examples: List[str]
    ):
        """Add a knowledge entry to the base."""
        self.knowledge[topic.lower()] = KnowledgeEntry(
            topic=topic,
            content=content,
            tags=tags,
            related_topics=related_topics,
            examples=examples
        )

    def search(self, query: str, limit: int = 3) -> List[KnowledgeEntry]:
        """Search for knowledge entries matching the query."""
        query_lower = query.lower()
        results = []

        for topic, entry in self.knowledge.items():
            # Match by topic
            if query_lower in topic:
                results.append(entry)
                continue

            # Match by tags
            if any(query_lower in tag.lower() for tag in entry.tags):
                results.append(entry)
                continue

            # Match by content (first 100 chars)
            if query_lower in entry.content.lower():
                results.append(entry)

        return results[:limit]

    def get(self, topic: str) -> Optional[KnowledgeEntry]:
        """Get a specific knowledge entry."""
        return self.knowledge.get(topic.lower())

    def suggest_related(self, topic: str, limit: int = 3) -> List[KnowledgeEntry]:
        """Suggest related topics."""
        entry = self.get(topic)
        if not entry:
            return []

        results = []
        for related_topic in entry.related_topics:
            related = self.get(related_topic)
            if related and related not in results:
                results.append(related)

        return results[:limit]

    def explain_command(self, command: str) -> str:
        """Provide explanation for a command."""
        explanations = {
            "nixos-rebuild": self.get("nixos-rebuild"),
            "nix-env": self.get("nix-package-management"),
            "qubesctl": self.get("nixqubes-containers"),
            "nix": self.get("nix-package-management"),
        }

        for cmd_prefix, entry in explanations.items():
            if command.startswith(cmd_prefix):
                return entry.content if entry else "No explanation available."

        return "No explanation available for this command."


if __name__ == "__main__":
    kb = HelpKnowledgeBase()

    # Test knowledge base
    test_queries = [
        "nixos",
        "packages",
        "containers",
        "rebuild"
    ]

    for query in test_queries:
        print(f"Query: {query}")
        results = kb.search(query)
        for entry in results:
            print(f"  Found: {entry.topic}")
            print(f"    Tags: {', '.join(entry.tags)}")
        print()

    # Test explanation
    print("Explanation for 'nixos-rebuild switch':")
    print(kb.explain_command("nixos-rebuild"))
