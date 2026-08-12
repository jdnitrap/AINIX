# AINIX Architecture

## Overview

AINIX is a unified system combining Help (advisory) and Control (execution) layers to provide intelligent assistance for NixOS.

```
┌─────────────────────────────────────────┐
│         User Interface (CLI)              │
│         ainix.py main script              │
└────────┬────────────────────────┬────────┘
         │                        │
         ▼                        ▼
    ┌────────────┐        ┌─────────────┐
    │   Router   │        │ Knowledge   │
    │ (Classify) │        │    Base     │
    └────────────┘        └─────────────┘
         │                        │
    Help or Control          Topic Search
         │                        │
         ▼                        ▼
    ┌────────────┐        ┌─────────────┐
    │ Executor   │        │ Help Layer  │
    │ (Execute)  │        │ (Advise)    │
    └────────────┘        └─────────────┘
         │
    ┌────┴────┬──────────┐
    ▼         ▼          ▼
  Local  Container  NixQubes
  Exec   Exec      Containers
```

## Core Components

### 1. Query Router (`core/router.py`)

**Purpose**: Classify user queries and route to appropriate handler

**Responsibilities**:
- Detect if query is a help request or control command
- Extract subject/topic from query
- Identify container requirements
- Parse command-line flags

**Key Features**:
- Help Keywords: "How", "What", "Why", "Explain", "Help"
- Control Keywords: "Install", "Build", "Deploy", "Update"
- Question Detection: Ends with `?` or starts with question word
- Container Extraction: Parse `--container <name>` flags

**Output**: `(QueryType, Subject)`
- `QueryType.HELP`: Advisory/information request
- `QueryType.CONTROL`: Execution/automation request
- `QueryType.EXPLAIN`: Detailed explanation request
- `QueryType.UNKNOWN`: Unable to classify

### 2. Executor (`control/executor.py`)

**Purpose**: Execute commands safely with guardrails

**Responsibilities**:
- Validate commands for dangerous operations
- Execute in appropriate mode (preview, dry-run, safe, direct)
- Use containers for isolation
- Track execution history
- Support rollback

**Execution Modes**:

```
┌──────────────┐  Show preview  ┌──────────────┐
│   PREVIEW    │  without       │   DRY_RUN    │
│ (Show what   │  execution     │   (Simulate  │
│  would run)  │◄────────────►  │   execution) │
└──────────────┘                └──────────────┘
       ▲                              ▲
       │                              │
       └──────────────┬───────────────┘
                      │
                      ▼
            ┌──────────────────┐
            │ Approval Gate    │
            │ (User confirms)  │
            └────────┬─────────┘
                     ▼
        ┌────────────────────────┐
        │  SAFE (Container)      │  or  │  EXECUTE (Direct)  │
        │  (Runs in container)   │      │  (Runs on system)  │
        └────────────────────────┘      │                    │
                                        └────────────────────┘
```

**Safety Features**:
- Dangerous operation detection
- Command substitution prevention
- Container isolation
- Timeout protection
- Execution tracking

### 3. Help Knowledge Base (`help/knowledge_base.py`)

**Purpose**: Provide advisory knowledge about NixOS and AINIX

**Responsibilities**:
- Store knowledge entries about topics
- Search knowledge base
- Suggest related topics
- Explain commands

**Knowledge Structure**:

```python
KnowledgeEntry {
  topic: str              # e.g., "nixos-rebuild"
  content: str            # Detailed explanation
  tags: List[str]         # e.g., ["nixos", "system"]
  related_topics: List    # References to other topics
  examples: List[str]     # Practical examples
}
```

**Query Types**:
- Topic search: "packages" → finds "nix-package-management"
- Tag search: "security" → finds related topics
- Content search: Looks in full content
- Command explanation: Specializes explanations

### 4. Main Interface (`ainix.py`)

**Purpose**: Unified CLI interface

**Flow**:

```
User Input
    │
    ▼
Parse Arguments
    │
    ▼
Classify Query (Router)
    │
    ├─► HELP ──────────► Knowledge Base ──► Display advice
    │
    ├─► EXPLAIN ───────► Knowledge Base ──► Display explanation
    │
    └─► CONTROL ───────► Executor ────────► Execute safely
         │
         ├─► Validate
         ├─► Preview/Dry-Run
         └─► Execute (with approval)
```

## Data Flow

### Help Query Flow

```
User: "How do I install a package?"
  │
  ▼
Router: Classify as HELP
  │
  ▼
Knowledge Base: Search "install" and "package"
  │
  ▼
Get: KnowledgeEntry(topic="nix-package-management")
  │
  ▼
Display: Explanation + Examples
```

### Control Query Flow

```
User: "install firefox"
  │
  ▼
Router: Classify as CONTROL, subject="firefox"
  │
  ▼
Executor: Validate command "install firefox"
  │
  ├─► Safe? NO ──► Show: "Dangerous operation detected"
  │
  └─► Safe? YES ──► Preview mode
        │
        ▼
      Show: "Would execute: install firefox"
        │
        ▼
      User: --execute
        │
        ▼
      Check: Use container?
        │
        ├─► YES ──► Execute in NixQubes container
        │
        └─► NO ──► Execute directly (with approval)
```

