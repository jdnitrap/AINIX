#!/usr/bin/env python3
"""
Tests for AINIX control executor.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from control.executor import SafeExecutor, ExecutionMode


def test_command_validation():
    executor = SafeExecutor()

    safe_commands = [
        "echo hello",
        "ls /tmp",
        "nix search firefox",
    ]

    for cmd in safe_commands:
        is_valid, error = executor.validate_command(cmd)
        assert is_valid, f"Expected '{cmd}' to be valid, but got error: {error}"
        print(f"✓ Valid: {cmd}")

    dangerous_commands = [
        "rm -rf /",
        "dd if=/dev/zero of=/dev/sda",
        "sudo nixos-rebuild switch",
    ]

    for cmd in dangerous_commands:
        is_valid, error = executor.validate_command(cmd)
        assert not is_valid, f"Expected '{cmd}' to be invalid"
        print(f"✓ Rejected: {cmd}")


def test_preview_mode():
    executor = SafeExecutor()

    query = "install firefox"
    result = executor.execute_safe(query, mode=ExecutionMode.PREVIEW)

    assert result.success
    assert "nix profile add" in result.stdout
    assert "Preview never changes the system" in result.stdout
    assert result.mode == ExecutionMode.PREVIEW
    print("✓ Preview mode for install")


def test_dry_run_mode():
    executor = SafeExecutor()

    query = "echo hello"
    result = executor.execute_safe(query, mode=ExecutionMode.DRY_RUN)

    assert result.success
    assert "Would run" in result.stdout
    print("✓ Dry-run mode")


def run_all_tests():
    print("Running AINIX Executor Tests")
    print("=" * 50)
    test_command_validation()
    print()
    test_preview_mode()
    print()
    test_dry_run_mode()
    print()
    print("=" * 50)
    print("✅ All executor tests passed!")


if __name__ == "__main__":
    run_all_tests()
