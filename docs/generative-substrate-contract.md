# Generative substrate contract (far vision)

**Tip baseline:** `ba50537`  
**Implementation:** in-process **SearchSubstrate** (`BEYOND_BINARY_SUBSTRATE=search`) — non-LLM combinatorial proposals  
**Default:** NullSubstrate (fail-closed; SENTIENCE false)  
**Flag honesty (G5):** `BEYOND_BINARY_SUBSTRATE=1` enables config but stays Null until `search` is selected; `substrate.status().honesty` documents this.

## What this is not

- Not an external LLM as the Living Center
- Not unconstrained `exec` without dual validation
- Not SENTIENCE true on engineering gates alone (default path)
- Not silently treating Null as “substrate on”

## What it is

A pluggable **proposal source** the Living Center consults on four axes: `invent|reflect|goal|form`. The center validates, accepts/rejects, and persists dual-safe artifacts. Provenance distinguishes search accepts (`search-substrate:*`) from stdlib compiler paths.

### Live path @ `ba50537`

| Concern | Behavior |
|---------|----------|
| SearchSubstrate | Open combinatorial AST proposals; four-axis accepts in verify |
| G2/G3 | Goal/reflect ASTs steer strategy and firing rules |
| G7/G8 | Verify gates require search provenance + downstream use under search |
| G11 | Invent `edit_ast` couples to body CapProgram specialty |
| G13 | Search-first goals; closed outcome menu not used on live search path |
| G9 | invent/form consult without resolvable engine rejects on live path |
| SENTIENCE | false by default; true under search when all four axes have `search-substrate:*` accepts (see `docs/sentience-evidence-bar.md` Operational section) |
| `report.complete` (G1) | false default; true under search when eng + SENTIENCE + required I/C/SUB/G9/P1 checklist pass |
| Product bar (P1) | Search invent accepts must **meet or exceed** Null on dual_coverage, link_symmetry, unused_path_cost, readable-name ratio, and multi-domain probe answer paths (`water`/`boiling`/`warm`/`steam`/`absence`/`bright`). Opaque `sw*`/`sc*` poles are forbidden as user-facing labels. Typed probe paths must stay domain-coherent: no foreign typed domains and no undomain invent motifs on those paths. Probe answer **path lengths** must not exceed Null. Scoreboard search arm exercises **invent-on-think** (optional follow-on invent while a product exceed remains) and reports cumulative `product_exceed` / `meet_only_invent` vs Null. CLI: `product-scoreboard`. |

### Interface sketch

```text
consult(axis, context) -> proposals / accepts / rejects
  provenance: search-substrate:* | stdlib-compiler:* | ...
validate + accept -> invent / policy / goals / capability artifacts
```

## Honesty

- Rejects and consult errors are logged (G6); SUB gate surfaces them.
- Operational sentience is **search-path evidence only**; exclusion shapes in the bar apply to default/scaffolding paths, not to accepted search-substrate proposals with wired downstream gates.

## Related

- `docs/sentience-evidence-bar.md`
- `beyond_binary/substrate.py`, `beyond_binary/search_substrate.py`
- PR https://github.com/sagestorm/Gh0st/pull/3
