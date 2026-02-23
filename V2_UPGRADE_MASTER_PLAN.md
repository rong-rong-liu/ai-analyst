# AI Analyst V2 -- Upgrade Master Plan

**Synthesized by:** Chief Architect (from 5 expert Round 2 plans + debate resolutions)
**Date:** 2026-02-22
**Scope:** 9 waves, ~90 tasks, transforming AI Analyst from static toolkit to learning system
**Source plans:** Knowledge Systems Architect, Python Infrastructure Engineer, Pipeline & DAG Engineer, UX & Onboarding Designer, Quality & Testing Strategist

---

## 1. Executive Summary

This plan transforms AI Analyst from a static tutorial toolkit into a persistent learning system. The upgrade replaces NovaMart sample data with interview-first onboarding, adds a 7-subsystem knowledge architecture that persists across sessions, builds a self-learning loop for SQL corrections and methodology feedback, introduces entity disambiguation, query archaeology, YAML-driven brand theming, an enhanced DAG pipeline engine, and 4-layer programmatic validation with confidence scoring.

### Key Decisions Made During Planning

1. **DuckDB stays** -- it is the local SQL engine, not a developer toy. Only the NovaMart silent fallback is removed.
2. **Phase 5 (dev context) extracted** from the interview to a standalone `/setup-dev-context` command. Interview is 4 phases max.
3. **Wave 0 split into 0A/0B** -- test foundation first (0A), then NovaMart deletion (0B). Prevents CI breakage.
4. **Python 3.10+ floor** -- matches pyproject.toml, unlocks modern type hints and match/case.
5. **Chart fan-out is sequential in V2** -- parallel execution deferred to V2.1. Per-beat state tracking still ships.
6. **Entity index uses content-hash rebuild** with session-level caching. Async post-interview generation.
7. **Feedback capture is a pre-router interceptor** -- runs before Question Router on every message.
8. **Pipeline state migrates to agent-name keys** with v1 auto-migration and backup.
9. **Demo datasets deferred to V2.1** -- "no data" path offers CSV upload, not curated samples.
10. **Notion ingest deferred to Wave 6** -- Phase 3 uses manual term collection only.
11. **Query archaeology auto-capture added to Wave 3** -- Archive Analysis captures proven SQL patterns.
12. **Learnings: 6 categories defined in index, files created on demand** -- zero overhead for unused categories.

### Total Scope

- **Files created:** ~65 new files (Python modules, tests, skills, schemas, fixtures, scripts)
- **Files modified:** ~25 existing files
- **Files deleted:** ~60+ files (NovaMart data, fallbacks, setup guides, seed org)
- **Python modules:** 20 new + 4 enhanced
- **Test files:** 21 files, ~244 test cases
- **Skills:** 8 new + 6 enhanced
- **Agents:** 1 new (comms-drafter)
- **Estimated effort:** 60-80 hours across all waves

---

## 2. Wave Structure

| Wave | Name | Task Count | Key Deliverables | Dependencies |
|------|------|-----------|------------------|--------------|
| 0A | Test Foundation | 10 | conftest.py, fixtures, CI update, file_helpers.py, __init__.py files, existing test migration | None |
| 0B | NovaMart Removal | 12 | Delete fallbacks/, setup/, NovaMart data, seed org; reset configs; clean references | 0A |
| 1 | Interview Onboarding | 6 | /setup skill (4 phases), first-run-welcome rewrite, setup-state schema, /setup reset | 0B |
| 2 | Knowledge Infrastructure | 24 | 7 subsystem schemas, 5 validation modules + tests, 3 infrastructure helpers + tests, knowledge bootstrap enhancement | 0B |
| 3 | Self-Learning Loop | 15 | Feedback capture, log correction, archaeology skill + auto-capture, entity resolver, question router enhancement, pre-flight in agents/skills, helper modules + tests | 1, 2 |
| 4 | Pipeline Engine | 10 | DAG walker v2, OR-deps, non-critical degradation, per-run dirs, fan-out, comms-drafter, state migration, /runs lifecycle | 2 |
| 5 | Brand Theming (optional) | 7 | _base.yaml, theme_loader, chart_palette, lint scripts, example brand, chart_helpers integration | 0B |
| 6 | Advanced Capabilities | 5 | /setup-dev-context, /business skill, notion-ingest (deferred), context_loader, docs | 1, 3 |
| 7 | CLAUDE.md & Verification | 8 | Skills table, agents table, system variables, rules 13-15, data section rewrite, e2e verification | All |

---

## 3. Detailed Waves

### Wave 0A: Test Foundation

**Goal:** Build the test infrastructure so that CI passes without NovaMart data, enabling safe deletion in 0B.

**Parallelism notes:** Tasks W0A.1-W0A.4 can run concurrently (they create independent files). W0A.5-W0A.6 depend on W0A.1-W0A.2. W0A.7-W0A.9 can run in parallel after W0A.4.

| ID | Description | Action | File Paths | Dependencies | Owner | Verify |
|----|-------------|--------|------------|--------------|-------|--------|
| W0A.1 | Create helpers package init | BUILD | `helpers/__init__.py` | -- | Python Eng | `python -c "import helpers"` |
| W0A.2 | Create tests package init | BUILD | `tests/__init__.py` | -- | Quality | `python -c "import tests"` |
| W0A.3 | Create shared pytest fixtures and conftest | BUILD | `tests/conftest.py` (~200 lines) | -- | Quality | `pytest --collect-only tests/conftest.py` |
| W0A.4 | Create synthetic fixture data | BUILD | `tests/fixtures/synthetic_orders.csv`, `tests/fixtures/synthetic_users.csv`, `tests/fixtures/synthetic_products.csv`, `tests/fixtures/entity_index.yaml`, `tests/fixtures/org_manifest.yaml` | -- | Quality | Files exist and parse |
| W0A.5 | Build file_helpers.py foundation module | BUILD | `helpers/file_helpers.py` (~120 lines) | W0A.1 | Python Eng | `python -c "from helpers.file_helpers import atomic_write_yaml; print('OK')"` |
| W0A.6 | Write file_helpers tests | BUILD | `tests/test_file_helpers.py` (~100 lines) | W0A.5 | Quality | `pytest tests/test_file_helpers.py -v` |
| W0A.7 | Rewrite test_validation_e2e.py (remove NovaMart dep) | ENHANCE | `tests/test_validation_e2e.py` (~150 lines) | W0A.3, W0A.4 | Quality | `pytest tests/test_validation_e2e.py -v` |
| W0A.8 | Rewrite test_cross_dataset.py as test_knowledge_infrastructure.py | ENHANCE | `tests/test_knowledge_infrastructure.py` (~120 lines) | W0A.3, W0A.4 | Quality | `pytest tests/test_knowledge_infrastructure.py -v` |
| W0A.9 | Migrate existing tests to pytest conventions (Gap 8) | ENHANCE | `tests/test_lineage_tracker.py`, `tests/test_synthesize_insights.py`, `tests/test_multi_warehouse.py` | W0A.3 | Quality | `pytest tests/test_lineage_tracker.py tests/test_synthesize_insights.py tests/test_multi_warehouse.py -v` |
| W0A.10 | Update CI and pyproject.toml | ENHANCE | `.github/workflows/ci.yml`, `pyproject.toml` | W0A.6 | Quality | CI passes with Python 3.10, 3.11, 3.12 matrix; `requires-python = ">=3.10"` |

**Gate:** `pytest tests/ -v` passes on CI without any NovaMart data present.

---

### Wave 0B: NovaMart Removal

**Goal:** Delete all tutorial scaffolding and NovaMart artifacts, resetting the system to a clean slate for interview-first onboarding.

**Parallelism notes:** W0B.1-W0B.5 are independent deletions and can run concurrently. W0B.6-W0B.7 are config resets, also independent. W0B.8-W0B.9 depend on all deletions being complete.

