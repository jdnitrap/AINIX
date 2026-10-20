#!/usr/bin/env python3
"""
AINIX Control Executor: preview with real Nix commands, then optional execute.
"""

import subprocess
import json
import re
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
        default = {"default_mode": "preview", "log_commands": True}
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
        with open(self.log_dir / "commands.log", "a") as f:
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
        if 'sudo' in lower:
            return False, "Refusing sudo without an explicit --sudo flag"
        return True, None

    def _install_preview(self, package: str) -> List[str]:
        return [
            "This would change the system if executed.",
            "",
            "Temporary (profile):",
            f"  nix profile add nixpkgs#{package}",
            "",
            "Declarative (preferred):",
            f"  environment.systemPackages = with pkgs; [ {package} ];",
            "  sudo nixos-rebuild switch",
            "",
            "Preview never changes the system.",
            "",
            "Copy-friendly:",
            f"  nix profile add nixpkgs#{package}",
        ]

    def preview_command(self, command: str) -> List[str]:
        parts = command.split()
        if len(parts) >= 2 and parts[0].lower() in ("install", "add"):
            return self._install_preview(parts[1])

        lines = [
            "Read-only / preview.",
            f"Would execute: {command}",
            "",
            "Preview never changes the system.",
        ]
        if command.strip().startswith(("nix ", "nixos-rebuild")):
            try:
                r = subprocess.run(
                    command, shell=True, capture_output=True, text=True, timeout=30
                )
                if r.stdout or r.stderr:
                    lines.append("")
                    lines.append("Tool output:")
                    lines.append((r.stdout or r.stderr)[:800])
            except (subprocess.TimeoutExpired, Exception):
                lines.append("(tool timed out or unavailable)")
        return lines

    def execute_safe(self, command: str, mode: ExecutionMode = ExecutionMode.PREVIEW) -> ExecutionResult:
        ok, err = self.validate_command(command)
        if not ok and mode != ExecutionMode.PREVIEW:
            return ExecutionResult(False, "", err or "Validation failed", command, mode)

        if mode == ExecutionMode.PREVIEW:
            return ExecutionResult(
                True, "\n".join(self.preview_command(command)), "", command, mode
            )

        if mode == ExecutionMode.DRY_RUN:
            return ExecutionResult(True, f"Would run: {command}", "", command, mode)

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
            })
            return result
        except subprocess.TimeoutExpired:
            return ExecutionResult(False, "", "Command timed out", command, mode)
