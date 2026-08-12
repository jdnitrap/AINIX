#!/usr/bin/env python3
"""
AINIX Query Router: Routes queries between Help and Control layers.
"""

import re
from enum import Enum
from typing import Optional, Tuple

class QueryType(Enum):
    HELP = "help"           # Advice, explanation, guidance
    CONTROL = "control"     # Execution, automation, state change
    EXPLAIN = "explain"     # Deep explanation of a command
    UNKNOWN = "unknown"

class QueryRouter:
    """Routes user queries to appropriate handlers."""

    # Control keywords that indicate execution intent
    CONTROL_KEYWORDS = {
        'install', 'uninstall', 'remove', 'update', 'upgrade',
        'build', 'rebuild', 'switch', 'run', 'start', 'stop',
        'enable', 'disable', 'configure', 'create', 'delete',
        'deploy', 'apply', 'commit', 'push', 'pull', 'clone'
    }

    # Help keywords that indicate information seeking
    HELP_KEYWORDS = {
        'how', 'what', 'why', 'when', 'where', 'explain',
        'help', 'show', 'list', 'find', 'search', 'guide',
        'describe', 'define', 'tell', 'teach', 'learn'
    }

    # Question patterns
    QUESTION_PATTERN = re.compile(r'^\s*[Hh]ow\s+|^\s*[Ww]hat\s+|^\s*[Ww]hy\s+|\?$')

    @staticmethod
    def classify(query: str) -> Tuple[QueryType, Optional[str]]:
        """
        Classify a query as Help or Control.

        Returns:
            (query_type, extracted_subject)
        """
        query_lower = query.lower().strip()

        # Check for explicit explanation request
        if '--explain' in query or 'explain' in query_lower[:20]:
            return QueryType.EXPLAIN, None

        # Check if it's a question (ends with ? or starts with question word)
        if QueryRouter.QUESTION_PATTERN.search(query):
            return QueryType.HELP, None

        # Extract first meaningful word
        words = re.findall(r'\b\w+\b', query_lower)
        if not words:
            return QueryType.UNKNOWN, None

        first_word = words[0]

        # If first word is a control keyword, route to control
        if first_word in QueryRouter.CONTROL_KEYWORDS:
            subject = ' '.join(words[1:3]) if len(words) > 1 else None
            return QueryType.CONTROL, subject

        # If first word is a help keyword, route to help
        if first_word in QueryRouter.HELP_KEYWORDS:
            subject = ' '.join(words[1:3]) if len(words) > 1 else None
            return QueryType.HELP, subject

        # If it contains control keywords, route to control
        for word in words:
            if word in QueryRouter.CONTROL_KEYWORDS:
                return QueryType.CONTROL, first_word

        # If it contains help keywords, route to help
        for word in words:
            if word in QueryRouter.HELP_KEYWORDS:
                return QueryType.HELP, first_word

        # Default: if it looks like a command (no spaces initially), try control
        if len(query) < 50 and ' ' not in query.split()[0] if query.split() else False:
            return QueryType.CONTROL, query

        return QueryType.UNKNOWN, None

    @staticmethod
    def should_use_container(query: str, query_type: QueryType) -> bool:
        """Determine if query should execute in a container."""
        if query_type != QueryType.CONTROL:
            return False

        # Dangerous operations should use containers
        dangerous_ops = [
            'install', 'uninstall', 'remove', 'update', 'upgrade',
            'delete', 'rebuild', 'deploy', 'apply'
        ]

        query_lower = query.lower()
        return any(op in query_lower for op in dangerous_ops)

    @staticmethod
    def extract_container_name(query: str) -> Optional[str]:
        """Extract container name from query if specified."""
        # Pattern: --container <name> or -c <name>
        patterns = [
            r'--container\s+(\w+)',
            r'-c\s+(\w+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, query)
            if match:
                return match.group(1)

        return None


if __name__ == "__main__":
    # Test the router
    test_queries = [
        "How do I install Rust?",
        "install firefox",
        "What's the difference between packages and modules?",
        "rebuild my system",
        "Explain what nixos-rebuild switch does",
        "--explain update nixpkgs",
    ]

    for query in test_queries:
        query_type, subject = QueryRouter.classify(query)
        container = QueryRouter.extract_container_name(query)
        use_container = QueryRouter.should_use_container(query, query_type)

        print(f"Query: {query}")
        print(f"  Type: {query_type.value}")
        print(f"  Subject: {subject}")
        print(f"  Use Container: {use_container}")
        print(f"  Container: {container}")
        print()