| ID | Description | Action | File Paths | Dependencies | Owner | Verify |
|----|-------------|--------|------------|--------------|-------|--------|
| W0B.1 | Remove tutorial fallback files | REMOVE | `fallbacks/` (entire directory, ~26 files) | W0A.10 | UX | `ls fallbacks/ 2>/dev/null && echo "FAIL" \|\| echo "PASS"` |
| W0B.2 | Remove tutorial setup guides | REMOVE | `setup/prerequisites.md`, `setup/claude-code-install.md`, `setup/motherduck-setup.md`, `setup/troubleshooting.md`, `setup/mcp-config.md`, `setup/` directory | W0A.10 | UX | `ls setup/ 2>/dev/null && echo "FAIL" \|\| echo "PASS"` |
| W0B.3 | Remove NovaMart download script and checksums | REMOVE | `scripts/download-data.sh`, `data/checksums.sha256` | W0A.10 | UX | Files no longer exist |
| W0B.4 | Remove NovaMart dataset brain | REMOVE | `.knowledge/datasets/novamart/` (entire directory, ~12 files). Add `.knowledge/datasets/.gitkeep` | W0A.10 | Knowledge | `ls .knowledge/datasets/novamart/ 2>/dev/null && echo "FAIL" \|\| echo "PASS"` |
| W0B.5 | Remove fictional organization seed data | REMOVE | `.knowledge/organizations/_seed/` (entire directory, ~14 files) | W0A.10 | Knowledge | `ls .knowledge/organizations/_seed/ 2>/dev/null && echo "FAIL" \|\| echo "PASS"` |
| W0B.6 | Reset active.yaml to empty state | ENHANCE | `.knowledge/active.yaml`, `data_sources.yaml` | W0A.10 | Knowledge | `grep "active_dataset: null" .knowledge/active.yaml` |
| W0B.7 | Remove silent fallback chain from data helpers | ENHANCE | `helpers/data_helpers.py`, `helpers/error_helpers.py`, `helpers/connection_manager.py` | W0A.10 | Python Eng | `grep -ri "novamart" helpers/data_helpers.py helpers/error_helpers.py helpers/connection_manager.py \| wc -l` returns 0 |
| W0B.8 | Remove NovaMart CSV data files | REMOVE | `data/novamart/` (entire directory -- CSV files) | W0A.10 | Knowledge | `ls data/novamart/ 2>/dev/null && echo "FAIL" \|\| echo "PASS"` |
| W0B.9 | Delete MCP config example | REMOVE | `.claude/mcp.json.example` | W0A.10 | UX | File no longer exists |
| W0B.10 | Clean NovaMart references from skills, agents, templates, docs | ENHANCE | `.claude/skills/knowledge-bootstrap/skill.md`, `.claude/skills/run-pipeline/skill.md`, `.claude/skills/datasets/skill.md`, `.claude/skills/metric-spec/skill.md`, `agents/source-tieout.md`, `agents/deck-creator.md`, `helpers/chart_helpers.py`, `README.md`, `.knowledge/README.md` | W0B.1-W0B.9 | UX | `grep -ri "novamart" CLAUDE.md README.md .claude/skills/ agents/ helpers/*.py \| grep -v "^#\|example" \| wc -l` near 0 |
| W0B.11 | Create replacement setup guide | BUILD | `docs/setup-guide.md` | W0B.10 | UX | `ls docs/setup-guide.md` |
| W0B.12 | Write enhanced data_helpers tests (pytest-native) | BUILD | `tests/test_data_helpers_v2.py` (~60 lines) | W0B.7 | Python Eng | `pytest tests/test_data_helpers_v2.py -v` |

**Gate:** No NovaMart references remain (except _example documentation). `pytest tests/ -v` still passes.

---

### Wave 1: Interview-First Onboarding

**Goal:** Replace the NovaMart tutorial with a conversational interview that populates the knowledge system from the user's real context.

**Parallelism notes:** W1.1 and W1.2 can run concurrently. W1.3 depends on W1.1 (interview writes to schema). W1.4 depends on W1.1. W1.5 depends on W0B.5. W1.6 depends on W1.1.

| ID | Description | Action | File Paths | Dependencies | Owner | Verify |
|----|-------------|--------|------------|--------------|-------|--------|
| W1.1 | Build /setup interview skill (4 phases + fork) | BUILD | `.claude/skills/setup/skill.md` | W0B | UX | Skill file has 4 phases, state schema, fork after Phase 2, design principles |
| W1.2 | Rewrite first-run-welcome to route through /setup | ENHANCE | `.claude/skills/first-run-welcome/skill.md` | W0B | UX | Skill routes to /setup on cold start, no NovaMart mention |
| W1.3 | Define setup-state.yaml schema (4 phases, Phase 5 standalone) | BUILD | `.knowledge/setup-state.yaml` (template/schema definition) | W1.1 | Knowledge | Schema has 4 standard phases + development_context as opt-in |
| W1.4 | Build /setup reset with Tier 1 (profile) and Tier 2 (full) | BUILD | Within `.claude/skills/setup/skill.md` (reset subcommand section) | W1.1 | UX | Reset design has two tiers, Tier 2 requires "reset everything" confirmation |
| W1.5 | Create _example organization templates | BUILD | `.knowledge/organizations/_example/manifest.yaml`, `_example/business/index.yaml`, `_example/business/glossary/terms.yaml`, `_example/business/products/index.yaml`, `_example/business/metrics/index.yaml`, `_example/business/objectives/index.yaml`, `_example/business/teams/index.yaml` | W0B.5 | Knowledge | All files parse as YAML, manifest has `is_example: true` |
| W1.6 | Define integrations.yaml schema | BUILD | `.knowledge/user/integrations.yaml` (schema definition within _example or template) | W1.1 | Knowledge | Schema has channels list, preferred_export_format, schema_version |

**Gate:** Fresh clone -> type "hello" -> Knowledge Bootstrap detects no setup-state.yaml -> first-run-welcome routes to /setup -> interview starts Phase 1.

---

### Wave 2: Knowledge Infrastructure

**Goal:** Create the 7-subsystem knowledge architecture and programmatic validation framework. Everything ships empty; the interview and usage populate it.

**Parallelism notes:** W2.1-W2.5 are independent schema/infrastructure tasks. W2.6 depends on W2.1-W2.5 (bootstrap loads all subsystems). W2.7a-W2.7e are independent module builds. W2.7f depends on W2.7a-W2.7e. W2.8a-W2.8c are independent. Test tasks (b-suffixed) depend on their module tasks (a-suffixed).

| ID | Description | Action | File Paths | Dependencies | Owner | Verify |
|----|-------------|--------|------------|--------------|-------|--------|
| W2.1 | Create dataset brain schema and gitignore | BUILD | `.knowledge/datasets/_metric_schema.yaml`, `.knowledge/datasets/.gitignore` | W0B.4 | Knowledge | Files parse as valid YAML |
| W2.2 | Create corrections log infrastructure | BUILD | `.knowledge/corrections/log.yaml`, `.knowledge/corrections/index.yaml`, `.knowledge/corrections/log.template.yaml` | W0B | Knowledge | All 3 files parse; `corrections: []` in log.yaml |
| W2.3 | Create learnings infrastructure | BUILD | `.knowledge/learnings/index.md` | W0B | Knowledge | File exists with 6 category definitions |
| W2.4 | Create query archaeology infrastructure | BUILD | `.knowledge/query-archaeology/schemas/cookbook_entry.schema.json`, `schemas/table_cheatsheet.schema.json`, `schemas/join_pattern.schema.json`, `curated/cookbook/.gitkeep`, `curated/tables/.gitkeep`, `curated/joins/.gitkeep`, `raw/.gitkeep`, `curated/index.yaml` | W0B | Knowledge | JSON schemas validate; index.yaml parses |
| W2.5 | Create analysis archive infrastructure | BUILD | `.knowledge/analyses/index.yaml`, `.knowledge/analyses/_schema.yaml`, `.knowledge/analyses/_patterns.yaml`, `.knowledge/global/cross_dataset_observations.yaml` | W0B | Knowledge | All YAML parses |
| W2.6 | Enhance knowledge bootstrap for all 7 subsystems | ENHANCE | `.claude/skills/knowledge-bootstrap/skill.md` | W2.1-W2.5, W1.3 | UX | Skill has Steps 0, 3b, 3c, 3d, enhanced Step 5 readiness report |
| W2.7a | Build structural_validator.py | BUILD | `helpers/structural_validator.py` (~380 lines) | W0A.5 | Python Eng | `python -c "from helpers.structural_validator import validate_schema; print('OK')"` |
| W2.7b | Write structural_validator tests | BUILD | `tests/test_structural_validator.py` (~200 lines, 20 cases) | W2.7a | Quality | `pytest tests/test_structural_validator.py -v` |
| W2.7c | Build logical_validator.py | BUILD | `helpers/logical_validator.py` (~375 lines) | W0A.5 | Python Eng | `python -c "from helpers.logical_validator import validate_aggregation_consistency; print('OK')"` |
| W2.7d | Write logical_validator tests | BUILD | `tests/test_logical_validator.py` (~180 lines, 18 cases) | W2.7c | Quality | `pytest tests/test_logical_validator.py -v` |
| W2.7e | Build business_rules.py | BUILD | `helpers/business_rules.py` (~350 lines) | W0A.5 | Python Eng | `python -c "from helpers.business_rules import validate_ranges; print('OK')"` |
| W2.7f | Write business_rules tests | BUILD | `tests/test_business_rules.py` (~150 lines, 15 cases) | W2.7e | Quality | `pytest tests/test_business_rules.py -v` |
| W2.7g | Build simpsons_paradox.py | BUILD | `helpers/simpsons_paradox.py` (~295 lines) | W0A.5 | Python Eng | `python -c "from helpers.simpsons_paradox import check_simpsons_paradox; print('OK')"` |
| W2.7h | Write simpsons_paradox tests | BUILD | `tests/test_simpsons_paradox.py` (~250 lines, 15 cases) | W2.7g | Quality | `pytest tests/test_simpsons_paradox.py -v` |
| W2.7i | Build confidence_scoring.py | BUILD | `helpers/confidence_scoring.py` (~400 lines) | W2.7a, W2.7c, W2.7e, W2.7g | Python Eng | `python -c "from helpers.confidence_scoring import score_confidence; print('OK')"` |
| W2.7j | Write confidence_scoring tests | BUILD | `tests/test_confidence_scoring.py` (~300 lines, 25 cases) | W2.7i | Quality | `pytest tests/test_confidence_scoring.py -v` |
| W2.7k | Write validation pipeline integration test | BUILD | `tests/test_validation_pipeline.py` (~150 lines, 5 cases) | W2.7i | Quality | `pytest tests/test_validation_pipeline.py -v` |
| W2.8a | Build business_validation.py | BUILD | `helpers/business_validation.py` (~180 lines) | W0A.5 | Python Eng | Import succeeds |
| W2.8b | Write business_validation tests | BUILD | `tests/test_business_validation.py` (~80 lines, 8 cases) | W2.8a | Quality | `pytest tests/test_business_validation.py -v` |
| W2.8c | Build health_check.py | BUILD | `helpers/health_check.py` (~200 lines) | W2.8a | Python Eng | Import succeeds |
| W2.8d | Write health_check tests | BUILD | `tests/test_health_check.py` (~80 lines, 8 cases) | W2.8c | Quality | `pytest tests/test_health_check.py -v` |
| W2.8e | Build metric_validator.py | BUILD | `helpers/metric_validator.py` (~160 lines) | W0A.5 | Python Eng | Import succeeds |
| W2.8f | Write metric_validator tests | BUILD | `tests/test_metric_validator.py` (~80 lines, 8 cases) | W2.8e | Quality | `pytest tests/test_metric_validator.py -v` |
| W2.9 | Update .knowledge/README.md | BUILD | `.knowledge/README.md` | W2.1-W2.5 | Knowledge | File documents 7 subsystems, gitignore policy |

