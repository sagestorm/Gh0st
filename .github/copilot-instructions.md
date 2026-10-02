# Copilot Instructions for Gh0st / Beyond Binary AI

## Project Overview
Dual-hemisphere antonym graph (cause / effect) with a Living Center (`think`/`cycle`) that grows, repairs, dedupes, prunes, and logs. First instance: hot/cold thermal domain. Collapse into a single bit is not the endgame.

## Development Setup
- Python 3.10+ (stdlib only; no pip deps)
- Run CLI: `python3 -m beyond_binary --help`
- Living Center from minimal seed: `seed-minimal` → `think --steps 5` → `show` / `answer water` / `log`
- Tests: `python3 -m unittest discover -s beyond_binary/tests -v`

## Architecture
- `beyond_binary/model.py` — Node, Torus, Hemisphere, CenterAction
- `beyond_binary/engine.py` — rules: dual answers, orphan→opposite, no duplicates, merge/migrate
- `beyond_binary/lexicon.py` — built-in thermal cascade + alias groups (deterministic grow)
- `beyond_binary/center.py` — Living Center cycle: review→repair→grow→dedupe→synthesize→challenge→migrate→prune→log
- `beyond_binary/store.py` — torus JSON + activity log beside it (`*.center.jsonl`)
- `beyond_binary/seed.py` — `seed_minimal_hot_cold` / `seed_hot_cold`
- `beyond_binary/__main__.py` — CLI

## Things to Avoid
- One-hemisphere answers or orphan nodes without opposite-state links
- External LLMs for Phase 2 growth (lexicon only)
- Multi-domain universality / sentience cosplay beyond the outline's near path
- Bit-collapse as an end state
