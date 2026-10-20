#!/usr/bin/env python3
"""
AINIX Control Executor: Safely executes commands with guardrails.
"""

import subprocess
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from enum import Enum

class ExecutionMode(Enum):
    DRY_RUN = "dry-run"
    PREVIEW = "preview"
    EXECUTE = "execute"
    SAFE = "safe"

@dataclass
class ExecutionResult:
    success: bool
    stdout: str
    stderr: str
    command: str
    mode: ExecutionMode
    rollback_available: bool = False

class SafeExecutor:
    DANGEROUS_OPS = {
        'rm', 'delete', 'remove', 'uninstall',
        'dd', 'format', 'mkfs', 'fdisk',
        'reboot', 'shutdown', 'halt',
        'nixos-rebuild switch'
    }

    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path)
        self.log_dir = Path.home() / ".local" / "share" / "ainix"
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        default = {
            "default_mode": "preview",
            "require_approval": True,
            "log_commands": True,
        }
        if config_path:
            try:
                with open(config_path) as f:
                    default.update(json.load(f))
            except (FileNotFoundError, json.JSONDecodeError):
                pass
        return default

    def _log(self, entry: dict):
        if not self.config.get("log_commands", True):
            return
        log_file = self.log_dir / "commands.log"
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def validate_command(self, command: str):
        lower = command.lower()
        for op in self.DANGEROUS_OPS:
            if op in lower:
                return False, f"Dangerous operation detected: {op}"
        if '`' in command or '$(' in command:
            return False, "Command substitution requires explicit approval"
        if any(x in command for x in ('&&', '||', ';')):
            return False, "Command chaining requires explicit approval"
        return True, None

    def preview_command(self, command: str) -> List[str]:
        lines = [
            "Would execute:",
            f"  {command}",
            "",
        ]
        # For nix/nixos commands, try a real dry-run if possible
        if command.strip().startswith(("nix ", "nixos-rebuild")):
            try:
                # Prefer a safe dry-run style where available
                dry = command
                if "nixos-rebuild" in command and "dry-run" not in command and "dry-build" not in command:
                    dry = command.replace("nixos-rebuild", "nixos-rebuild", 1) + " --dry-run"
                r = subprocess.run(
                    dry, shell=True, capture_output=True, text=True, timeout=60
                )
                if r.stdout or r.stderr:
                    lines.append("Dry-run output:")
                    lines.append((r.stdout or r.stderr)[:1500])
            except (subprocess.TimeoutExpired, Exception):
                pass
        return lines

    def execute_safe(self, command: str, mode: ExecutionMode = ExecutionMode.PREVIEW) -> ExecutionResult:
        ok, err = self.validate_command(command)
        if not ok:
            return ExecutionResult(False, "", err or "Validation failed", command, mode)

        if mode == ExecutionMode.PREVIEW:
            return ExecutionResult(
                True, "\n".join(self.preview_command(command)), "", command, mode
            )

        if mode == ExecutionMode.DRY_RUN:
            return ExecutionResult(
                True, f"Would run: {command}", "", command, mode
            )

        if mode in (ExecutionMode.EXECUTE, ExecutionMode.SAFE):
            return self._run(command, mode)

        return ExecutionResult(False, "", "Unknown mode", command, mode)

    def _run(self, command: str, mode: ExecutionMode) -> ExecutionResult:
        try:
            r = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=300
            )
            result = ExecutionResult(
                r.returncode == 0, r.stdout, r.stderr, command, mode
            )
            self._log({
                "time": datetime.utcnow().isoformat() + "Z",
                "command": command,
                "mode": mode.value,
                "success": result.success,
                "returncode": r.returncode,
            })
            return result
        except subprocess.TimeoutExpired:
            self._log({
                "time": datetime.utcnow().isoformat() + "Z",
                "command": command,
                "mode": mode.value,
                "success": False,
                "error": "timeout",
            })
            return ExecutionResult(False, "", "Command timed out", command, mode)