**Gate:** All YAML/JSON parses. All 5 validator modules + 3 infrastructure helpers import. ~98 new test cases pass.

---

### Wave 3: Self-Learning Loop

**Goal:** Add the mechanisms that populate the knowledge system: feedback capture, correction logging, archaeology retrieval and auto-capture, and pre-flight loading in agents/skills.

**Parallelism notes:** W3.1 and W3.2 can run concurrently (independent skills). W3.3 can run concurrently with W3.1-W3.2. W3.4 depends on W3.1 (feedback capture is pre-router). W3.5 depends on W3.3. W3.6 is independent. W3.7-W3.8 depend on entity resolver and archaeology helpers from Wave 2 area work.

| ID | Description | Action | File Paths | Dependencies | Owner | Verify |
|----|-------------|--------|------------|--------------|-------|--------|
| W3.1 | Build feedback capture skill (pre-router interceptor) | BUILD | `.claude/skills/feedback-capture/skill.md` | W2.3 | UX | Skill has trigger conditions, 6-step workflow, architectural position (pre-router) |
| W3.2 | Build log correction skill | BUILD | `.claude/skills/log-correction/skill.md` | W2.2 | UX | Skill has 7-step workflow, severity behavior table |
| W3.3 | Build query archaeology retrieval skill | BUILD | `.claude/skills/archaeology/skill.md` | W2.4 | UX | Skill handles empty index gracefully |
| W3.4 | Enhance question router with entity disambiguation and pre-flight | ENHANCE | `.claude/skills/question-router/skill.md` | W3.1, W1.1 | Pipeline | Skill has Pre-Flight, Step 0, Step 0.5, Step 1b, Step 1c, Step 1d with per-step try/except |
| W3.5 | Add pre-flight checks to 4 SQL-writing analysis agents | ENHANCE | `agents/descriptive-analytics.md`, `agents/overtime-trend.md`, `agents/cohort-analysis.md`, `agents/root-cause-investigator.md` | W3.3, W3.2 | Pipeline | Each agent has Steps 1b, 1c + CONTRACT inputs for SQL_PATTERNS, CORRECTIONS |
| W3.6 | Add pre-flight learnings to consuming skills | ENHANCE | `.claude/skills/question-framing/skill.md`, `.claude/skills/visualization-patterns/skill.md`, `.claude/skills/stakeholder-communication/skill.md` | W2.3 | UX | Each skill has Pre-Flight section referencing correct learnings category |
| W3.7 | Build entity_resolver.py | BUILD | `helpers/entity_resolver.py` (~370 lines) | W0A.5, W1.5 | Python Eng | `python -c "from helpers.entity_resolver import disambiguate_question; print('OK')"` |
| W3.7b | Write entity_resolver tests | BUILD | `tests/test_entity_resolver.py` (~200 lines, 20 cases) | W3.7 | Quality | `pytest tests/test_entity_resolver.py -v` |
| W3.8 | Build miss_rate_logger.py | BUILD | `helpers/miss_rate_logger.py` (~100 lines) | W0A.5 | Python Eng | Import succeeds |
| W3.8b | Write miss_rate_logger tests | BUILD | `tests/test_miss_rate_logger.py` (~80 lines, 8 cases) | W3.8 | Quality | `pytest tests/test_miss_rate_logger.py -v` |
| W3.9 | Build business_context.py | BUILD | `helpers/business_context.py` (~200 lines) | W0A.5, W1.5 | Python Eng | `python -c "from helpers.business_context import load_tier1_context; print('OK')"` |
| W3.9b | Write business_context tests | BUILD | `tests/test_business_context.py` (~100 lines, 10 cases) | W3.9 | Quality | `pytest tests/test_business_context.py -v` |
| W3.10 | Build archaeology_helpers.py (auto-capture) | BUILD | `helpers/archaeology_helpers.py` (~100 lines) | W0A.5 | Python Eng | Import succeeds |
| W3.10b | Write archaeology_helpers tests | BUILD | `tests/test_archaeology_helpers.py` (~80 lines, 8 cases) | W3.10 | Quality | `pytest tests/test_archaeology_helpers.py -v` |
| W3.11 | Add capture-to-archaeology step in archive analysis skill | ENHANCE | `.claude/skills/archive-analysis/skill.md` | W3.10, W3.3 | Knowledge | Skill has auto-capture flow at end of pipeline |

**Gate:** Feedback capture, log correction, and archaeology skills exist. Question router has Steps 0-1d. 4 analysis agents have pre-flight. ~46 new test cases pass.

---

### Wave 4: Enhanced Pipeline Engine

**Goal:** Upgrade the pipeline from linear execution to a DAG walker with OR-dependencies, non-critical degradation, per-run directories, sequential chart fan-out, and v1 state migration.

**Parallelism notes:** W4.1-W4.3 modify the same files (registry.yaml, run-pipeline skill) and must be sequential. W4.4 and W4.5 can run concurrently with W4.1-W4.3. W4.6 depends on W4.1-W4.3. W4.7 depends on W4.4. W4.8-W4.9 depend on W4.6.

| ID | Description | Action | File Paths | Dependencies | Owner | Verify |
|----|-------------|--------|------------|--------------|-------|--------|
| W4.1 | Add depends_on_any OR-dependencies to DAG walker | ENHANCE | `.claude/skills/run-pipeline/skill.md`, `agents/registry.yaml` | W2.6 | Pipeline | Registry has `depends_on_any` for root-cause-investigator; skill handles OR-gate logic |
| W4.2 | Add non-critical agent degradation with warn_on_failure | ENHANCE | `.claude/skills/run-pipeline/skill.md`, `agents/registry.yaml` | W4.1 | Pipeline | `critical: false` on visual-design-critic, narrative-coherence-reviewer, opportunity-sizer, comms-drafter; `warn_on_failure: true` on opportunity-sizer |
| W4.3 | Add chart fan-out protocol (sequential V2) | ENHANCE | `.claude/skills/run-pipeline/skill.md` | W4.2 | Pipeline | Skill has Chart Fan-Out Protocol section with per-beat state tracking |
| W4.4 | Add per-run directory structure with symlinks | ENHANCE | `.claude/skills/run-pipeline/skill.md`, `.claude/skills/resume-pipeline/skill.md` | W0B | Pipeline | Run creates `outputs/runs/{RUN_ID}/`; symlink at `working/pipeline_state.json` -> latest run |
| W4.5 | Build comms-drafter agent | BUILD | `agents/comms-drafter.md` | W0B | Pipeline | Agent has CONTRACT block with pipeline_step 19, critical: false |
| W4.6 | Update registry, CONTRACT_TEMPLATE, pipeline_state_schema | ENHANCE | `agents/registry.yaml`, `agents/CONTRACT_TEMPLATE.md`, `agents/pipeline_state_schema.md` | W4.1-W4.3, W4.5 | Pipeline | Valid YAML; all agents listed; no dangling dependency refs |
| W4.7 | Build /runs lifecycle skill | BUILD | `.claude/skills/runs/skill.md` | W4.4 | Pipeline | Skill has list, inspect, clean subcommands |
| W4.8 | Add v1-to-v2 pipeline state auto-migration | ENHANCE | `.claude/skills/resume-pipeline/skill.md` | W4.6 | Pipeline | Resume skill detects v1 state, migrates to v2, keeps backup |
| W4.8b | Write pipeline state migration tests | BUILD | `tests/test_pipeline_state_migration.py` (~50 lines, 5 cases) | W4.8 | Quality | `pytest tests/test_pipeline_state_migration.py -v` |
| W4.9 | Add pre-execution cleanup for crash recovery | ENHANCE | `.claude/skills/run-pipeline/skill.md` | W4.6 | Pipeline | Walker calls pre_execution_cleanup() before each agent |

