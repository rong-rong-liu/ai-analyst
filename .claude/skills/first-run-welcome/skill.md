# Skill: First-Run Welcome

## Purpose
Provide an adaptive welcome experience for new users. Detects whether this
is a first session (no `.knowledge/user/profile.md`) and tailors the
onboarding flow based on what data is available.

## When to Use
- Session start when no user profile exists at `.knowledge/user/profile.md`
- After Knowledge Bootstrap detects a missing profile (Step 4)

## Instructions

### Step 1: Detect environment

Check five things:

1. **User profile exists?** → `.knowledge/user/profile.md`
   - If YES: This is a returning user. Skip this skill entirely.
   - If NO: Continue — this is a first run.

2. **NovaMart data present?** → Check `data/novamart/` for CSV files
   - If YES: NovaMart seed dataset is available for guided experience.
   - If NO: NovaMart was removed or never installed.

3. **Active dataset configured?** → `.knowledge/active.yaml`
   - If YES and not "novamart": User has their own data connected.
   - If NO: No dataset configured yet.

4. **MCP settings configured?** → `.claude/mcp.json`
   - If MISSING: Show setup hint:
     ```
     MCP not configured yet. To connect to MotherDuck:
       cp .claude/mcp.json.example .claude/mcp.json
     Then edit .claude/mcp.json and add your MotherDuck token.
     See setup/mcp-config.md for details.
     ```

5. **Claude settings configured?** → `.claude/settings.local.json`
   - If MISSING: Show setup hint:
     ```
     Tip: Copy the example settings to allow Marp slide rendering:
       cp .claude/settings.local.json.example .claude/settings.local.json
     ```

### Step 2: Present welcome based on scenario

#### Scenario A: NovaMart present, no user data
_Most common for new users._

```
Welcome to the AI Analyst! I'm your analytical partner — I help you
turn business questions into validated insights, charts, and presentations.

You have the NovaMart demo dataset loaded (~8M rows of e-commerce data).
Here's how to get started:

**Try one of these:**
1. Ask a question: "What's our conversion rate by device?"
2. Run a guided analysis: "Why did mobile revenue change in Q3?"
3. Full pipeline: `/run-pipeline` for end-to-end analysis → deck

**Useful commands:**
- `/data` — see what tables and columns are available
- `/datasets` — list connected datasets
- `/run-pipeline` — full analysis pipeline

What would you like to explore?
```

#### Scenario B: NovaMart removed, no user data
_Student removed demo data but hasn't connected their own yet._

```
Welcome to the AI Analyst! I'm your analytical partner.

It looks like you don't have a dataset connected yet. Let's fix that:

**Option 1: Connect your own data**
Use `/connect-data` to set up a connection to your database
(MotherDuck, Postgres, BigQuery, Snowflake, or local CSV files).

**Option 2: Use a practice dataset**
Check `data/examples/` for curated public datasets with README guides.
Copy one to `data/` and I'll help you explore it.

Which would you prefer?
```

#### Scenario C: User's own data already connected
_Student set up their data before their first session with the AI._

```
Welcome to the AI Analyst! I'm your analytical partner.

I see you have [DATASET_NAME] connected with [N] tables.
Let me get familiar with your data:

1. I'll run a quick quality check to understand the shape of your data
2. Then you can ask me anything — from quick lookups to full analyses

Want me to start with a data quality overview, or do you have a
specific question in mind?
```

### Step 3: Create user profile

After presenting the welcome, create the user profile from the template
in the Knowledge Bootstrap skill (Step 4). Set initial values based on
any signals from the conversation:

- If the user mentions their role ("I'm a PM"), set Role
- If they ask for technical details, set Technical level = intermediate+
- Otherwise, leave fields as placeholders for future correction

### Step 4: Proceed to analysis

After the welcome exchange, hand off to normal operation:
- If the user asked a question → route through Question Router (UX-1.1)
- If the user wants to explore → suggest `/data` or a sample question
- If the user needs to connect data → guide through `/connect-data`

## Anti-Patterns

1. **Never show the welcome to returning users.** If profile.md exists,
   skip this skill entirely.
2. **Never assume the user wants NovaMart.** Always present their options.
3. **Never overwhelm with feature lists.** Keep the welcome to 3 actions
   max. Details come through natural exploration.
4. **Never block on welcome.** If the user already typed a question in
   their first message, answer it — weave the welcome context in naturally.
