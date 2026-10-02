# Beyond Binary AI

Thin-slice dual-hemisphere antonym graph: **cause** / **effect** hemispheres, a **center** navigator, and a CLI. First seeded instance: **hot / cold**.

Living outline (project store): see coordinator docs for intent and rules. Collapse into a single bit is not the endgame; answers always span both hemispheres.

## Setup

Python 3.10+ (stdlib only). From the repo root:

```bash
python3 -m beyond_binary --help
```

## Quick start

```bash
# Load the first hot/cold synonym cascade into data/torus.json
python3 -m beyond_binary seed-hot-cold --force

# Show both hemispheres + opposite-state links
python3 -m beyond_binary show

# Dual-hemisphere answer (never one side only)
python3 -m beyond_binary answer water

# Center navigation hooks
python3 -m beyond_binary center review hot
python3 -m beyond_binary center challenge boiling
```

## CLI (minimum useful set)

| Command | Purpose |
|---------|---------|
| `init` | Empty torus store |
| `seed-hot-cold` | First instance cascade |
| `add-pair CAUSE EFFECT` | Antonym pair across hemispheres |
| `add-under PARENT CHILD` | Nest under a pole; links opposite immediately |
| `link-opposite A B` | Cross-hemisphere opposite-state link |
| `merge SOURCE TARGET` | Dedupe within a hemisphere (also absorbs opposite pair) |
| `migrate-link NODE [--parent P] [--opposite O]` | Proven better links |
| `show` | Print structure |
| `answer TOPIC` | Trace both hemisphere paths |
| `center ACTION [TOPIC]` | review / synthesize / challenge / experiment / add / prune / retrieve / save |

Store path defaults to `data/torus.json` (override with `--store PATH`).

## Core rules (enforced)

- No one-hemisphere answers — `answer` and topic-bearing `center` acts require an opposite-state link.
- Orphans must link opposite immediately — `add-under` creates or binds an opposite; `assert_no_orphans` after merge/migrate.
- No duplicates — normalized names; use `merge` / `migrate-link` instead of pile-on.
- Simple → complex without collapse — nesting under poles + mutable opposite links.

## Provisional hemisphere jobs

Documented in `beyond_binary/model.py` (easy to rename later):

- **cause** — initiating / generative pole of an antonym pair
- **effect** — reciprocal / consequent pole of that pair

## Tests

```bash
python3 -m unittest discover -s beyond_binary/tests -v
```