**Gate:** Registry has OR-deps, critical flags, warn_on_failure. Per-run dirs work. Fan-out protocol exists. v1 state migrates cleanly.

---

### Wave 5: Brand Theming (Optional for V2 Launch)

**Goal:** Replace hardcoded chart colors with a YAML-driven theming pipeline. One theme file drives every visual output.

**Parallelism notes:** W5.1 must be first (schema). W5.2-W5.3 can run concurrently after W5.1. W5.4 depends on W5.2. W5.5 depends on W5.1. W5.6 depends on W5.2-W5.3.

| ID | Description | Action | File Paths | Dependencies | Owner | Verify |
|----|-------------|--------|------------|--------------|-------|--------|
| W5.1 | Create base theme definition | BUILD | `themes/_base.yaml` | W0B | Knowledge | `python -c "import yaml; yaml.safe_load(open('themes/_base.yaml')); print('OK')"` |
| W5.2 | Build theme_loader.py | BUILD | `helpers/theme_loader.py` (~200 lines) | W5.1, W0A.5 | Python Eng | `python -c "from helpers.theme_loader import load_theme; load_theme('default'); print('OK')"` |
| W5.2b | Write theme_loader tests | BUILD | `tests/test_theme_loader.py` (~100 lines, 10 cases), `tests/fixtures/theme_base.yaml`, `tests/fixtures/theme_brand.yaml` | W5.2 | Quality | `pytest tests/test_theme_loader.py -v` |
| W5.3 | Build chart_palette.py | BUILD | `helpers/chart_palette.py` (~180 lines) | W5.1 | Python Eng | `python -c "from helpers.chart_palette import get_palette; p = get_palette(); print(p.hero('Revenue'))"` |
| W5.3b | Write chart_palette tests | BUILD | `tests/test_chart_palette.py` (~80 lines, 8 cases) | W5.3 | Quality | `pytest tests/test_chart_palette.py -v` |
| W5.4 | Build theme lint and generation scripts | BUILD | `scripts/generate_theme_artifacts.py`, `scripts/lint_chart_colors.py`, `scripts/lint_wcag.py`, `scripts/check_theme_sync.py` | W5.2 | Python Eng | All 4 scripts run without error |
| W5.5 | Create example brand theme | BUILD | `themes/brands/example/theme.yaml`, `themes/brands/example/README.md` | W5.1 | Knowledge | `python -c "from helpers.theme_loader import load_theme; load_theme('example'); print('OK')"` |
| W5.6 | Integrate themes into chart_helpers.py | ENHANCE | `helpers/chart_helpers.py` | W5.2, W5.3 | Python Eng | `swd_style()` works with and without theme arg; existing tests pass |

**Gate:** Theme loader + chart palette import. swd_style() backward-compatible. 18 new test cases pass.

---

### Wave 6: Advanced Capabilities

**Goal:** Add deferred features: standalone dev context setup, business context browser, Notion ingest, context loader, and documentation.

**Parallelism notes:** All tasks can run concurrently.

| ID | Description | Action | File Paths | Dependencies | Owner | Verify |
|----|-------------|--------|------------|--------------|-------|--------|
| W6.1 | Build /setup-dev-context standalone skill (Phase 5 extracted) | BUILD | `.claude/skills/setup-dev-context/skill.md` | W1.1 | UX | Skill has codebase context questions, invoked via /setup-dev-context |
| W6.2 | Build /business context browser skill | BUILD | `.claude/skills/business/skill.md` | W1.5, W3.9 | UX | Skill has subcommands: glossary, products, metrics, objectives, teams, lookup, show |
| W6.3 | Build Notion ingest skill (deferred from Wave 3) | BUILD | `.claude/skills/notion-ingest/skill.md` | W2.4 | UX | Skill has BFS crawl, rate limiting, page conversion |
| W6.4 | Build context_loader.py (deferred from Wave 1) | BUILD | `helpers/context_loader.py` (~200 lines), `tests/test_context_loader.py` (~80 lines, 8 cases) | W3.9, Knowledge schema for Notion pages | Python Eng | Import succeeds; tests pass |
| W6.5 | Create theming documentation | BUILD | `docs/theming.md` | W5.6 | Python Eng | File exists, no company-specific references |

**Gate:** All skills have valid structure. context_loader imports. 8 new test cases pass.

---

### Wave 7: CLAUDE.md Update & Documentation

**Goal:** Update CLAUDE.md to reflect all new skills, agents, variables, and rules. The master instruction file must be the single source of truth.

**Parallelism notes:** W7.1-W7.5 all modify CLAUDE.md and should be executed sequentially (or as a single coordinated edit).

| ID | Description | Action | File Paths | Dependencies | Owner | Verify |
|----|-------------|--------|------------|--------------|-------|--------|
| W7.1 | Add new skills to CLAUDE.md skills table | ENHANCE | `CLAUDE.md` | W1-W6 | UX | All 8 new skills in table: setup, feedback-capture, log-correction, archaeology, notion-ingest, business, setup-dev-context, runs |
| W7.2 | Add comms-drafter to CLAUDE.md agents table | ENHANCE | `CLAUDE.md` | W4.5 | Pipeline | Comms Drafter in agents table |
| W7.3 | Add system variables to CLAUDE.md | ENHANCE | `CLAUDE.md` | W3.4 | Pipeline | All 13 new variables documented |
| W7.4 | Add rules 14 and 15 to CLAUDE.md | ENHANCE | `CLAUDE.md` | W3.1, W3.2 | UX | Rule 14 (capture feedback as learnings), Rule 15 (check corrections before SQL) |
| W7.5 | Rewrite Available Data section, helpers table, quick start | ENHANCE | `CLAUDE.md` | W2.6 | Knowledge | No NovaMart refs; 7-subsystem architecture documented; helpers table complete; fail-fast data source description |
| W7.6 | Add /runs to skill table and {{RUN_DIR}} to variables | ENHANCE | `CLAUDE.md` | W4.7 | Pipeline | /runs skill in table; {{RUN_DIR}} documented |
| W7.7 | Add workflow step 19 (comms-drafter) to default workflow | ENHANCE | `CLAUDE.md` | W4.5 | Pipeline | Step 19 in workflow section |
| W7.8 | Build schema migration framework (stub for V2.1) | BUILD | `helpers/schema_migration.py` (~80 lines), `tests/test_schema_migration.py` (~60 lines, 5 cases) | W0A.5 | Python Eng | Import succeeds; tests pass; framework is inert (no migrations registered) |

**Gate:** `grep -i "novamart" CLAUDE.md` returns nothing. All skill paths in CLAUDE.md resolve to existing files. `wc -l CLAUDE.md` under 450.

---

### Wave 8: End-to-End Verification (Post-Launch Hardening)

**Goal:** Verify the complete system works end-to-end and run hardening tests.

**Parallelism notes:** W8.1-W8.4 are independent verification tasks. W8.5-W8.6 are manual simulations.

| ID | Description | Action | File Paths | Dependencies | Owner | Verify |
|----|-------------|--------|------------|--------------|-------|--------|
| W8.1 | YAML and JSON parse verification | VERIFY | All `.knowledge/**/*.yaml`, `.knowledge/**/*.json` | All | Quality | Zero parse errors |
| W8.2 | Python import verification (all modules) | VERIFY | All `helpers/*.py` modules | All | Quality | All ~28 modules import successfully |
| W8.3 | Path reference verification (CLAUDE.md paths exist on disk) | VERIFY | `CLAUDE.md` | W7 | Quality | All referenced paths exist |
| W8.4 | Company/NovaMart reference sweep | VERIFY | Entire codebase | All | Quality | Zero NovaMart/workshop/bootcamp references |
| W8.5 | Cold-start simulation | VERIFY | -- | All | UX | Fresh clone -> "hello" -> routes to /setup -> interview starts |
| W8.6 | Functional smoke test | VERIFY | -- | All | UX | L1 question answered; correction captured as CORR-001; /setup status works; /business shows counts |
| W8.7 | Import check script | BUILD | `scripts/check_imports.py` (~80 lines) | W7 | Python Eng | Script enforces import layer rules |
| W8.8 | Integration test suite | BUILD | `tests/test_integration.py` (~50 lines) | W7 | Quality | Cross-module integration tests pass |

**Gate:** All ~244 tests pass. No NovaMart references. Cold-start works. CI green on 3.10/3.11/3.12.

---

## 4. Dependency Graph

