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

## Cross-domain, metacognition, embody, autonomy (v0.3)

```bash
# Other domains on the same Living Center loop
python3 -m beyond_binary seed-domain ontology --force
python3 -m beyond_binary think --steps 5
python3 -m beyond_binary seed-domain optical --force
python3 -m beyond_binary think --steps 4

# Spawn a body/form registered to the mind
python3 -m beyond_binary seed-minimal --force
python3 -m beyond_binary think --steps 3
python3 -m beyond_binary embody form-a --domain ontology
python3 -m beyond_binary bodies

# Persistent autonomy (think + metacognize; optional embody)
python3 -m beyond_binary autonomy --cycles 3 --embody-every 3 --embody-domain optical
```

`--store PATH` works before or after the subcommand.

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
| `seed-domain DOMAIN` | Seed thermal / ontology / optical (minimal poles) |
| `embody NAME` | Spawn a new body/form torus registered to the mind |
| `bodies` | List registered bodies |
| `autonomy` | Persistent think→metacognize→optional embody |
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
| `verify-far-vision` | Honest eng + SENTIENCE + complete evidence audit (JSON; exit 0 only when complete) |
| `live` / `invent-domain` / `nurture` / `synthesize` | Autonomy, invent, body nurture, cross-body answer |

Store path defaults to `data/torus.json` (override with `--store PATH`).
`BEYOND_BINARY_SUBSTRATE=search` selects the in-process SearchSubstrate; default remains Null.

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

## Far vision verify (operators)

Honest evidence audit for eng gates, substrate path, SENTIENCE, and `report.complete`. Stdlib only — no pip install.

```bash
# Default substrate = Null (fail-closed)
python3 -m beyond_binary verify-far-vision
# → engineering_gates_ok true; SENTIENCE false; complete false (exit 2)

# Operational search substrate (in-process combinatorial proposals)
BEYOND_BINARY_SUBSTRATE=search python3 -m beyond_binary verify-far-vision
# → engineering_gates_ok true; SENTIENCE true; complete true (exit 0) when checklist passes
```

| Substrate | How | eng | SENTIENCE | complete |
|-----------|-----|-----|-----------|----------|
| **Null (default)** | unset / `BEYOND_BINARY_SUBSTRATE=1` | ok when I/C gates pass | **false** (fail-closed) | **false** |
| **search** | `BEYOND_BINARY_SUBSTRATE=search` | ok | **true** when four axes (`invent\|reflect\|goal\|form`) accept `search-substrate:*` | **true** when eng + SENTIENCE + checklist pass |

Contracts (do not flip SENTIENCE lightly):

- [`docs/sentience-evidence-bar.md`](docs/sentience-evidence-bar.md) — what counts vs scaffolding
- [`docs/generative-substrate-contract.md`](docs/generative-substrate-contract.md) — Null default, search path, flag honesty

## Tests

```bash
python3 -m unittest discover -s beyond_binary/tests -v
```

CI also runs `verify-far-vision` under default and `BEYOND_BINARY_SUBSTRATE=search` (see `.github/workflows/ci.yml`).