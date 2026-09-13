# PulseHub Lead Finder (V1)

Outscraper -> deduplication/filtering -> Claude qualification -> SQLite -> CSV.

This V1 intentionally does **not** send emails or call Apollo. It is designed to validate lead quality first.

## Requirements

- Python 3.10+
- Outscraper API key
- Anthropic API key

Anthropic's current Python SDK supports structured outputs / `messages.parse()` with Pydantic models, which this project uses for reliable qualification JSON. See the current Claude structured-output docs: https://platform.claude.com/docs/en/build-with-claude/structured-outputs

Outscraper provides a Python SDK and Google Maps search methods for query-based place discovery. See: https://outscraper.com/hi/google-maps-scraping-in-python/

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill `.env`:

```env
OUTSCRAPER_API_KEY=...
ANTHROPIC_API_KEY=...
CLAUDE_MODEL=YOUR_VALID_CLAUDE_MODEL_ID
```

Do not commit `.env`.

## Configure searches

Edit `config.yaml`.

For your first run, keep the London example small. Each search is one Outscraper query. Increase limits after checking result quality.

## Run

```bash
python main.py run --config config.yaml
```

Outputs:

- `data/raw_leads.csv`
- `data/qualified_leads.csv`
- `data/pulsehub_leads.db`

By default `qualified_leads.csv` contains priority A and B leads only.

## Export later

```bash
python main.py export --priority A
python main.py export --priority B
python main.py export
```

## Notes

1. Outscraper is the discovery layer. Claude is only the qualification/classification layer.
2. The script does not invent email addresses or personal contact details.
3. The script does not automatically send outreach.
4. Validate a sample of Claude classifications before scaling.
5. Search/category results can overlap, so the app deduplicates by Place ID first.
6. Keep your usage within the terms and policies of the services you use and applicable outreach/privacy rules.