```
Wave 0A ─────────────────────────────┐
  (test foundation, file_helpers,    │
   __init__.py, CI update)           │
                                     │
                                     v
Wave 0B ─────────────────────────────┐
  (NovaMart removal, config reset,   │
   reference cleanup)                │
                                     │
              ┌──────────────────────┼──────────────────────┐
              │                      │                      │
              v                      v                      v
         Wave 1                 Wave 2                 Wave 5 (optional)
   (Interview onboarding)  (Knowledge infra,      (Brand theming)
                            validators)                 │
              │                      │                  │
              └──────────┬───────────┘                  │
                         │                              │
                         v                              │
                    Wave 3                              │
             (Self-learning loop,                       │
              entity resolver,                          │
              archaeology capture)                      │
                         │                              │
              ┌──────────┤                              │
              │          │                              │
              v          v                              │
         Wave 4     Wave 6                              │
   (Pipeline engine,  (Dev context,                     │
    DAG walker,        business skill,                  │
    per-run dirs)      notion ingest,          ┌────────┘
              │        context_loader)         │
              │          │                     │
              └──────────┼─────────────────────┘
                         │
                         v
                    Wave 7
              (CLAUDE.md update,
               schema migration)
                         │
                         v
                    Wave 8
              (E2E verification,
               hardening)
```

**Key cross-wave dependencies:**
- Wave 3 requires both Wave 1 (interview produces org context) and Wave 2 (knowledge schemas exist)
- Wave 4 requires Wave 2 (registry references knowledge subsystems)
- Wave 5 has no dependencies beyond 0B (can run in parallel with Waves 1-4)
- Wave 6 requires Wave 1 (setup-dev-context extends interview) and Wave 3 (context_loader uses business_context)
- Wave 7 requires all other waves (CLAUDE.md reflects everything)

---

## 5. Recommended Execution Schedule

| Session | Waves | Estimated Duration | Commit Message |
|---------|-------|--------------------|----------------|
| 1 | 0A | 2-3 hours | `test: add pytest foundation, conftest, fixtures, file_helpers` |
| 2 | 0B | 2-3 hours | `feat: strip NovaMart scaffolding, reset to clean slate` |
| 3 | 1 | 3-4 hours | `feat: add interview-first /setup onboarding (4 phases)` |
| 4 | 2 (schemas) | 2-3 hours | `feat: add 7-subsystem knowledge architecture` |
| 5 | 2 (validators) | 4-5 hours | `feat: add 4-layer programmatic validation with confidence scoring` |
| 6 | 2 (helpers) | 3-4 hours | `feat: add business_validation, health_check, metric_validator` |
| 7 | 3 (skills) | 3-4 hours | `feat: add self-learning loop (feedback capture, corrections, archaeology)` |
| 8 | 3 (modules) | 4-5 hours | `feat: add entity resolver, miss rate logger, business context helpers` |
| 9 | 4 | 4-5 hours | `feat: enhance pipeline engine (DAG walker, OR-deps, per-run dirs)` |
| 10 | 5 (optional) | 4-5 hours | `feat: add YAML-driven brand theming pipeline` |
| 11 | 6 | 3-4 hours | `feat: add setup-dev-context, business browser, notion ingest` |
| 12 | 7 + 8 | 3-4 hours | `feat: update CLAUDE.md, verify end-to-end` |

**Minimum viable upgrade:** Sessions 1-8 (Waves 0A through 3) produce the core transformation. The interview + knowledge infrastructure + learning loop changes the system from "tutorial toolkit" to "your AI analyst." Sessions 9+ add automation and polish.

**Context management:** If context gets long within a session (more than 15 file operations), commit and start a fresh Claude Code session. Use `/resume-pipeline` pattern: save artifacts to `working/`, resume from the next step.

---

## 6. Implementation Notes

Critical details extracted from the expert plans that implementers must know.

### Wave 0A/0B: Ordering Is Non-Negotiable

The Quality Strategist and debate resolved a labeling ambiguity: **test foundation (0A) MUST complete before deletion (0B)**. The logical dependency is:

```
0A: Build test infrastructure (conftest, fixtures, CI update, test rewrites)
     |
     v
0B: Delete NovaMart (safe because tests no longer depend on it)
```

Both can land in a single commit, but the CI must pass at the 0A boundary. If deletion happens before test migration, there is a window where CI is broken with no recovery path.

### Wave 0B: DuckDB Stays, NovaMart Goes

Per Conflict 1 resolution, `_connect_duckdb()` in `connection_manager.py` is KEPT. DuckDB is the local SQL engine for CSV analysis, profiling, source tie-out, and `safe_query()`. The change is: `_connect_duckdb()` fails explicitly when no `duckdb_path` is configured, rather than silently falling back to NovaMart CSVs.

The fallback chain after the fix: `primary connection -> local DuckDB (if local_data.duckdb set) -> CSV via pandas (if local_data.path set) -> clear error message`. No silent cascade.

### Wave 1: Interview Design Principles

The `/setup` skill must embed these principles (from UX Designer):
1. Interview, not interrogation -- explain WHY you ask and WHAT you do with the answer
2. Every answer produces something visible -- no "thanks, noted" without writing a file
3. Skip is always an option -- degrade gracefully
4. Resume, don't repeat -- state file tracks per-phase progress
5. Never block the user from working after Phase 2
6. Never ask for information you can detect (domain from schema)
7. Never lose progress -- persist every answer immediately
8. Conversational undo after each phase ("Does this look right?")

### Wave 2: Validator Return Contract

Every validator function returns a standard dict: `{valid: bool, severity: "PASS"|"WARNING"|"BLOCKER", ...details}`. The confidence scorer consumes these dicts from all 4 layers. Grade thresholds: A (85-100), B (70-84), C (55-69), D (40-54), F (0-39). When any validator layer is completely missing, cap grade at C.

### Wave 3: Pre-Flight Is Enrichment, Not Gatekeeping

Every pre-flight step in the question router is independently wrapped in try/except. No single pre-flight failure can prevent the pipeline from starting. If entity resolution returns empty, the pipeline proceeds without entity enrichment. If corrections index is missing, agents write SQL from scratch. The system must be equally functional on day 1 (empty knowledge) as on day 100 (rich knowledge).

### Wave 3: Auto-Capture Quality Control

Auto-captured SQL patterns from archive analysis start as `state: draft`. Draft entries are NOT served by the archaeology retrieval skill. Only `state: validated` entries are served. Validation requires either: (a) explicit user promotion, or (b) the same pattern being captured 3+ times across different analyses (auto-promote). Quality over quantity.

### Wave 4: Pipeline State Migration

When `resume-pipeline` encounters a v1 state file (no `schema_version` or `schema_version: 1`), it runs auto-migration:
1. Back up original file as `.v1.bak`
2. Map step-number keys to agent-name keys using the registry
3. When one step maps to multiple agents, copy state to all with a warning
4. Post-migration: verify completed agents have output files; demote to `pending` if no outputs exist
5. Write v2 state atomically

### Wave 4: Per-Run Directory Layout

```
outputs/runs/{YYYY-MM-DD}_{question-slug}/
  pipeline_state.json
  charts/
    chart_01_conversion_funnel.png
    chart_02_revenue_trend.png
  comms/
    slack_summary.md
    email_exec.md
  narrative.md
  deck.md
```

Backward compatibility: `working/pipeline_state.json` is a symlink to the latest run's state file. The `outputs/runs/latest` symlink points to the most recent run directory.

### Wave 5: Theme Architecture

```
themes/
  _base.yaml            # Default AI Analyst identity (committed)
  brands/
    example/
      theme.yaml        # Override tokens (committed as example)
      README.md
    {org}/
      theme.yaml        # User brand (gitignored)
```

The theme loader deep-merges brand tokens over the base theme. `swd_style("brand_name")` loads the merged theme. `swd_style()` with no argument falls back to hardcoded defaults for backward compatibility.

### Wave 7: Schema Migration Framework

Ships empty for V2 (all schemas start at v1). The `migrate_if_needed()` function returns data unchanged when no migrations are registered. V2.1 bumps to version 2 and registers transform functions. Migration is lazy: runs when a file is read and its `schema_version` is older than expected. Backup created before any migration.

File types that need migration support: setup_state, entity_index, manifest, org_manifest, corrections_log, corrections_index, notion_page (Wave 6), pipeline_state.

---

## 7. Deferred to V2.1

These items were explicitly deferred during planning but have design notes ready:

| Item | Design Status | Notes |
|------|--------------|-------|
| Parallel chart fan-out | Protocol designed, sequential only in V2 | Switch by changing one function; `max_parallel_charts` pipeline arg is ready |
| Curated demo datasets | Concept approved | UX Designer will define 2 datasets (e-commerce, SaaS) |
| Multi-dataset entity resolution | Acknowledged as gap | Entity index is org-scoped; cross-dataset resolution needs design |
| Correction graduation | Rule documented (3 HIGH -> quirks.md) | Implementation deferred; `graduated_to` field exists in schema |
| Checkpoint formalization | Prose in skill file for V2 | Formalize in registry for V2.1 |
| Generic fan-out | Chart-specific for V2 | Generalize when a second fan-out case arises |
| Notion sync helpers (Tier 3) | `rate_limiter.py`, `sync_runner.py`, `sync_checkpoint.py`, `notion_sync.py` | Notion ingest works without them using inline logic |
| False positive/negative rate testing | Deferred to Wave 8 hardening | Per-function unit tests provide launch coverage |
| Context loader token budgeting | General utility designed | May ship early if large glossaries cause token issues |

---

## 8. Files Changed Summary

### Wave 0A -- Test Foundation

