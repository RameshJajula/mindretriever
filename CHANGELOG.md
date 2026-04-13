# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-04-09

### Changed

- Renamed PyPI distribution from `graphmind-rj` to `mindretriever`.
- Added new primary CLI entry points:
  - `mindretriever`
  - `mindretriever-api`
- Added a new public module wrapper package: `mindretriever`.

### Compatibility

- Legacy command aliases remain available:
  - `graphmind`
  - `graphmind-api`
- Existing internal imports under `graphmind.*` continue to work.

## [0.1.3] - 2026-04-09

### Added

- Dedicated TypeScript semantic extraction for `.js`, `.jsx`, `.ts`, `.tsx`
  - Import relationship extraction
  - Symbol extraction: functions, classes, components, interfaces, type aliases
  - JSX component reference extraction
- Dedicated Vue/Svelte semantic extraction for `.vue`, `.svelte`
  - Script/template section-aware parsing
  - Import extraction
  - Vue `defineProps` and `defineEmits` signal extraction
  - Svelte `export let` prop extraction
  - Store reference extraction (`$store`)
  - Slot and component-tag extraction from templates
- Frontend stylesheet extraction improvements
  - CSS/SCSS selector extraction (`.class`, `#id`)
- Expanded test coverage for frontend and UI-framework extraction behavior

### Changed

- Upload endpoint compatibility improved: accepts both multipart field names `files` (preferred) and `file` (legacy examples).
- Frontend extensions are now included consistently across detection and context planning (`.tsx`, `.jsx`, `.css`, `.scss`, `.vue`, `.svelte`).
- README and usage docs updated for Windows-safe command fallbacks and accurate package naming.

### Fixed

- Removed deprecated UTC timestamp usage (`datetime.utcnow`) in API upload timestamps and database default timestamps.
- Cleaned duplicated/contradictory README sections to keep a single authoritative guide.

## [0.1.0] - 2026-04-08

### Added

- **Core Pipeline**: Multi-language extraction and graph building
  - Python AST extraction (functions, classes, methods)
  - SQL schema extraction (tables, columns, constraints)
  - DOCX semantic extraction (structure and concepts)
  - Markdown semantic extraction (headings and paragraphs)
  
- **Knowledge Graph**: NetworkX-based graph construction
  - Community detection via Louvain algorithm
  - Hub ranking by graph centrality
  - Incremental cache for unchanged files
  
- **FastAPI Backend**: 6+ REST endpoints
  - `/api/run` - Pipeline orchestration
  - `/api/upload` - File ingestion (.md, .docx, .sql)
  - `/api/runs` - Run history and browsing
  - `/api/runs/{run_id}/graph` - Graph retrieval
  - `/api/context-pack` - Optimized LLM context
  - `/health` - Service health check
  
- **SQL Persistence**: SQLAlchemy ORM with SQLite
  - RunRecord - Pipeline run metadata
  - NodeRecord - Graph node snapshots
  - EdgeRecord - Graph edge snapshots
  
- **Token Optimization Layer**: 60-80% token savings
  - Context Budget Engine (`context_budget.py`) - Priority-based token allocation
  - Retrieval Planner (`retrieval_planner.py`) - 3-tier context delivery
  - Prompt Templates (`prompt_templates.py`) - Task-specific LLM formats
  - Artifact Cache (extended `cache.py`) - Reusable summaries and contracts
  - Context Gating - Auto-detection of sufficient context
  
- **CLI**: Command-line interface
  - `graphmind run <path>` - Run on directory
  - `graphmind-api` - Start backend server
  
- **Frontend**: React + Vite dashboard
  - Run management interface
  - File upload handlers
  - Run history browser
  
- **Testing**: pytest test suite
  - Pipeline end-to-end tests
  - API endpoint tests
  - Extractor integration tests

### Fixed

- Regex escape sequences in security module (raw string literals)
- Frontend-backend CORS communication via Vite proxy
- Extraction deduplication across multiple extractors

### Known Limitations

- SQL extractor: Only CREATE TABLE parsing (no foreign keys yet)
- Graph visualization: JSON output only (HTML coming soon)
- Frontend: Dashboard UI only (interactive graph viewer in roadmap)

---

## Roadmap

### v0.2.0 - Planned

- [ ] Interactive graph visualization in React
- [ ] SQL JOIN and foreign key extraction
- [ ] Support for JSON and YAML files
- [ ] Performance profiling module
- [ ] GitHub integration for repo analysis

### v1.0.0 - Planned

- [ ] VS Code extension with embedded context packing
- [ ] Cursor IDE integration
- [ ] Multi-repository analysis
- [ ] Custom extractor plugins
- [ ] WebSocket support for real-time updates

