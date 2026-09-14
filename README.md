# farming-agent
 
A single-file, rule-based agent (`main.py`) for **[Kaggriculture](https://www.kaggle.com/competitions/kaggriculture)**, the Kaggle × Google simulation competition. Two players each run a farm for a 30-day season (720 turns, 24 turns/day = 1 turn per in-game hour), managing crops, animals, hired labor, land, and a shared live market, trying to end the season with the largest bank.
 
This agent is fully deterministic — no training, no model weights. Every decision is a hand-tuned heuristic re-evaluated from scratch each turn (plus a small amount of memory to keep workers committed to multi-step tasks).
 
## How the agent is called
 
Kaggriculture calls a single function each turn:
 
```python
def agent(obs) -> dict:
    ...
```
 
`agent()` is a thin safety wrapper around `_inner()`: if anything throws, it falls back to a no-op turn (`{"farmer": ["PASS"], "hands": [], "market": []}`) instead of crashing the episode.
 
**Input (`obs`), as consumed by this file:**
- `obs["player"]` — this agent's seat index (0 or 1)
- `obs["day"]`, `obs["hour"]` — season clock
- `obs["farms"][player]` — this farm's `tiles` grid, `farmer` position, `hands` (hired worker positions), `money`, `unlocked_quadrants`
- `obs["farms"][1 - player]` — the opponent's farm (read-only, used for market-aware planning)
- `obs["private"]` — `inventories` (per-worker carried items), `shed` (stored goods), `seeds` (owned seed stock)
- `obs["market"]["prices"]` — current sell/buy prices per item
**Output:**
```python
{
  "farmer": [...],      # one action for the main farmer
  "hands": [[...], ...],# one action per hired hand, same order as obs
  "market": [[...], ...]# up to 10 economic actions this turn
}
```
 
Movement/work actions: `PASS`, `NORTH`/`SOUTH`/`EAST`/`WEST`, `PICKUP item qty`, `DROP`, `WATER`, `FERTILIZE`, `HARVEST`, `FEED`, `CARE`, `COLLECT_FERTILIZER`, `DIG`, `PLANT crop`, `PLACE animal`, `BUILD_COOP`, `BUILD_PASTURE`.
Market actions: `BUY_PRODUCT item qty`, `SELL item qty`, `HIRE`, `BUY_SEED crop qty`, `BUY_ANIMAL type qty`, `BUY_LAND`.
 
## Turn pipeline
 
Each call to `_inner(obs)` runs the same five stages:
 
### 1. Read the board
Walks the tile grid once, bucketing every tile into `plants`, `animals`, `weeds`, `empty_tiles`, and empty `COOP`/`PASTURE` structures, while counting wheat/melon plants and animals already placed. Also pulls shed stock, seed stock, and per-worker carried inventory.
 
### 2. Score the economy
- `pr(item, default)` reads a market price with a floor of 1 so nothing downstream divides by zero or goes negative.
- Per-animal expected value (`goose_ev`, `cow_ev`, `sheep_ev`) is computed as `product_yield × price + fertilizer_value − feed_cost`.
- `goose_ok` / `cow_ok` gate new purchases: EV is only "worth it" if the *remaining* days in the season can plausibly earn back the animal's cost. **Sheep are hard-disabled** (`sheep_ok = False`) — wool is scored but never bought or fed once the market for it looks bad (`wool_dead`), at which point existing sheep are quietly abandoned (no feed/harvest jobs generated for them).
- **Opponent awareness:** the agent peeks at the opponent's farm to count their cows, geese, and melons, and lowers its own caps (`cow_cap`, `goose_cap`, `melon_cap`) when the opponent already has a lot of one commodity — selling into a market the opponent is already flooding is a losing move.
- **Mirror-breaking:** if both farms currently look similar (`mirror_like`), the agent deterministically pushes seat `0` toward cows + melons and seat `1` toward geese, so two copies of the same agent don't play an identical, self-defeating game against each other.
- `shutdown` (day ≥ 30, or day 29 past hour 20) turns off all new investment — the rest of the season is spent finishing/selling only. `eod_rush` (hour ≥ 17) raises watering/feeding urgency so nothing dies overnight.
### 3. Build a job queue
Every actionable thing on the farm is turned into a `job = {op, pos, prio, arg, needs, needs_n}` (lower `prio` = more urgent):
 
| Priority | Typical jobs |
|---|---|
| 0 | Feeding an animal that's already gone a day unfed, urgent watering on a plant about to die |
| 1 | Routine care/feeding, placing purchased animals, harvesting perishable stock |
| 2 | Collecting fertilizer, routine watering, planting melon |
| 3 | Building coops/pastures, planting wheat |
| 4 | Weeding |
 
Jobs also declare a resource `needs` (e.g. `FEED` needs `WHEAT`) — a job is filtered out of the pool entirely if the shed/inventory can't supply it (`feasible()`).
 
### 4. Assign workers to jobs
- `_MEM` is a module-level dict keyed by `(seat, day, worker_index)` that remembers what each worker was doing last turn. If that job is still `valid()` and `feasible()`, the worker keeps it — this stops workers from re-planning mid-walk every single turn.
- Remaining workers and remaining jobs are matched greedily: `cost_for(worker, job)` = Manhattan distance + a priority penalty + an extra detour cost if the worker has to swing by the shed first to pick up a needed item.
- A second pass (`urgent`) lets priority-0 jobs **steal** a worker from any job with priority ≥ 2, so a dying crop or starving animal can interrupt something less important.
- Workers left with no job fall back to: carry a purchased animal to its structure → dig the nearest weed → return excess inventory to the shed → `PASS`.
- Any worker carrying ≥16 items (and not mid-delivery for their current job) is redirected to the shed to `DROP` before doing anything else, so inventories don't cap out.
- A final pass checks that enough seeds actually exist to cover every `PLANT` action queued this turn; any planting the seed stock can't cover is downgraded to `PASS` rather than issuing an invalid action.
### 5. Decide the market actions
Built as a list of `(priority, action)` intents, sorted, and truncated to the top 10:
 
1. **Restock wheat** if animal feed buffer is running low and price is reasonable.
2. **Sell** everything in the shed above a rolling reserve (reserve wheat for feed, reserve fertilizer), in a fixed sell-order (`SELL_PREF`) so staples aren't dumped ahead of higher-value goods.
3. **Hire hands** up toward a day-dependent headcount target, at a Fibonacci-scaled cost (`FIB`) so the crew grows early and cheaply, then gets expensive.
4. **Buy melon seed** only inside the profitable planting window(s) and only while melon isn't oversupplied.
5. **Buy animals**, ranked by EV-per-dollar, capped per type, opponent-aware, with a staggered opening (one cow day 0, one goose day 1) and a per-day purchase cap.
6. **Buy land** (unlock the next quadrant) once cash flow clears the price plus a safety buffer.
7. **Buy wheat seed** to keep total wheat plantings near the animal-feed-driven target.
## Key constants
 
| Name | Meaning |
|---|---|
| `TPD` | Turns per day (24 — one turn per in-game hour) |
| `SHED_TILES` / `SHED_SET` | The four central tiles that make up the shed (drop-off/pickup point) |
| `LAND_PRICES` | Cost of unlocking each additional quadrant, in order |
| `FIB` | Fibonacci sequence used to price each successive hire |
| `CROP_FY`, `CROP_MY`, `CROP_MAXY` | Per-crop day/yield thresholds that drive when a crop is watered, fertilized, and harvested |
| `ONGOING` | Crops (tomato, strawberry) that yield repeatedly rather than once at maturity |
| `ANIMAL_CAP_HELD` | Max yield units an animal can hold before harvesting becomes urgent |
| `ANIMAL_COST`, `ANIMAL_STRUCT` | Purchase price and required structure (coop/pasture) per animal |
| `SELL_PREF` | Fixed priority order for selling shed stock |
| `PLANT_LAST_DAY` | Last day a crop can still be planted and mature before season end |
| `_MEM` | Per-worker job memory across turns (module-level, process-lifetime) |
| `_PURCH` | Per-(seat, day) count of animals already bought, to enforce the daily purchase cap |
 
## State & concurrency note
 
`_MEM` and `_PURCH` are plain module-level dicts, not part of `obs`. This is safe under Kaggle's normal execution model (one long-lived process runs the agent for an entire episode), but it means:
- The agent is **not** safe to reuse across multiple simultaneous episodes in one process without namespacing these dicts by episode.
- `_MEM` self-prunes each turn (drops any entry not matching the current seat/day/worker count), so stale plans from a previous day or a worker that no longer exists never linger.
## Known simplifications / ideas for improvement
 
- Movement is a single greedy cardinal step toward the target each turn (`_step_toward`) — there's no multi-step pathfinding or collision avoidance around other workers/obstacles.
- No explicit look-ahead simulation of future prices or the opponent's likely moves beyond the current-turn opponent snapshot.
- Sheep/wool is permanently disabled (`sheep_ok = False`) rather than dynamically evaluated — worth revisiting if wool economics change.
- Thresholds (EV cutoffs, spend floors, caps) are hand-tuned constants rather than derived from a model; a natural next step is backtesting these against recorded ladder episodes to retune them.
## Submitting
 
Kaggriculture submissions are a single self-contained Python file exposing `agent(obs)`, matching this file's structure. Typical local smoke-testing uses the `kaggle_environments` package to run this file against the built-in baseline agents before submitting via the Kaggle CLI.
 