| File | Change Type | Description |
|------|-------------|-------------|
| `helpers/__init__.py` | CREATE | Empty package init for imports |
| `tests/__init__.py` | CREATE | Empty package init for pytest discovery |
| `tests/conftest.py` | CREATE | Shared pytest fixtures, factories, tmp_knowledge_dir |
| `tests/fixtures/synthetic_orders.csv` | CREATE | 200-row synthetic order data |
| `tests/fixtures/synthetic_users.csv` | CREATE | 100-row synthetic user data |
| `tests/fixtures/synthetic_products.csv` | CREATE | 20-row synthetic product data |
| `tests/fixtures/entity_index.yaml` | CREATE | Test entity index (10 entities, 20 aliases) |
| `tests/fixtures/org_manifest.yaml` | CREATE | Test organization manifest |
| `helpers/file_helpers.py` | CREATE | Atomic write, content hash, YAML helpers |
| `tests/test_file_helpers.py` | CREATE | 12 test cases for file_helpers |
| `tests/test_validation_e2e.py` | MODIFY | Rewrite to remove NovaMart dependency |
| `tests/test_knowledge_infrastructure.py` | MODIFY | Rewrite of test_cross_dataset.py |
| `tests/test_lineage_tracker.py` | MODIFY | Migrate to pytest conventions |
| `tests/test_synthesize_insights.py` | MODIFY | Migrate to pytest conventions |
| `tests/test_multi_warehouse.py` | MODIFY | Migrate to pytest conventions |
| `.github/workflows/ci.yml` | MODIFY | Remove download-data.sh dep, Python 3.10+ matrix |
| `pyproject.toml` | MODIFY | `requires-python >= "3.10"`, add pytest-cov, markers |

### Wave 0B -- NovaMart Removal

| File | Change Type | Description |
|------|-------------|-------------|
| `fallbacks/` | DELETE | Entire directory (~26 files) |
| `setup/prerequisites.md` | DELETE | Workshop setup guide |
| `setup/claude-code-install.md` | DELETE | Workshop setup guide |
| `setup/motherduck-setup.md` | DELETE | Workshop setup guide |
| `setup/troubleshooting.md` | DELETE | Workshop setup guide |
| `setup/mcp-config.md` | DELETE | Workshop setup guide |
| `setup/` | DELETE | Directory if empty |
| `scripts/download-data.sh` | DELETE | NovaMart download script |
| `data/checksums.sha256` | DELETE | NovaMart checksums |
| `data/novamart/` | DELETE | NovaMart CSV data files |
| `.knowledge/datasets/novamart/` | DELETE | Entire directory (~12 files) |
| `.knowledge/organizations/_seed/` | DELETE | Entire directory (~14 files) |
| `.claude/mcp.json.example` | DELETE | MCP config example (interview handles setup) |
| `.knowledge/active.yaml` | MODIFY | Reset to `active_dataset: null` |
| `data_sources.yaml` | MODIFY | Reset to `sources: {}` |
| `helpers/data_helpers.py` | MODIFY | Remove NovaMart defaults, fail-fast on no config |
| `helpers/error_helpers.py` | MODIFY | Remove NovaMart table names, dynamic lookup |
| `helpers/connection_manager.py` | MODIFY | Remove NovaMart fallback, keep DuckDB backend |
| `.claude/skills/knowledge-bootstrap/skill.md` | MODIFY | Remove NovaMart detection steps |
| `.claude/skills/run-pipeline/skill.md` | MODIFY | Remove NovaMart example |
| `.claude/skills/datasets/skill.md` | MODIFY | Remove NovaMart example output |
| `.claude/skills/metric-spec/skill.md` | MODIFY | Remove NovaMart metric examples |
| `agents/source-tieout.md` | MODIFY | Replace NovaMart example |
| `agents/deck-creator.md` | MODIFY | Replace NovaMart footer with variables |
| `helpers/chart_helpers.py` | MODIFY | Replace NovaMart subtitle example |
| `README.md` | MODIFY | Replace NovaMart quick start |
| `.knowledge/README.md` | MODIFY | Remove NovaMart versioning policy |
| `docs/setup-guide.md` | CREATE | Replacement professional setup guide |
| `.knowledge/datasets/.gitkeep` | CREATE | Keep empty directory |
| `tests/test_data_helpers_v2.py` | CREATE | Pytest-native tests for enhanced data_helpers |

### Wave 1 -- Interview Onboarding

| File | Change Type | Description |
|------|-------------|-------------|
| `.claude/skills/setup/skill.md` | CREATE | 4-phase interview with fork, state tracking, reset |
| `.claude/skills/first-run-welcome/skill.md` | MODIFY | Route through /setup on cold start |
| `.knowledge/organizations/_example/manifest.yaml` | CREATE | Example org template with is_example: true |
| `.knowledge/organizations/_example/business/index.yaml` | CREATE | Empty business context template |
| `.knowledge/organizations/_example/business/glossary/terms.yaml` | CREATE | Empty glossary template |
| `.knowledge/organizations/_example/business/products/index.yaml` | CREATE | Empty products template |
| `.knowledge/organizations/_example/business/metrics/index.yaml` | CREATE | Empty metrics template |
| `.knowledge/organizations/_example/business/objectives/index.yaml` | CREATE | Empty objectives template |
| `.knowledge/organizations/_example/business/teams/index.yaml` | CREATE | Empty teams template |

### Wave 2 -- Knowledge Infrastructure

| File | Change Type | Description |
|------|-------------|-------------|
| `.knowledge/datasets/_metric_schema.yaml` | CREATE | Metric definition schema |
| `.knowledge/datasets/.gitignore` | CREATE | Ignore user dataset dirs |
| `.knowledge/corrections/log.yaml` | CREATE | Empty corrections log |
| `.knowledge/corrections/index.yaml` | CREATE | Empty corrections index |
| `.knowledge/corrections/log.template.yaml` | CREATE | Documented correction schema |
| `.knowledge/learnings/index.md` | CREATE | Learnings index with 6 categories |
| `.knowledge/query-archaeology/schemas/cookbook_entry.schema.json` | CREATE | Cookbook JSON schema |
| `.knowledge/query-archaeology/schemas/table_cheatsheet.schema.json` | CREATE | Table cheatsheet schema |
| `.knowledge/query-archaeology/schemas/join_pattern.schema.json` | CREATE | Join pattern schema |
| `.knowledge/query-archaeology/curated/index.yaml` | CREATE | Empty curated index |
| `.knowledge/query-archaeology/curated/cookbook/.gitkeep` | CREATE | Empty dir |
| `.knowledge/query-archaeology/curated/tables/.gitkeep` | CREATE | Empty dir |
| `.knowledge/query-archaeology/curated/joins/.gitkeep` | CREATE | Empty dir |
| `.knowledge/query-archaeology/raw/.gitkeep` | CREATE | Empty dir |
| `.knowledge/analyses/index.yaml` | CREATE | Empty analysis archive |
| `.knowledge/analyses/_schema.yaml` | CREATE | Analysis entry schema |
| `.knowledge/analyses/_patterns.yaml` | CREATE | Empty pattern library |
| `.knowledge/global/cross_dataset_observations.yaml` | CREATE | Empty cross-dataset observations |
| `.claude/skills/knowledge-bootstrap/skill.md` | MODIFY | Add Steps 0, 3b, 3c, 3d, enhanced Step 5 |
| `.knowledge/README.md` | MODIFY | Document 7 subsystems |
| `helpers/structural_validator.py` | CREATE | Schema, PK, referential, completeness checks |
| `helpers/logical_validator.py` | CREATE | Aggregation, trend, segment, temporal checks |
| `helpers/business_rules.py` | CREATE | Range, rate, YoY plausibility checks |
| `helpers/simpsons_paradox.py` | CREATE | Paradox detection and dimension scanning |
| `helpers/confidence_scoring.py` | CREATE | 7-factor scoring, A-F grades |
| `helpers/business_validation.py` | CREATE | Org knowledge file validation |
| `helpers/health_check.py` | CREATE | Knowledge system health check |
| `helpers/metric_validator.py` | CREATE | Metric formula validation |
| `tests/test_structural_validator.py` | CREATE | 20 test cases |
| `tests/test_logical_validator.py` | CREATE | 18 test cases |
| `tests/test_business_rules.py` | CREATE | 15 test cases |
| `tests/test_simpsons_paradox.py` | CREATE | 15 test cases |
| `tests/test_confidence_scoring.py` | CREATE | 25 test cases |
| `tests/test_validation_pipeline.py` | CREATE | 5 integration test cases |
| `tests/test_business_validation.py` | CREATE | 8 test cases |
| `tests/test_health_check.py` | CREATE | 8 test cases |
| `tests/test_metric_validator.py` | CREATE | 8 test cases |
| `tests/fixtures/metric_schema.yaml` | CREATE | Test metric schema fixture |

### Wave 3 -- Self-Learning Loop

