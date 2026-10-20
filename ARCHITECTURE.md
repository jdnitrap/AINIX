# AINIX Architecture

## Overview

AINIX is a unified system combining Help (advisory) and Control (execution) layers to provide intelligent assistance for NixOS.

```
┌────────────────────────────────────────┐
│         User Interface (CLI)              │
│         ainix.py main script              │
└───────┬─────────────────┬───────────┘
         │                        │
         ▼                        ▼
    ┌───────────┐        ┌────────────┐
    │   Router   │        │ Knowledge   │
    │ (Classify) │        │    Base     │
    └───────────┘        └────────────┘
         │                        │
    Help or Control          Topic Search
         │                        │
         ▼                        ▼
    ┌───────────┐        ┌────────────┐
    │ Executor   │        │ Help Layer  │
    │ (Execute)  │        │ (Advise)    │
    └───────────┘        └────────────┘
         │
    ┌────┤
    ▼
  Local Exec
  (with tracking)
```

## Core Components

### 1. Query Router (`core/router.py`)

Classifies user queries as Help, Control, or Explain and routes them to the right handler.

### 2. Executor (`control/executor.py`)

Safely executes commands with:
- Dangerous operation detection
- Preview / dry-run / safe / execute modes
- Timeout protection
- Execution tracking and optional rollback

### 3. Help Knowledge Base (`help/knowledge_base.py`)

Stores and searches advisory knowledge about NixOS and AINIX.

### 4. Main Interface (`ainix.py`)

Unified CLI that ties the router, knowledge base, and executor together.

## Data Flow

**Help query**
```
User: "How do I install a package?"
  → Router classifies as HELP
  → Knowledge Base search
  → Display explanation + examples
```

**Control query**
```
User: "install firefox"
  → Router classifies as CONTROL
  → Executor validates
  → Preview by default
  → Only runs on explicit --execute
```

## Safety Model

- Preview / dry-run by default
- Dangerous commands require explicit approval
- Command substitution and chaining are flagged
- Timeouts and execution history
- Optional rollback tracking

## Configuration

Defaults live in the executor; user config can override via `~/.config/ainix.json` or the system module.

## Future Enhancements

- Better query classification (optionally with an LLM)
- GUI / web interface
- Plugin system
- Stronger local learning
