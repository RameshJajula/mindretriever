# mindretriever

Local code knowledge graph and token-efficient context retrieval for AI coding workflows.

[![PyPI version](https://img.shields.io/pypi/v/mindretriever)](https://pypi.org/project/mindretriever/)
[![Python](https://img.shields.io/pypi/pyversions/mindretriever)](https://pypi.org/project/mindretriever/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## What It Solves

Large codebases make LLM workflows noisy and expensive. Sending entire files to an assistant increases token usage, response time, and irrelevant context.

Instead of reading dozens of files for a single bug-fix question, `mindretriever` builds a local repo graph and returns only the most relevant code, docs, and schema fragments within a token budget.

`mindretriever` solves this by:

- Building a local graph of files, code symbols, imports, documents, and related artifacts
- Selecting task-relevant snippets for bug fixes, feature work, refactors, tests, and reviews
- Producing token-budgeted context packs instead of sending whole files
- Recording token and estimated input-cost savings per retrieval run

## Key Features

- Local-first architecture (no external indexing service required)
- Multi-language extraction across backend and frontend assets
- FastAPI service for automation and tool integration
- MCP server for native use in VS Code Copilot Chat and Cursor
- Incremental runs via file-hash cache
- Local SQLite history of runs, graph entities, and savings metrics

## Install

Basic install:

```bash
pip install mindretriever
```

Install with MCP support (recommended for VS Code/Cursor chat integration):

```bash
pip install "mindretriever[mcp]"
```

Verify CLI:

```bash
mindretriever --help
```

If command resolution fails on Windows:

```bash
python -m mindretriever --help
```

## Quick Start (CLI + API)

### 1) Analyze a repo

```bash
mindretriever run .
```

Expected output (example):

```text
Run complete
- Files: 182
- Nodes: 1248
- Edges: 3671
- Communities: 22
- Out dir: graphmind-out/
```

Windows-safe fallback:

```bash
python -m mindretriever run .
```

### 2) Start API

```bash
mindretriever-api
```

Windows-safe fallback:

```bash
python -m uvicorn mindretriever.api:app --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://localhost:8000/health
```

### 3) Create a context pack for a question

```bash
curl -X POST http://localhost:8000/api/context-pack \
  -H "Content-Type: application/json" \
  -d '{
    "run_id": 1,
    "task_type": "bug_fix",
    "query": "Why is checkout timing out after deployment?",
    "token_budget": 6000,
    "include_artifacts": true
  }'
```

Sample response (trimmed):

```json
{
  "tier": "snippets",
  "total_tokens": 1840,
  "code_snippets": [
    {
      "file_path": "backend/checkout/service.py",
      "start_line": 81,
      "end_line": 132,
      "reason": "contains_bug"
    }
  ],
  "recommended_next_steps": [
    "Run the failing test to reproduce",
    "Add breakpoints in the shown code"
  ],
  "token_savings": {
    "full_tokens": 26340,
    "pack_tokens": 1840,
    "saved_tokens": 24500,
    "savings_pct": 93.0
  }
}
```

### 4) Check savings proof

```bash
curl http://localhost:8000/api/savings
```

This returns:

- Per-query before/after token counts
- Estimated before/after input cost
- Aggregate total savings across all recorded queries

## Use Directly In VS Code And Cursor (MCP)

`mindretriever` includes an MCP server so chat assistants can call tools automatically while you ask normal questions.

Compatibility note: MCP currently runs from the legacy internal module path `graphmind.mcp_server`. Public package name and CLI remain `mindretriever`.

### VS Code setup

Create `.vscode/mcp.json`:

```json
{
  "servers": {
    "mindretriever": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "graphmind.mcp_server"],
      "cwd": "${workspaceFolder}",
      "env": {}
    }
  }
}
```

### Cursor setup

Create `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "mindretriever": {
      "command": "python",
      "args": ["-m", "graphmind.mcp_server"],
      "cwd": "${workspaceFolder}"
    }
  }
}
```

Then restart the editor and ask questions normally.

## MCP Tools

- `mindretriever_analyze(path=".")`
  - Builds graph and stores a run record
- `mindretriever_context(query, task_type="auto", run_id=None, token_budget=8000)`
  - Returns task-focused context pack
- `mindretriever_runs(limit=5)`
  - Lists recent analysis runs
- `mindretriever_savings(limit=20)`
  - Shows token and cost savings evidence from local history

## API Overview

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Service health |
| POST | `/api/run` | Run extraction + graph build |
| POST | `/api/upload` | Upload `.md`, `.docx`, `.sql` files |
| GET | `/api/runs` | List run history |
| GET | `/api/runs/{run_id}/graph` | Retrieve graph payload for a run |
| POST | `/api/context-pack` | Get token-aware context pack |
| GET | `/api/savings` | Show local token/cost savings history |

Upload field names:

- Preferred: `files`
- Compatibility alias: `file`

Example upload:

```bash
curl -F "files=@architecture.md" -F "files=@schema.sql" http://localhost:8000/api/upload
```

## Supported Inputs

### Implemented extraction

| Extension group | Coverage |
|---|---|
| `.py` | Python AST extraction |
| `.sql` | SQL schema extraction |
| `.js`, `.jsx`, `.ts`, `.tsx` | TypeScript/JavaScript semantic extraction |
| `.vue`, `.svelte` | Section-aware Vue/Svelte semantic extraction |
| `.css`, `.scss` | CSS selector extraction |
| `.md`, `.txt`, `.rst` | Heading/concept extraction |
| `.docx` | Semantic extraction |

### Basic detection only (deeper extraction planned)

| Extension group | Coverage |
|---|---|
| `.go`, `.java` | File detection and pipeline inclusion only |

### Vue/Svelte semantic coverage

- Script/template section-aware parsing
- Imports and component references
- Props (`defineProps`, `export let`)
- Emits (`defineEmits`)
- Stores (`$store` references)
- Slot usage (`<slot ...>`)

## CLI

```bash
mindretriever run [path] [--full]
```

- Default `path`: current directory
- Default mode: incremental
- `--full`: force full reprocessing

Legacy aliases kept for compatibility:

```bash
graphmind run .
graphmind-api
```

## Output Artifacts

Generated in `graphmind-out/`:

- `graph.json`: portable graph data
- `graph.html`: human-readable graph visualization
- `GRAPH_REPORT.md`: summary metrics
- `graphmind.db`: SQLite database (runs, nodes, edges, savings)
- `cache/file_hashes.json`: incremental cache
- `uploads/`: uploaded source documents
- `artifacts/`: cached context artifacts

## Token Savings Methodology

`mindretriever` records savings on each context request.

Definitions:

- `full_tokens`: tokens if all candidate project files were sent to the LLM
- `pack_tokens`: tokens in the generated context pack
- `saved_tokens = full_tokens - pack_tokens`
- `savings_pct = saved_tokens / full_tokens * 100`

Cost estimates:

- Uses input-token pricing table (default model: `gpt-4o`)
- Stored with each record and aggregated in `/api/savings` and `mindretriever_savings`

Token counting:

- Uses `tiktoken` when installed
- Falls back to `len(text) // 4` approximation otherwise

### Example benchmark (representative)

| Query | Full tokens | Packed tokens | Savings % | Files considered | Files included | Latency |
|---|---:|---:|---:|---:|---:|---:|
| Fix checkout timeout after deploy | 26,340 | 1,840 | 93.0% | 182 | 9 | 1.2s |
| Add coupon support to cart API | 24,110 | 2,210 | 90.8% | 182 | 11 | 1.4s |
| Refactor auth middleware tests | 19,870 | 2,460 | 87.6% | 182 | 14 | 1.1s |

## Development

```bash
git clone https://github.com/RameshJajula/mindretriever.git
cd mindretriever
pip install -e ".[dev,mcp]"
python -m pytest tests -q
```

Build and validate package:

```bash
python -m build
python -m twine check dist/*
```

See [PUBLISH.md](PUBLISH.md) for release steps.

## Project Structure

`mindretriever/` is the public package interface. `graphmind/` contains internal and legacy-compatible modules retained during migration.

```text
mindretriever/
  __init__.py
  __main__.py
  cli.py
  api.py
graphmind/
  api.py
  cli.py
  mcp_server.py
  token_counter.py
  pipeline.py
  detect.py
  db.py
  context_budget.py
  retrieval_planner.py
  prompt_templates.py
  extractors/
    python_ast.py
    sql_schema.py
    typescript_semantic.py
    vue_svelte_semantic.py
    text_semantic.py
    docx_semantic.py
  graph/
    builder.py
    analytics.py
  exporters/
    json_exporter.py
    html_exporter.py
```

## Compatibility Notes

- Python 3.10+
- SQLite is bundled with Python; no external DB required
- For Windows command resolution issues, use module invocation commands
- Legacy CLI aliases `graphmind` and `graphmind-api` remain available
- Output directory currently remains `graphmind-out/` for backward compatibility

## License

MIT. See [LICENSE](LICENSE).

## Links

- PyPI: https://pypi.org/project/mindretriever/
- Repository: https://github.com/RameshJajula/mindretriever
- Issues: https://github.com/RameshJajula/mindretriever/issues