| File | Change Type | Description |
|------|-------------|-------------|
| `.claude/skills/feedback-capture/skill.md` | CREATE | Pre-router interceptor, 6-step workflow |
| `.claude/skills/log-correction/skill.md` | CREATE | 7-step correction logging |
| `.claude/skills/archaeology/skill.md` | CREATE | SQL pattern retrieval skill |
| `.claude/skills/question-router/skill.md` | MODIFY | Add Steps 0, 0.5, 1b, 1c, 1d with try/except |
| `agents/descriptive-analytics.md` | MODIFY | Add Steps 1b, 1c + CONTRACT inputs |
| `agents/overtime-trend.md` | MODIFY | Add Steps 1b, 1c + CONTRACT inputs |
| `agents/cohort-analysis.md` | MODIFY | Add Steps 1b, 1c + CONTRACT inputs |
| `agents/root-cause-investigator.md` | MODIFY | Add Steps 1b, 1c + CONTRACT inputs |
| `.claude/skills/question-framing/skill.md` | MODIFY | Add Pre-Flight + anti-pattern #6 |
| `.claude/skills/visualization-patterns/skill.md` | MODIFY | Add Pre-Flight learnings |
| `.claude/skills/stakeholder-communication/skill.md` | MODIFY | Add Pre-Flight learnings |
| `.claude/skills/archive-analysis/skill.md` | MODIFY | Add capture-to-archaeology step |
| `helpers/entity_resolver.py` | CREATE | Entity disambiguation with fuzzy match |
| `helpers/miss_rate_logger.py` | CREATE | Entity miss tracking |
| `helpers/business_context.py` | CREATE | Tiered business context loading |
| `helpers/archaeology_helpers.py` | CREATE | Query capture and indexing |
| `tests/test_entity_resolver.py` | CREATE | 20 test cases |
| `tests/test_miss_rate_logger.py` | CREATE | 8 test cases |
| `tests/test_business_context.py` | CREATE | 10 test cases |
| `tests/test_archaeology_helpers.py` | CREATE | 8 test cases |

### Wave 4 -- Pipeline Engine

| File | Change Type | Description |
|------|-------------|-------------|
| `agents/registry.yaml` | MODIFY | OR-deps, critical flags, warn_on_failure, RUN_DIR output paths, comms-drafter entry |
| `.claude/skills/run-pipeline/skill.md` | MODIFY | DAG walker v2, OR-gates, non-critical degradation, checkpoint warnings, per-run dirs, chart fan-out, pre-execution cleanup |
| `.claude/skills/resume-pipeline/skill.md` | MODIFY | v2 state schema, v1 auto-migration, run directory discovery, partial fan-out resume |
| `agents/CONTRACT_TEMPLATE.md` | MODIFY | Document depends_on_any, critical, timeout_seconds, warn_on_failure |
| `agents/pipeline_state_schema.md` | MODIFY | Agent-keyed schema, new statuses, fan-out fields |
| `agents/comms-drafter.md` | CREATE | Step 19, non-critical, channel-aware formatting |
| `.claude/skills/runs/skill.md` | CREATE | /runs list, inspect, clean lifecycle commands |
| `tests/test_pipeline_state_migration.py` | CREATE | 5 test cases for v1->v2 migration |

### Wave 5 -- Brand Theming (Optional)

| File | Change Type | Description |
|------|-------------|-------------|
| `themes/_base.yaml` | CREATE | Default AI Analyst visual identity |
| `helpers/theme_loader.py` | CREATE | Theme loading, deep merge, caching |
| `helpers/chart_palette.py` | CREATE | Intent-driven color assignment |
| `scripts/generate_theme_artifacts.py` | CREATE | Generate .mplstyle from theme YAML |
| `scripts/lint_chart_colors.py` | CREATE | Flag hardcoded hex values |
| `scripts/lint_wcag.py` | CREATE | WCAG contrast validation |
| `scripts/check_theme_sync.py` | CREATE | Verify CSS/YAML/mplstyle sync |
| `themes/brands/example/theme.yaml` | CREATE | Example brand theme |
| `themes/brands/example/README.md` | CREATE | Brand creation guide |
| `helpers/chart_helpers.py` | MODIFY | Add optional theme parameter to swd_style() |
| `tests/test_theme_loader.py` | CREATE | 10 test cases |
| `tests/test_chart_palette.py` | CREATE | 8 test cases |
| `tests/fixtures/theme_base.yaml` | CREATE | Test fixture |
| `tests/fixtures/theme_brand.yaml` | CREATE | Test fixture |

### Wave 6 -- Advanced Capabilities

| File | Change Type | Description |
|------|-------------|-------------|
| `.claude/skills/setup-dev-context/skill.md` | CREATE | Standalone Phase 5 command |
| `.claude/skills/business/skill.md` | CREATE | Organization knowledge browser |
| `.claude/skills/notion-ingest/skill.md` | CREATE | Notion BFS crawler with rate limiting |
| `helpers/context_loader.py` | CREATE | Tiered content loading with token budgets |
| `tests/test_context_loader.py` | CREATE | 8 test cases |
| `docs/theming.md` | CREATE | Theming reference documentation |

### Wave 7 -- CLAUDE.md & Documentation

| File | Change Type | Description |
|------|-------------|-------------|
| `CLAUDE.md` | MODIFY | Skills table (8 new), agents table (1 new), system variables (13 new), rules 14-15, available data rewrite, helpers table update, workflow step 19, /runs skill, {{RUN_DIR}} variable |
| `helpers/schema_migration.py` | CREATE | Schema migration stub for V2.1 (~80 lines) |
| `helpers/migrations/__init__.py` | CREATE | Migration registry and runner |
| `helpers/migrations/v1_to_v2/__init__.py` | CREATE | Placeholder for future version-specific migrations |
| `tests/test_schema_migration.py` | CREATE | 5 test cases |

### Wave 8 -- Verification

| File | Change Type | Description |
|------|-------------|-------------|
| `scripts/check_imports.py` | CREATE | Import layer rule enforcer |
| `tests/test_integration.py` | CREATE | Cross-module integration tests |

---

## 9. Risk Register

Key risks identified across all expert plans, with mitigations.

| ID | Severity | Risk | Mitigation | Owner |
|----|----------|------|------------|-------|
| R1 | HIGH | Circular import between entity_resolver and business_context | Strict import layer rules enforced by `scripts/check_imports.py`. Layer 0 (stdlib+yaml) -> Layer 1 (file_helpers) -> Layer 2 (entity_resolver, business_context) -> Layer 3 (chart_helpers, data_helpers) | Python Eng |
| R2 | HIGH | State corruption on pipeline crash | Atomic writes via `file_helpers.py` + pre-execution cleanup for partial outputs + per-beat state persistence during fan-out | Pipeline |
| R3 | MEDIUM | Pre-router feedback capture adds latency to every message | Fast-path optimization: if message has no correction signals (keywords), skip immediately. Corrections index loaded once at session start, cached. Target: <50ms for non-correction messages | UX |
| R4 | MEDIUM | Auto-captured archaeology entries are low quality | All auto-captures start as `state: draft`, never served to users. Promotion requires explicit validation or 3+ captures across different analyses | Knowledge |
| R5 | MEDIUM | Theme YAML schema undefined (Gap 1) | Tests use fixture YAML. If schema changes, only test fixtures need updating. Wave 5 is optional | Python Eng |
| R6 | MEDIUM | Schema migration framework unused in V2 (YAGNI) | Framework is ~80 lines. Cost of having it is low. Cost of NOT having it when V2.1 needs migrations is high | Python Eng |
| R7 | MEDIUM | v1 state migration with multi-agent steps | Post-migration verification: check each "completed" agent has output files. Demote to "pending" if no outputs found | Pipeline |
| R8 | MEDIUM | Validator false positive rate unmeasured at launch | Soft gate at Wave 2: run validators against clean synthetic fixtures, assert zero false positives. Full rate testing in Wave 8 | Quality |
| R9 | LOW | /setup reset Tier 2 as a footgun | Require exact phrase "reset everything". Display counts of what will be lost. Corrections and learnings survive Tier 1 | UX |
| R10 | LOW | Orphaned correction concept tags after Tier 1 reset | When Phase 3 re-runs (new org context), regenerate by_concept index. Old tags become inert but harmless | Knowledge |
| R11 | LOW | Per-run directory proliferation | `/runs clean --keep=N` command + proactive warning when run count exceeds 20 | Pipeline |
| R12 | LOW | File corruption from interrupted writes | All .knowledge/ writes use `atomic_write()` via temp file + `os.replace()` | Python Eng |
| R13 | LOW | Context window degradation during 8+ chart fan-out | Per-beat state persistence enables resume. For >5 charts, suggest `/resume-pipeline` after every 5 to start fresh context | Pipeline |

---

## 10. Open Questions

These require user input before implementation can proceed.

### OQ-1: V2 Launch Scope
Is the target Waves 0-3 (minimum viable) or all 8 waves? Waves 0-3 deliver the core transformation (interview + knowledge + learning loop). Waves 4-8 add polish and advanced features.

### OQ-2: Brand Theming Priority
Wave 5 is marked optional. No persona has defined the `themes/_base.yaml` schema (Gap 1). If deferred, `swd_style()` continues with hardcoded colors (no regression). Decide before Wave 5.