## Integration Points

### 1. NixQubes Containers

AINIX uses NixQubes for isolation:

```nix
containers = {
  net: {
    autoStart = true;
    privateNetwork = false;
    # Handles all networking
  };
  
  work: {
    autoStart = false;
    # Office/work apps
  };
  
  dev: {
    autoStart = false;
    # Development tools
  };
  
  untrusted: {
    autoStart = false;
    ephemeral = true;
    # Testing, auto-destroyed
  };
}
```

**Command Execution in Containers**:

```bash
qubesctl shell <container>           # Interactive shell
qubesctl run <container> <command>   # Run command
qubesctl start <container>           # Start container
qubesctl stop <container>            # Stop container
```

### 2. NixOS Module Integration

AINIX module configuration:

```nix
services.ainix = {
  enable = true;
  enableNixQubesIntegration = true;
  enableLocalLearning = true;
  
  settings = {
    execution.default_mode = "preview";
    containers.preferred_container = "untrusted";
    safety.enable_rollback = true;
  };
}
```

### 3. Learning System

Tracks usage patterns:

```
Command Execution
    │
    ├─► Success ──► Store in learning DB
    │              (build cache, patterns)
    │
    └─► Failure ──► Analyze error
                   (what to avoid)
                   │
                   ▼
                Record pattern
```

## Configuration

### Config Hierarchy

```
1. Built-in defaults (executor.py)
2. User config file (~/.config/ainix.json)
3. System config (/etc/ainix/config.json)
4. Runtime flags (--container, --execute)
```

### Key Settings

```json
{
  "execution": {
    "default_mode": "preview|dry-run|safe|execute",
    "require_approval": true,
    "use_containers": true
  },
  
  "containers": {
    "enabled": true,
    "preferred_container": "untrusted|work|dev|net"
  },
  
  "safety": {
    "enable_rollback": true,
    "dangerous_operations_require_approval": true,
    "log_commands": true,
    "timeout_seconds": 300
  },
  
  "learning": {
    "enabled": true,
    "store_successful_commands": true
  }
}
```

## Extension Points

### 1. Adding New Knowledge

Edit `help/knowledge_base.py`:

```python
self.add_entry(
  topic="my-topic",
  content="Detailed explanation",
  tags=["tag1", "tag2"],
  related_topics=["other-topic"],
  examples=["example 1", "example 2"]
)
```

### 2. Custom Execution Modes

Extend `control/executor.py`:

```python
def execute_custom(self, command: str) -> ExecutionResult:
    # Custom validation
    # Custom execution logic
    # Custom result handling
    pass
```

### 3. Router Extensions

Add keywords to `core/router.py`:

```python
CONTROL_KEYWORDS.add("mynewcommand")
HELP_KEYWORDS.add("mynewkeyword")
```

## Error Handling

### Validation Errors

```
Command Validation
  │
  ├─► Dangerous? ──► Reject with reason
  │
  ├─► Substitution? ──► Flag for approval
  │
  └─► Unknown? ──► Warn, suggest alternatives
```

### Execution Errors

```
Execution
  │
  ├─► Timeout ──► Kill process, report
  │
  ├─► Non-zero exit ──► Log error, suggest help
  │
  └─► Permission denied ──► Suggest sudo/container
```

## Performance Characteristics

| Operation | Time | Notes |
|-----------|------|-------|
| Query classification | <1ms | Fast regex matching |
| Knowledge search | 10-50ms | Full-text search |
| Preview generation | <1ms | No execution |
| Dry-run simulation | 100-500ms | Depends on command |
| Container startup | 2-5s | NixOS container boot |
| Direct execution | Variable | Depends on command |

## Security Model

### Threat Model

1. **Malicious input**: Prevented by validation
2. **Container escape**: Mitigated by NixQubes isolation
3. **Privilege escalation**: Limited by user permissions
4. **Command injection**: Prevented by parsing
5. **Data leakage**: Containers are isolated

### Trust Boundaries

```
User (trusted)
  │
  ▼
AINIX CLI (validated input)
  │
  ▼
Router/Executor (guardrails)
  │
  ├─► Knowledge Base (read-only)
  │
  ├─► Config (user-controlled)
  │
  └─► Execution (sandboxed)
       │
       ├─► Container (NixQubes isolated)
       │
       └─► Direct (requires approval)
```

## Future Enhancements

1. **AI Integration**: Use LLM for better classification
2. **GUI Mode**: Web interface for AINIX
3. **Remote Execution**: Execute on remote NixOS systems
4. **Plugin System**: Custom handlers and extensions
5. **Advanced Learning**: ML-based pattern recognition
6. **Cloud Sync**: Sync learning data across machines

## References

- NixOS: https://nixos.org/
- Qubes OS: https://www.qubes-os.org/
- systemd-nspawn: https://www.freedesktop.org/software/systemd/man/systemd-nspawn.html
