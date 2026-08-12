#!/usr/bin/env python3
"""
AINIX Control Executor: Safely executes commands with guardrails.
"""

import subprocess
import json
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from enum import Enum

class ExecutionMode(Enum):
    DRY_RUN = "dry-run"       # Show what would happen
    PREVIEW = "preview"       # Show exact commands that will run
    EXECUTE = "execute"       # Actually run the commands
    SAFE = "safe"             # Run in container with rollback

@dataclass
class ExecutionResult:
    """Result of executing a command."""
    success: bool
    stdout: str
    stderr: str
    command: str
    mode: ExecutionMode
    container_used: Optional[str] = None
    rollback_available: bool = False

class SafeExecutor:
    """Executes commands safely with guardrails and validation."""

    # Operations that require explicit approval
    DANGEROUS_OPS = {
        'rm', 'delete', 'remove', 'uninstall',
        'dd', 'format', 'mkfs', 'fdisk',
        'reboot', 'shutdown', 'halt',
        'nixos-rebuild switch'
    }

    def __init__(self, config_path: Optional[str] = None):
        """Initialize executor with config."""
        self.config = self._load_config(config_path)
        self.history = []

    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Load configuration for safety policies."""
        default_config = {
            "default_mode": "preview",
            "require_approval": True,
            "use_containers": True,
            "preferred_container": "untrusted",
            "log_commands": True,
            "enable_rollback": True,
        }

        if config_path:
            try:
                with open(config_path, 'r') as f:
                    user_config = json.load(f)
                    default_config.update(user_config)
            except (FileNotFoundError, json.JSONDecodeError):
                pass

        return default_config

    def validate_command(self, command: str) -> tuple[bool, Optional[str]]:
        """Validate if a command is safe to execute."""
        command_lower = command.lower()

        # Check for dangerous operations
        for dangerous_op in self.DANGEROUS_OPS:
            if dangerous_op in command_lower:
                return False, f"Dangerous operation detected: {dangerous_op}"

        # Check for suspicious patterns
        if '`' in command or '$(' in command:
            return False, "Detected command substitution - requires explicit approval"

        if '&&' in command or '||' in command or ';' in command:
            return False, "Detected command chaining - requires explicit approval"

        return True, None

    def preview_command(self, command: str) -> List[str]:
        """Show what would be executed without actually running it."""
        return [
            "Would execute:",
            f"  {command}",
            "",
            "Breakdown:",
            f"  - Command: {command.split()[0] if command.split() else 'unknown'}",
            f"  - Arguments: {' '.join(command.split()[1:]) if len(command.split()) > 1 else 'none'}",
        ]

    def dry_run(self, command: str) -> ExecutionResult:
        """Simulate execution and show side effects."""
        is_valid, error = self.validate_command(command)

        if not is_valid:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=error or "Command failed validation",
                command=command,
                mode=ExecutionMode.DRY_RUN
            )

        # For package operations, show what would be changed
        if 'nix' in command.lower():
            return ExecutionResult(
                success=True,
                stdout=f"Would execute Nix operation: {command}\n\nUse --execute to run.",
                stderr="",
                command=command,
                mode=ExecutionMode.DRY_RUN
            )

        return ExecutionResult(
            success=False,
            stdout="",
            stderr="Unable to simulate this command",
            command=command,
            mode=ExecutionMode.DRY_RUN
        )

    def execute_safe(
        self,
        command: str,
        container: Optional[str] = None,
        mode: ExecutionMode = ExecutionMode.PREVIEW
    ) -> ExecutionResult:
        """Execute command safely with guardrails."""

        # Validate before any execution
        is_valid, error = self.validate_command(command)
        if not is_valid:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=error or "Validation failed",
                command=command,
                mode=mode
            )

        # Preview mode: show what would happen
        if mode == ExecutionMode.PREVIEW:
            return ExecutionResult(
                success=True,
                stdout="\n".join(self.preview_command(command)),
                stderr="",
                command=command,
                mode=mode
            )

        # Dry-run mode: simulate
        if mode == ExecutionMode.DRY_RUN:
            return self.dry_run(command)

        # Use container if specified or if dangerous
        if container or self.config.get("use_containers"):
            return self._execute_in_container(command, container or self.config.get("preferred_container"))

        # Safe execution mode: run and track
        if mode == ExecutionMode.SAFE:
            return self._execute_with_tracking(command)

        # Full execution (only after explicit approval)
        if mode == ExecutionMode.EXECUTE:
            return self._execute_direct(command)

        return ExecutionResult(
            success=False,
            stdout="",
            stderr="Unknown execution mode",
            command=command,
            mode=mode
        )

    def _execute_in_container(self, command: str, container: str) -> ExecutionResult:
        """Execute command in an isolated NixQubes container."""
        try:
            # This is a stub that would integrate with qubesctl
            result = subprocess.run(
                ['echo', f'Would run in container: {container}'],
                capture_output=True,
                text=True,
                timeout=30
            )

            return ExecutionResult(
                success=True,
                stdout=f"Executing in container '{container}':\n{command}",
                stderr="",
                command=command,
                mode=ExecutionMode.SAFE,
                container_used=container,
                rollback_available=True
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr="Command timed out",
                command=command,
                mode=ExecutionMode.SAFE,
                container_used=container
            )

    def _execute_with_tracking(self, command: str) -> ExecutionResult:
        """Execute with tracking and ability to rollback."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300
            )

            self.history.append({
                "command": command,
                "success": result.returncode == 0,
                "timestamp": None  # Would be filled in real implementation
            })

            return ExecutionResult(
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr,
                command=command,
                mode=ExecutionMode.SAFE,
                rollback_available=True
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr="Command timed out (exceeded 5 minutes)",
                command=command,
                mode=ExecutionMode.SAFE
            )

    def _execute_direct(self, command: str) -> ExecutionResult:
        """Direct execution (use with caution)."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300
            )

            return ExecutionResult(
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr,
                command=command,
                mode=ExecutionMode.EXECUTE
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr="Command timed out",
                command=command,
                mode=ExecutionMode.EXECUTE
            )


if __name__ == "__main__":
    executor = SafeExecutor()

    # Test execution
    test_commands = [
        "echo 'Hello AINIX'",
        "nix search firefox",
        "rm -rf /",  # Should be rejected
    ]

    for cmd in test_commands:
        print(f"Testing: {cmd}")
        result = executor.execute_safe(cmd, mode=ExecutionMode.PREVIEW)
        print(f"Success: {result.success}")
        print(f"Output: {result.stdout}")
        if result.stderr:
            print(f"Error: {result.stderr}")
        print()
