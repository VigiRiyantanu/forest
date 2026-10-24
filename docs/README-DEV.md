# Animal Playground — Developer Guide

Welcome to the development documentation for **Animal Playground**, an autonomous 6-animal village operating entirely on Git commits.

---

## 1. How to Run Test Mode Locally

### Prerequisites
- Python 3.11+
- Git 2.20+
- (Optional) `pytest` for running unit test suite

### Running with Default Mock Provider
By default, the village runs using the built-in deterministic `mock` provider, requiring **no API keys** and making **no network requests**:

```bash
# Execute a single forced turn (dry-run mode without modifying files)
python -m src.tick --force

# Run a single turn live and commit
python -m src.tick --force

# Run the local autonomous test loop (re-reads config.json live, sleeps between turns)
python scripts/run_loop.py
```

### Resetting Repository State
To restore the repository back to initial state (clean history, empty memories, 3 seed topics):
```bash
python scripts/reset.py --yes
```

---

## 2. How to Set API Keys

When you want the village to use a real LLM provider (instead of `mock`), set the appropriate environment variables:

### Google Gemini (Recommended)
```bash
export LLM_PROVIDER="gemini"
export LLM_MODEL="gemini-1.5-flash"   # or gemini-2.0-flash
export GEMINI_API_KEY="your-gemini-api-key"
```

### Anthropic Claude
```bash
export LLM_PROVIDER="anthropic"
export LLM_MODEL="claude-3-5-haiku-latest"
export ANTHROPIC_API_KEY="your-anthropic-api-key"
```

### OpenAI
```bash
export LLM_PROVIDER="openai"
export LLM_MODEL="gpt-4o-mini"
export OPENAI_API_KEY="your-openai-api-key"
```

*Note: In Windows PowerShell, use `$env:LLM_PROVIDER="gemini"` and `$env:GEMINI_API_KEY="your-key"`.*

---

## 3. How to Switch to Prod Mode & Enable Workflow

### A. Update `config.json`
Change `"mode": "test"` to `"mode": "prod"`:
```json
{
  "mode": "prod",
  "interval_minutes": {
    "test": 1,
    "prod": 480
  },
  "tolerance_minutes": 10,
  "push": true
}
```
In `prod` mode, turns are spaced 480 minutes (8 hours) apart with a 10-minute tolerance window.

### B. Configure GitHub Repository Secrets
Under your GitHub repository **Settings → Secrets and variables → Actions**, add:
- `LLM_PROVIDER`: e.g. `gemini`
- `GEMINI_API_KEY`: your Google Gemini API key (or `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`)

### C. GitHub Actions Workflow
The workflow is located at `.github/workflows/tick.yml`. It runs automatically at 00:00, 08:00, and 16:00 WIB (UTC 17:00, 01:00, 09:00). You can also manually trigger a turn via GitHub Actions **Run workflow** button with optional `force: true`.

---

## 4. How to Edit the Cast

The cast is defined in `animals/cast.json`.

```json
[
  {
    "slug": "ayam-jantan",
    "name": "Ayam Jantan",
    "emoji": "🐓",
    "personality": "energetic, bossy, loud, loves organizing",
    "speech_style": "bersemangat, gemar memberi aba-aba, lugas dan tegas",
    "likes": ["jadwal harian", "ketertiban desa", "fajar menyingsing", "lumbung pakan"]
  }
]
```

### Rules when modifying the cast:
1. Maintain exactly 6 animals in the list to preserve the deterministic 6-turn cycle:
   - Index 0: Day A / pagi
   - Index 1: Day A / siang
   - Index 2: Day A / malam
   - Index 3: Day B / pagi
   - Index 4: Day B / siang
   - Index 5: Day B / malam
2. `slug` must be lowercase alphanumeric with hyphens (e.g. `burung-hantu`).
3. Ensure corresponding memory file `animals/<slug>.json` exists:
   ```json
   {
     "memory_lines": [],
     "relationships": {},
     "known_topics": []
   }
   ```
4. Run `python scripts/reset.py --yes` if you want a fresh start with the new cast.

---

## 5. Running the Acceptance Tests

Run the full pytest suite:
```bash
pytest -v
```