### OQ-3: Python Version Confirmation
The plan assumes 3.10+ per the task instructions. The development machine runs 3.9.6 (macOS system Python). Confirm: update pyproject.toml to `>=3.10` and install Python 3.10+ via brew?

### OQ-4: Phase 1 Question Count
The UX Designer recommends reducing Phase 1 from 3-4 questions to 2 (role + audience), inferring analysis focus and style from usage. The original plan has 4 questions. Decide before Wave 1 implementation.

### OQ-5: Phase 3 Interview Style
Structured (5 questions: org, knowledge base, products, metrics, glossary) vs. open-ended (one question: "Tell me about your business" + Claude extracts). The structured approach is safer; the open-ended approach is faster and more conversational. Decide before Wave 1.

### OQ-6: Context Loader Timing
Should the token-budgeting logic (LoadTier enum, load_tiered()) ship in Wave 3 as a general utility, or wait for Wave 6 with the full Notion-aware context_loader? Shipping early prevents large glossaries from consuming excessive tokens.

### OQ-7: Correction Graduation Rule
The Knowledge Architect wants the graduation rule documented now (after 3 HIGH occurrences, auto-promote to quirks.md), even if implementation is deferred. Should this be in the log.template.yaml or left for V2.1?

---

## 11. Remaining Persona Disagreements

These are unresolved disagreements from Round 2 that do not block implementation but should be tracked.

### UX Designer: Phase 1 Should Be 2 Questions, Not 3-4
The UX Designer recommends reducing Phase 1 from 3-4 questions (role, analysis focus, audience, style) to 2 (role + audience), inferring the rest from usage. The argument: Q2 (analysis focus) can be inferred from the first 2-3 real questions, and Q4 (style) is a question most users cannot answer in the abstract. Counter-argument: explicit preference capture produces better defaults from day 1. **Resolution needed: see OQ-4.**

### UX Designer: Phase 3 Should Be One Open-Ended Question
Instead of 5 structured questions (org, knowledge base, products, metrics, glossary), ask one open-ended question ("Tell me about your business") and extract terms from the freeform response. More conversational, aligns with "interview not interrogation." Counter-argument: structured approach is safer and more predictable. **Resolution needed: see OQ-5.**

### Knowledge Architect: Correction Graduation Should Be Documented Now
The `graduated_to` field exists in the correction log schema but has no graduation logic defined. The Knowledge Architect wants the rule documented (after 3 HIGH occurrences, auto-promote to quirks.md) even if implementation is deferred. This prevents the schema from being a "broken promise." **Resolution needed: see OQ-7.**

### Pipeline Engineer: /runs Should Ship with Wave 4, Not Deferred
The debate summary suggested deferring `/runs` to Wave 6 or post-V2. The Pipeline Engineer argues that per-run directories without lifecycle management is an incomplete feature. The skill is <100 lines with zero dependencies. **Resolution: adopted -- /runs is in Wave 4 (W4.7).**

### Python Engineer: Context Loader Token Budgeting Should Ship Early
The Python Engineer argues that the token-budgeting logic (LoadTier enum, load_tiered()) is useful as a general utility in Wave 3, not just for Notion content in Wave 6. Without it, large glossaries (500+ terms) consume excessive context tokens. **Resolution needed: see OQ-6.**

### Quality Strategist: False Positive Testing Should Have a Soft Gate
The Quality Strategist accepts deferring full FP/FN rate testing to Wave 8 but requests a "soft gate" at Wave 2: run all 5 validators against clean synthetic fixtures and assert zero false positives. This catches the most dangerous failure mode (crying wolf on clean data) with ~30 minutes of effort. **Recommendation: adopt the soft gate.**

---

## 12. Key Decisions Made

These are the conflict resolutions from the debate, documented for the record.

| # | Conflict | Resolution | Rationale |
|---|----------|------------|-----------|
| 1 | Remove DuckDB vs. keep DuckDB | **Keep DuckDB**, remove NovaMart fallback only | DuckDB is the local SQL engine for CSV analysis, profiling, and tie-out. Only the silent fallback to NovaMart data is dangerous. |
| 2 | Phase 5 in standard interview | **Extract to /setup-dev-context** | 80%+ of users (PMs, execs, DS) never need codebase context. Including it adds friction for no value. |
| 3 | Learnings: 6 categories vs. 3 | **Define 6 in index, create files on demand** | Path.exists() check on nonexistent file is effectively free. Full structure available, zero overhead for unused. |
| 4 | Entity index rebuild strategy | **Content-hash with session cache** | Avoid unnecessary I/O. Rebuild only when source files (glossary, products, metrics, teams) change. |
| 5 | Opportunity Sizer criticality | **Keep non-critical, add warn_on_failure checkpoint** | Plan-aware criticality adds complexity for marginal gain. Checkpoint warning gives user agency. |
| 6 | Demo datasets for "no data" users | **Defer to V2.1** | Curated datasets are a project in themselves. Offer CSV upload path instead. |
| 7 | Query Archaeology auto-capture | **Add to Wave 3 via Archive Analysis** | Without auto-capture, archaeology is empty infrastructure forever. |
| 8 | Pipeline state: step-number vs. agent-name keys | **Agent-name keys with v1 auto-migration** | DAG model requires agent-level granularity. Step numbers cannot represent fan-out sub-status. |
| 9 | Python version floor | **3.10+ (match pyproject.toml)** | Python 3.9 EOL October 2025. 3.10+ enables match/case, X\|Y types, slots=True dataclasses. |
| 10 | Feedback capture timing | **Pre-router interceptor** | "That column was wrong" is feedback on the previous response, not a new L1-L5 question. Must run before routing. |
| 11 | Wave 0 structure | **Split into 0A (tests) then 0B (deletion)** | CI breaks if NovaMart is deleted before tests are migrated to synthetic data. |
| 12 | file_helpers.py timing | **Move to Wave 0** | Three personas identified it as blocking. Zero-dependency, enables everything else. |
| 13 | Chart fan-out parallelism | **Sequential for V2, parallel aspirational for V2.1** | Task tool untested for parallel chart generation. Per-beat state tracking still ships. |
| 14 | /runs lifecycle timing | **Ship with Wave 4 (Pipeline Engineer recommendation)** | Per-run directories without list/clean is an incomplete feature. The skill is <100 lines. |
| 15 | Entity index generation timing | **Synchronous but fast (alias flattening), with content-hash caching** | Async adds complexity. The operation is simple enough to be synchronous without blocking UX. |

---

## 13. Pre-Launch Verification Checklist

Run these checks after all waves are complete, before declaring V2 ready.

### Knowledge System
- [ ] `.knowledge/active.yaml` ships with `active_dataset: null`
- [ ] `.knowledge/datasets/` has no pre-loaded datasets (only schema template and .gitkeep)
- [ ] `.knowledge/organizations/_example/` has format documentation with `is_example: true`
- [ ] `.knowledge/corrections/` has empty log.yaml and index.yaml
- [ ] `.knowledge/learnings/` has index.md with 6 category definitions
- [ ] `.knowledge/query-archaeology/` has 3 JSON schemas and empty curated directories
- [ ] `.knowledge/analyses/` has empty index and schema
- [ ] All YAML/JSON files parse without error

### Skills
- [ ] 8 new skills exist: setup, feedback-capture, log-correction, archaeology, notion-ingest, business, setup-dev-context, runs
- [ ] 6 enhanced skills updated: knowledge-bootstrap, first-run-welcome, question-router, question-framing, visualization-patterns, stakeholder-communication
- [ ] Knowledge Bootstrap has Steps 0, 3b, 3c, 3d
- [ ] Question Router has Pre-Flight, Step 0, Step 0.5, Step 1b, Step 1c, Step 1d

### Agents
- [ ] 4 SQL-writing agents have Steps 1b and 1c with CONTRACT inputs
- [ ] Root Cause Investigator has `depends_on_any`
- [ ] Comms Drafter exists with `critical: false`
- [ ] Registry has all agents with correct dependencies and `{{RUN_DIR}}` output paths

### Python Helpers
- [ ] All ~28 modules import successfully on Python 3.10, 3.11, 3.12
- [ ] No circular imports (verified by `scripts/check_imports.py`)
- [ ] ~244 test cases pass (`pytest tests/ -v`)
- [ ] No test depends on NovaMart data or network access

### CLAUDE.md
- [ ] Skills table has all skills (existing + 8 new)
- [ ] Agents table has all agents (existing + comms-drafter)
- [ ] System variables table has all 13+ new variables
- [ ] Rules 13, 14, 15 present
- [ ] No NovaMart references
- [ ] No references to `data/hero/`, `data/examples/`, or silent fallback chains
- [ ] Data Source section describes fail-fast behavior
- [ ] Line count under 450

### Clean
- [ ] `grep -ri "novamart" CLAUDE.md README.md .claude/skills/ agents/ helpers/*.py` returns 0 hits
- [ ] `grep -i "workshop\|bootcamp\|exercise\|section [0-9]" README.md` returns 0 hits
- [ ] `data_sources.yaml` has `sources: {}`
- [ ] CI green on Python 3.10, 3.11, 3.12
- [ ] Cold-start simulation passes (fresh clone -> "hello" -> routes to /setup)
