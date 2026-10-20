# AINIX: AI-Native NixOS Integration

AINIX is an intelligent assistant for NixOS that combines **Help** (advisory, knowledge) and **Control** (execution, automation) into a single unified system.

## Architecture

```
AINIX = Help System + Control Agent

User Query
├─ Is it a question? → Help: explain, advise, guide
└─ Is it a command? → Control: execute, verify, learn
```

## Core Principles

1. **Help First**: Explain what's happening
2. **Control Second**: Execute safely with guardrails
3. **Learn Always**: Remember what worked/failed
4. **Safe by Default**: Preview mode, validation, and optional rollback

## Components

### Help Layer (`help/`)
- Knowledge base about NixOS, packages, configurations
- Advisory queries ("how do I...?")
- Explanations of Nix concepts
- Recommendations and best practices

### Control Layer (`control/`)
- Command execution with safety checks
- Package installation and management
- Configuration rebuilds
- System state management

### Core System (`core/`)
- Query routing (help vs control)
- Safety guardrails and validation
- Local learning/memory system

### Configuration (`config/`)
- AINIX settings and policies
- Allowed operations whitelist/blacklist
- Learning preferences

## Usage

```bash
# Ask for help
ainix "How do I install a package?"

# Execute a command (with guardrails)
ainix install firefox

# Show reasoning
ainix --explain "What would happen if I..."
```

## Safety Features

1. **Dry-run / Preview by Default**: Show what would happen before doing it
2. **Rollback Support**: Track system state, enable rollback
3. **Permission Model**: Different permission levels for different operations
4. **Audit Trail**: Log all executed commands
5. **Dangerous operation detection**: Blocks risky commands unless explicitly approved

## Learning System

AINIX learns from:
- Successful operations (build cache, configuration patterns)
- Failed operations (what to avoid, error patterns)
- User preferences (which solutions you prefer)
- Performance metrics (which approaches are fastest)

## Current Status

- Help layer: Foundation
- Control layer: Under development
- Core routing: Planned
- Learning system: Planned

## Next Steps

1. Implement query classification (help vs control)
2. Build help knowledge base
3. Implement control execution with guards
4. Add learning/memory system
