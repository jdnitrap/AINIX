#!/usr/bin/env python3
"""
Tests for AINIX control executor.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from control.executor import SafeExecutor, ExecutionMode


def test_command_validation():
    """Test command validation."""
    executor = SafeExecutor()

    # Safe commands
    safe_commands = [
        "echo hello",
        "ls /tmp",
        "cat /etc/hostname",
    ]

    for cmd in safe_commands:
        is_valid, error = executor.validate_command(cmd)
        assert is_valid, f"Expected '{cmd}' to be valid, but got error: {error}"
        print(f"✓ Valid: {cmd}")

    print()

    # Dangerous commands
    dangerous_commands = [
        "rm -rf /",
        "dd if=/dev/zero of=/dev/sda",
        "format /dev/sda1",
    ]

    for cmd in dangerous_commands:
        is_valid, error = executor.validate_command(cmd)
        assert not is_valid, f"Expected '{cmd}' to be invalid"
        print(f"✓ Rejected (dangerous): {cmd}")
        print(f"  Reason: {error}")

    print()

    # Commands with substitution (requires approval)
    approval_commands = [
        "echo `whoami`",
        "echo $(date)",
        "cmd1 && cmd2",
    ]

    for cmd in approval_commands:
        is_valid, error = executor.validate_command(cmd)
        assert not is_valid, f"Expected '{cmd}' to require approval"
        print(f"✓ Requires approval: {cmd}")
        print(f"  Reason: {error}")


def test_preview_mode():
    """Test preview mode execution."""
    executor = SafeExecutor()

    query = "echo hello world"
    result = executor.execute_safe(query, mode=ExecutionMode.PREVIEW)

    assert result.success, "Preview mode should succeed"
    assert "Would execute" in result.stdout, "Preview should show what would be executed"
    assert result.mode == ExecutionMode.PREVIEW
    print(f"✓ Preview mode:")
    print(f"  Command: {query}")
    print(f"  Output preview: {result.stdout[:50]}...")


def test_dry_run_mode():
    """Test dry-run mode execution."""
    executor = SafeExecutor()

    query = "nix search firefox"
    result = executor.execute_safe(query, mode=ExecutionMode.DRY_RUN)

    assert result.success, "Dry-run for Nix should succeed"
    assert result.mode == ExecutionMode.DRY_RUN
    print(f"✓ Dry-run mode:")
    print(f"  Command: {query}")
    print(f"  Would execute: {result.stdout[:50]}...")


def test_dangerous_command_rejection():
    """Test that dangerous commands are rejected."""
    executor = SafeExecutor()

    dangerous = "rm -rf /"
    result = executor.execute_safe(dangerous, mode=ExecutionMode.PREVIEW)

    assert not result.success, "Dangerous command should be rejected"
    assert "Dangerous" in result.stderr or "dangerous" in result.stderr.lower()
    print(f"✓ Dangerous command rejected:")
    print(f"  Command: {dangerous}")
    print(f"  Error: {result.stderr}")


def test_container_execution():
    """Test container-based execution."""
    executor = SafeExecutor()

    query = "echo test"
    result = executor.execute_safe(
        query,
        container="untrusted",
        mode=ExecutionMode.SAFE
    )

    assert result.success, "Container execution should succeed"
    assert result.container_used == "untrusted"
    assert result.rollback_available
    print(f"✓ Container execution:")
    print(f"  Command: {query}")
    print(f"  Container: {result.container_used}")
    print(f"  Rollback available: {result.rollback_available}")


def run_all_tests():
    """Run all tests."""
    print("Running AINIX Executor Tests")
    print("=" * 50)

    test_command_validation()
    print()

    test_preview_mode()
    print()

    test_dry_run_mode()
    print()

    test_dangerous_command_rejection()
    print()

    test_container_execution()
    print()

    print("=" * 50)
    print("✅ All executor tests passed!")


if __name__ == "__main__":
    run_all_tests()
