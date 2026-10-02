# Copilot Instructions for Gh0st / Beyond Binary AI

## Project Overview
Thin-slice dual-hemisphere antonym graph (cause / effect) with a center navigator and CLI. First seeded instance: hot/cold. Collapse into a single bit is not the endgame.

## Development Setup
- Python 3.10+ (stdlib only; no pip deps required for the thin slice)
- Run CLI: `python3 -m beyond_binary --help`
- Tests: `python3 -m unittest discover -s beyond_binary/tests -v`

## Architecture
- `beyond_binary/model.py` — Node, Torus, Hemisphere, CenterAction (provisional cause/effect jobs documented in-module)
- `beyond_binary/engine.py` — rules: no one-hemisphere answers, orphan→opposite immediately, no duplicates, merge/migrate
- `beyond_binary/store.py` — JSON persistence (`data/torus.json`)
- `beyond_binary/seed.py` — hot → boiling → water ↔ condensation cascade
- `beyond_binary/__main__.py` — CLI

## Things to Avoid
- One-hemisphere answers or orphan nodes without opposite-state links
- Speculative far-vision (sentience, islands poetry) beyond the outline's near path
- Bit-collapse as an end state
