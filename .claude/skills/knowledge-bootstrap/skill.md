# Skill: Knowledge Bootstrap

## Purpose
Initialize the knowledge system for a new session or a new dataset. Ensures
the `.knowledge/` directory is populated with the active dataset's context
before analysis begins.

## When to Use
- At the start of any session (read and validate the knowledge state)
- After `/connect-data` adds a new dataset
- After `/switch-dataset` changes the active dataset
- When the system detects missing or stale knowledge files

## Instructions

### Step 1: Read active dataset

```
Read .knowledge/active.yaml
```

If the file is missing or empty:
- If NovaMart data files exist in `data/novamart/`, set `active_dataset: novamart`
- Otherwise, prompt: "No active dataset configured. Use `/connect-data` to add one."

### Step 1b: Check for Tier 2 data files

Check if the 5 large Tier 2 CSV files are present in `data/novamart/`:
- `users.csv`, `orders.csv`, `events.csv`, `sessions.csv`, `support_tickets.csv`

**If any are missing**, display this message before proceeding:

```
Some data files are not downloaded yet. The repo ships with 8 small
reference tables but the 5 large analysis tables need to be downloaded.

Run this from the repo root:
  bash scripts/download-data.sh         # Sample data (~15MB, good for learning)
  bash scripts/download-data.sh --full  # Full dataset (~200MB compressed)

Missing files: {list of missing files}

You can still query the Tier 1 tables (products, calendar, experiments,
promotions, memberships, nps_responses, experiment_assignments, order_items).
```

Continue with bootstrap — don't halt. The system works with partial data.

### Step 2: Validate dataset brain

Check that `.knowledge/datasets/{active}/` contains:

| File | Required | Action if Missing |
|------|----------|-------------------|
| `manifest.yaml` | Yes | HALT — cannot proceed without connection config |
| `schema.md` | Yes | Generate from YAML schema or by profiling tables (see Step 2b) |
| `quirks.md` | No | Create empty template with section headers |

**Step 2b: Schema generation/refresh**

If `schema.md` is missing or empty, generate it:

1. **Check for structured schema YAML** at `data/schemas/{active}.yaml`. If found, use `schema_to_markdown()` from `helpers/data_helpers.py` to render it:
   ```python
   import yaml
   from helpers.data_helpers import schema_to_markdown
   with open(f"data/schemas/{active}.yaml") as f:
       schema_data = yaml.safe_load(f)
   schema_md = schema_to_markdown(schema_data)
   # Write to .knowledge/datasets/{active}/schema.md
   ```

2. **If no YAML exists**, fall back to profiling:
   ```python
   from helpers.data_helpers import get_connection_for_profiling
   from helpers.schema_profiler import profile_source
   conn_info = get_connection_for_profiling()
   schema = profile_source(conn_info)
   schema_md = schema_to_markdown(schema)
   ```

3. **Staleness check**: If `schema.md` exists but `last_profile.md` shows a more recent profiling date, regenerate from the latest profile data.

### Step 2c: Validate metric dictionary

Check `.knowledge/datasets/{active}/metrics/index.yaml`:
- **If it exists:** Read it and count defined metrics. Report count in Step 5.
- **If missing:** Create from template: `{dataset_id: {active}, metrics: [], total_metrics: 0}`. Note in Step 5: "No metrics defined yet. Use the metric-spec skill to define metrics."

### Step 2d: Load recent analysis history

Read `.knowledge/analyses/index.yaml`:
- If analyses exist for the active dataset, load the **last 3** entries.
- Extract: title, date, key findings count, question level.
- These provide continuity context — "Last time you analyzed this dataset, you found X."
- If the most recent analysis was <24 hours ago, note it: "Recent analysis available — use `/history {id}` to review."

### Step 3: Load context into session

Read these files and hold in context for the session:
1. `manifest.yaml` — for `{{DISPLAY_NAME}}`, `{{DATE_RANGE}}`, connection details
2. `schema.md` — for table/column reference
3. `quirks.md` — for data gotchas to watch for
4. `metrics/index.yaml` — for available metric definitions
5. Last 3 analysis summaries — for continuity context

Extract and set system variables:
- `{{SCHEMA}}` = `connection.schema_prefix` from manifest
- `{{DISPLAY_NAME}}` = `display_name` from manifest
- `{{DATE_RANGE}}` = `summary.date_range` from manifest
- `{{DATABASE}}` = `connection.database` from manifest

### Step 4: Initialize user profile

Check `.knowledge/user/profile.md`:
- **If it exists:** Read it and apply preferences to the session:
  - `Detail level` → controls response verbosity (executive-summary = brief, deep-dive = verbose)
  - `Chart preference` → controls how many charts to generate
  - `Narrative style` → controls bullet-points vs prose in storytelling
  - Check Corrections Log for past mistakes to avoid repeating
- **If it does not exist:** Create it from the template below, then continue:

```markdown
# User Profile

Auto-created by the knowledge bootstrap system. Updated as the system
learns your preferences from interactions.

## Role & Expertise

- **Role:** _[auto-detected or user-specified]_
- **Technical level:** _[beginner | intermediate | advanced]_
- **SQL comfort:** _[none | basic | intermediate | advanced]_
- **Statistics comfort:** _[none | basic | intermediate | advanced]_
- **Domain:** _[e-commerce | fintech | saas | marketplace | other]_

## Communication Preferences

- **Detail level:** _[executive-summary | standard | deep-dive]_
- **Chart preference:** _[minimal | standard | chart-heavy]_
- **Narrative style:** _[bullet-points | prose | mixed]_

## Corrections Log

_Records of times the user corrected the system's assumptions. Used to
improve future interactions._

<!-- Format: YYYY-MM-DD | What was wrong | What was right -->
```

### Step 4b: Update profile from corrections

When the user corrects the system during a session (e.g., "I'm a PM not an engineer",
"give me more detail", "I prefer bullet points"), update the profile:

1. Update the relevant field in Role & Expertise or Communication Preferences
2. Append an entry to the Corrections Log:
   ```
   YYYY-MM-DD | Assumed [wrong thing] | User prefers [right thing]
   ```
3. Write the updated file back to `.knowledge/user/profile.md`

**Important:** Only update the profile when the user explicitly corrects a
preference or states a preference. Do not infer preferences from silence.

### Step 5: Report readiness

Output a brief status:

```
Dataset: {display_name} ({source type})
Tables: {N} tables, ~{row_count} rows
Date range: {date_range}
Metrics: {M} defined
Profile: {loaded | new}
Status: Ready for analysis
```

## Edge Cases

- **No `.knowledge/` directory:** Create the full tree (datasets/, analyses/,
  global/, user/) and prompt for `/connect-data`.
- **Manifest exists but schema.md is empty:** Run a quick profile to regenerate.
- **Active dataset has no data files:** Report the issue and suggest checking
  the connection or falling back to CSV.
- **Multiple datasets exist:** Report which is active and remind about
  `/switch-dataset`.

## Anti-Patterns

1. **Never skip bootstrap.** Even if you "know" the dataset, always read the
   manifest — connection details may have changed.
2. **Never hardcode dataset names.** Always resolve from `active.yaml`.
3. **Never modify manifest.yaml during bootstrap.** Bootstrap reads only.
   Only `/connect-data` and manual edits write to manifests.
