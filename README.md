# Beyond Binary AI

Dual-hemisphere antonym graph with a **Living Center**: cause / effect hemispheres, a median navigator that grows and maintains structure, and a CLI. First instance: **hot / cold** (thermal domain).

Collapse into a single bit is not the endgame. Answers always span both hemispheres. Orphans link to an opposite state immediately. Growth is paired with dedupe and prune.

## Setup

Python 3.10+ (stdlib only). From the repo root:

```bash
python3 -m beyond_binary --help
```

## Living Center quick start (from minimal seed)

```bash
# Poles only — hot ↔ cold
python3 -m beyond_binary seed-minimal --force

# Center cycles: review → repair → grow → dedupe → synthesize → challenge → migrate → prune → log
python3 -m beyond_binary think --steps 5

# Grown dual structure (boiling/freezing/water/condensation, …)
python3 -m beyond_binary show

# Dual-hemisphere answer
python3 -m beyond_binary answer water

# Inspect center activity (persisted beside the torus JSON)
python3 -m beyond_binary log
```

Activity log path defaults to `data/torus.center.jsonl` when the store is `data/torus.json`.

## Full cascade seed (optional)

```bash
python3 -m beyond_binary seed-hot-cold --force
python3 -m beyond_binary show
python3 -m beyond_binary answer water
python3 -m beyond_binary center review hot
```

## CLI

| Command | Purpose |
|---------|---------|
| `init` | Empty torus store |
| `seed-minimal` | Hot↔cold poles only (for `think` growth) |
| `seed-hot-cold` | Full first-instance cascade |
| `think [--steps N]` | Run N Living Center cycles |
| `cycle` | One center cycle |
| `log` / `center-history` | Persisted center activity |
| `add-pair CAUSE EFFECT` | Antonym pair across hemispheres |
| `add-under PARENT CHILD` | Nest under a pole; links opposite immediately |
| `link-opposite A B` | Cross-hemisphere opposite-state link |
| `merge SOURCE TARGET` | Dedupe within a hemisphere (also absorbs opposite pair) |
| `migrate-link NODE [--parent P] [--opposite O]` | Proven better links |
| `show` | Print structure |
| `answer TOPIC` | Trace both hemisphere paths |
| `center ACTION [TOPIC]` | Manual center act: review / synthesize / challenge / experiment / add / prune / retrieve / save |

Store path defaults to `data/torus.json` (override with `--store PATH`).

## Core rules (enforced)

- **Dual answers** — `answer` and topic-bearing center acts require an opposite-state link across hemispheres.
- **Orphan → opposite immediately** — `add-under` and each `think` cycle repair orphans.
- **No duplicates** — normalized names; center dedupe merges lexicon aliases; use `merge` / `migrate-link` instead of pile-on.
- **Economy** — each cycle pairs grow with dedupe/prune; domain-capped thermal lexicon; soft node cap.
- **Mutable organization** — experiment/migrate keeps a change only when provisional structural score does not regress.

## Provisional hemisphere jobs

Documented in `beyond_binary/model.py` (easy to rename later):

- **cause** — initiating / generative pole of an antonym pair
- **effect** — reciprocal / consequent pole of that pair

## Tests

```bash
python3 -m unittest discover -s beyond_binary/tests -v
```
