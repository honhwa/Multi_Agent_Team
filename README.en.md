# Officetool (Agent OS)

[中文 README](README.md)

[![Regression CI](https://github.com/jonhncatt/multi-agents-based-os/actions/workflows/regression-ci.yml/badge.svg?branch=main)](https://github.com/jonhncatt/multi-agents-based-os/actions/workflows/regression-ci.yml)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](requirements.txt)
[![FastAPI](https://img.shields.io/badge/FastAPI-app-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Officetool is a local **Agent OS-style** system with a stable kernel, formal business modules, tool/provider contracts, quality gates, and operational runbooks.

## What It Is

- `KernelHost` stays small and stable: load, dispatch, isolate, health, rollback.
- `office_module` is a business module, not the platform core.
- `research_module` is the second formal module and the current non-office reference module.
- Swarm MVP is implemented as a bounded module-local orchestration flow, not a kernel rewrite.
- Quality is guarded through pytest, gate evals, smoke layers, replay samples, platform metrics, and release runbooks.

## Quick Start

```bash
git clone https://github.com/jonhncatt/multi-agents-based-os.git
cd multi-agents-based-os
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
./run.sh
```

Main app: <http://127.0.0.1:8080>

Role-agent lab: 

```bash
./run-role-agent-lab.sh
```

Lab app: <http://127.0.0.1:8081>

## Screenshots

### Main app (8080)

![Kernel Robot home](docs/assets/screenshots/kernel_robot_home.png)

### Role-Agent Lab (8081)

![Role Agent Lab home](docs/assets/screenshots/role_agent_lab_home.png)

## Demo Paths

- baseline smoke: `python scripts/demo_minimal_agent_os.py --check`
- research module demo: `python scripts/demo_research_module.py --check`
- research Swarm demo: `python scripts/demo_research_swarm.py --check`

## Operations Entry

Start here if you want the current platform status, gate status, metrics summary, replay sample overview, and reporting template:

- [Platform Operations Overview](docs/operations/platform_operations_overview.md)
- [Platform Reporting Template](docs/operations/platform_reporting_template.md)
- [Quality Gates](docs/operations/quality_gates.md)
- [Smoke Matrix](docs/operations/smoke_matrix.md)

## Key Docs

- [Current Execution Path](docs/architecture/current_execution_path.md)
- [Platform Boundaries](docs/architecture/platform_boundaries.md)
- [Research Module](docs/modules/research_module.md)
- [Swarm Roadmap](docs/swarm-roadmap.md)
- [Swarm Demo Notes](docs/demo/research_swarm_demo.md)
- [Packages Boundary Guide](packages/README.md)

## Architecture Sketch

```mermaid
flowchart LR
    UI["Web UI / API"] --> Assemble["assemble_runtime()"]
    Assemble --> Kernel["KernelHost"]
    Kernel --> Registry["ModuleRegistry"]
    Kernel --> ToolBus["ToolBus"]

    Registry --> Office["office_module"]
    Registry --> Research["research_module"]
    Registry --> System["system_modules"]

    Office --> ToolRuntime["tool_runtime_module"]
    Research --> ToolRuntime
    ToolRuntime --> ProviderRegistry["ProviderRegistry"]

    ProviderRegistry --> Workspace["LocalWorkspaceProvider"]
    ProviderRegistry --> Web["HttpWebProvider"]

    Research --> Swarm["Module-local Swarm MVP"]
    Swarm --> Aggregator["merge / deduplicate / mark conflicts"]
```
