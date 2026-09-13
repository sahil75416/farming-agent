TPD = 24
SHED_TILES = [(4, 4), (5, 4), (4, 5), (5, 5)]
SHED_SET = set(SHED_TILES)
LAND_PRICES = [1000, 2000, 4000]
FIB = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377]

CROP_FY = {"WHEAT": 2, "CARROT": 2, "TOMATO": 8, "STRAWBERRY": 10, "MELON": 10}
CROP_MY = {"WHEAT": 4, "CARROT": 3, "TOMATO": 8, "STRAWBERRY": 10, "MELON": 12}
CROP_MAXY = {"WHEAT": 6, "CARROT": 4, "TOMATO": 4, "STRAWBERRY": 4, "MELON": 6}
ONGOING = ("TOMATO", "STRAWBERRY")
ANIMAL_CAP_HELD = {"GOOSE": 4, "COW": 6, "SHEEP": 6}

ANIMAL_COST = {"GOOSE": 300, "COW": 400, "SHEEP": 500}
ANIMAL_STRUCT = {"GOOSE": "COOP", "COW": "PASTURE", "SHEEP": "PASTURE"}

SELL_PREF = ["MILK", "EGG", "MELON", "WOOL", "STRAWBERRY", "TOMATO", "CARROT", "FERTILIZER", "WHEAT"]
PLANT_LAST_DAY = {"WHEAT": 25, "MELON": 19}

_MEM = {}
_PURCH = {}


def _man(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _step_toward(pos, tgt):
    dx = tgt[0] - pos[0]
    dy = tgt[1] - pos[1]
    if dx == 0 and dy == 0:
        return ["PASS"]
    if abs(dx) >= abs(dy):
        return ["EAST"] if dx > 0 else ["WEST"]
    return ["SOUTH"] if dy > 0 else ["NORTH"]


def _nearest(pos, pts):
    best = None
    bk = None
    for p in pts:
        k = (_man(pos, p), p)
        if bk is None or k < bk:
            bk, best = k, p
    return best


def _nearest_shed(pos):
    return _nearest(pos, SHED_TILES)


def agent(obs):
    try:
        return _inner(obs)
    except Exception:
        return {"farmer": ["PASS"], "hands": [], "market": []}


def _inner(obs):
    me = obs["player"]
    day = int(obs.get("day", 0))
    hour = int(obs.get("hour", 0))
    farm = obs["farms"][me]
    private = obs["private"]
    prices = obs["market"]["prices"]
    tiles = farm["tiles"]

    worker_pos = [tuple(farm["farmer"])] + [tuple(h) for h in farm.get("hands", [])]
    invs = private.get("inventories", [])
    n_workers = len(worker_pos)

    plants = []
    animals = []
    weeds = []
    empty_tiles = []
    empty_structs = {"COOP": [], "PASTURE": []}
    n_placed = {"GOOSE": 0, "COW": 0, "SHEEP": 0}
    n_wheat = 0
    n_melon = 0
    tile_map = {}

    for y in range(len(tiles)):
        row = tiles[y]
        for x in range(len(row)):
            t = row[x]
            tile_map[(x, y)] = t
            if t is None:
                empty_tiles.append((x, y))
            elif t == "LOCKED" or not isinstance(t, dict):
                continue
            else:
                k = t.get("kind")
                if k == "PLANT":
                    plants.append((x, y, t))
                    if t.get("crop") == "WHEAT":
                        n_wheat += 1
                    elif t.get("crop") == "MELON":
                        n_melon += 1
                elif k == "WEED":
                    weeds.append((x, y))
                elif k in ("COOP", "PASTURE"):
                    a = t.get("animal")
                    if a:
                        animals.append((x, y, t))
                        n_placed[a] += 1
                    else:
                        empty_structs[k].append((x, y))

    shed = private.get("shed") or {}
    seeds = private.get("seeds") or {}
    n_animals = sum(n_placed.values())
    in_shed = {a: int(shed.get(a, 0)) for a in ANIMAL_COST}
    shed_wheat = int(shed.get("WHEAT", 0))
    shed_fert = int(shed.get("FERTILIZER", 0))

    def pr(item, dflt):
        try:
            return max(1.0, float(prices.get(item, dflt)))
        except Exception:
            return float(dflt)

    p_fert = pr("FERTILIZER", 100)
    R = 29 - day
    shutdown = (day >= 30) or (day == 29 and hour >= 20)
    eod_rush = hour >= 17

    feed_cost = min(pr("WHEAT", 25), 40.0)
    goose_ev = 2.0 * pr("EGG", 50) + p_fert - feed_cost
    cow_ev = 1.5 * pr("MILK", 160) + p_fert - feed_cost
    sheep_ev = 1.3333 * pr("WOOL", 200) + p_fert - feed_cost
    goose_ok = (R - 3) * goose_ev >= 350
    cow_ok = (R - 9) * cow_ev >= 550
    
    sheep_ok = False

    # opponent-aware caps: don't race them into the same product
    try:
        opp_farm = obs["farms"][1 - me]
        opp_cows = opp_geese = opp_melons = 0
        for row in opp_farm["tiles"]:
            for t in row:
                if isinstance(t, dict):
                    if "animal" in t:
                        if t["animal"] == "COW":
                            opp_cows += 1
                        elif t["animal"] == "GOOSE":
                            opp_geese += 1
                    elif t.get("kind") == "PLANT" and t.get("crop") == "MELON":
                        opp_melons += 1
    except Exception:
        opp_cows = opp_geese = opp_melons = 0
    cow_cap = 12 if opp_cows <= 6 else 8
    goose_cap = 14 if opp_geese <= 6 else 9
    melon_cap = 8 if opp_melons <= 3 else 5
    # break mirror symmetry deterministically so clones specialize apart
    try:
        mirror_like = (abs(opp_cows - n_placed["COW"]) <= 1
                       and abs(opp_geese - n_placed["GOOSE"]) <= 1)
    except Exception:
        mirror_like = False
    if mirror_like:
        if me == 0:
            cow_cap += 3
            melon_cap = min(melon_cap + 2, 8)
        else:
            goose_cap += 3
            melon_cap = max(melon_cap - 2, 3)

    wheat_target = min(36, 14 + int(n_animals * 1.5))
    melon_window = (day <= 8) or (10 <= day <= 16)
    melon_active = n_melon + int(seeds.get("MELON", 0))

    # ---------------- build jobs ----------------
    jobs = []

    def add(op, pos, prio, arg=None, needs=None, needs_n=1):
        jobs.append({"op": op, "pos": tuple(pos), "prio": int(prio),
                     "arg": arg, "needs": needs, "needs_n": needs_n})

    reserved_build = []
    if not shutdown:
        owned_g = n_placed["GOOSE"] + in_shed["GOOSE"]
        owned_c = n_placed["COW"] + in_shed["COW"]
        owned_s = n_placed["SHEEP"] + in_shed["SHEEP"]
        want_g = min(14, owned_g + 1) if (goose_ok and day <= 24) else owned_g
        want_c = min(12, owned_c + 1) if (cow_ok and day <= 20) else owned_c
        want_s = min(6, owned_s + 2) if sheep_ok else owned_s
        struct_total = {"COOP": len(empty_structs["COOP"]), "PASTURE": len(empty_structs["PASTURE"])}
        for (_x, _y, t) in animals:
            struct_total[t["kind"]] += 1
        bw_coop = max(0, min(2, want_g - struct_total["COOP"]))
        bw_past = max(0, min(2, (want_c + want_s) - struct_total["PASTURE"]))
        open_sorted = sorted((c for c in empty_tiles if c not in SHED_SET),
                             key=lambda c: (_man(c, (4, 4)), c[1], c[0]))
        for c in open_sorted:
            if bw_coop > 0:
                reserved_build.append((c, "BUILD_COOP"))
                bw_coop -= 1
            elif bw_past > 0:
                reserved_build.append((c, "BUILD_PASTURE"))
                bw_past -= 1
            else:
                break
    built_set = set(c for c, _o in reserved_build)
    for (c, op) in reserved_build:
        add(op, c, 3)

    # ---------------- animal jobs ----------------
    unfed_cnt = 0
    wool_dead = pr("WOOL", 200) < 45 and day >= 14
    for (x, y, t) in animals:
        pos = (x, y)
        is_freed_sheep = wool_dead and t.get("animal") == "SHEEP"
        if not t.get("fed_today", False):
            unfed_cnt += 1
            if not is_freed_sheep:
                add("FEED", pos, 0 if (t.get("consecutive_unfed", 0) >= 1 or eod_rush or hour >= 12) else 1,
                    needs="WHEAT", needs_n=10)
        if not t.get("cared_today", False):
            add("CARE", pos, 1)
        if t.get("fertilizer_available", False):
            add("COLLECT_FERTILIZER", pos, 2)
        yu = t.get("yield_units", 0)
        if yu > 0 and not (is_freed_sheep):
            add("HARVEST", pos, 1 if yu >= ANIMAL_CAP_HELD.get(t.get("animal"), 6) else 2)

    # ---------------- placement jobs ----------------
    if not shutdown:
        for a_type in ("COW", "GOOSE", "SHEEP"):
            cnt = in_shed[a_type]
            if cnt <= 0:
                continue
            for spot in empty_structs[ANIMAL_STRUCT[a_type]][:cnt]:
                add("PLACE", spot, 1, arg=a_type, needs=a_type, needs_n=cnt)

    # ---------------- plant jobs ----------------
    def water_useful(crop, planted):
        if day < 27 or crop not in PLANT_LAST_DAY:
            return True
        return (planted + CROP_MY[crop]) <= 29

    for (x, y, t) in plants:
        pos = (x, y)
        crop = t["crop"]
        planted = t.get("planted_day", day)
        age = day - planted
        yu = t.get("yield_units", 0)
        dying = t.get("consecutive_unwatered", 0) >= 1
        if crop == "MELON":
            in_sched = (age <= 4 and age % 2 == 0) or (6 <= age <= CROP_MY["MELON"])
        elif crop in ONGOING:
            in_sched = True
        else:
            ws = (CROP_MY[crop] + 1) // 2
            in_sched = ws <= age <= CROP_MY[crop]
        if (not t.get("watered_today", False)) and age <= CROP_MY[crop] and water_useful(crop, planted):
            if dying or in_sched:
                urgent = dying or (crop != "MELON" and age == CROP_MY[crop]) or eod_rush
                add("WATER", pos, 0 if urgent else 2)
        if crop == "WHEAT" and age in (1, 2) and t.get("fertilized_until_day", -1) < day and planted <= 25:
            add("FERTILIZE", pos, 1, needs="FERTILIZER", needs_n=4)
        do_harvest = False
        late = False
        if crop in ONGOING:
            do_harvest = yu > 0
        elif crop == "MELON":
            if age >= 11 or (age >= CROP_FY["MELON"] and yu > 1):
                do_harvest = True
                late = age >= 12
        else:
            if age >= CROP_MY[crop]:
                do_harvest = True
                late = age >= CROP_MY[crop] + 1
            elif yu >= CROP_MAXY[crop]:
                do_harvest = True
        if do_harvest and yu > 0:
            add("HARVEST", pos, 1 if late else 3)

    # ---------------- new planting jobs ----------------
    if not shutdown and day <= 25:
        rem_spots = [c for c in sorted((c for c in empty_tiles if c not in SHED_SET and c not in built_set),
                                       key=lambda c: (_man(c, (4, 4)), c[1], c[0]))]
        melon_n = 0
        if melon_window and pr("MELON", 250) >= 140 and day <= PLANT_LAST_DAY["MELON"]:
            melon_n = max(0, min(int(seeds.get("MELON", 0)), 8 - n_melon))
        wheat_n = max(0, min(int(seeds.get("WHEAT", 0)), wheat_target - n_wheat,
                             len(rem_spots) - melon_n))
        for c in rem_spots[:melon_n]:
            add("PLANT", c, 2, arg="MELON")
        for c in rem_spots[melon_n:melon_n + wheat_n]:
            add("PLANT", c, 3, arg="WHEAT")

    # ---------------- weeds ----------------
    if not shutdown:
        for wp in sorted(weeds, key=lambda p: (_man(p, (4, 4)), p))[:16]:
            add("DIG", wp, 4)

    # ---------------- feasibility + commitment ----------------
    inv_wheat_all = sum(int(i.get("WHEAT", 0)) for i in invs) if invs else 0

    def feasible(j):
        if j["op"] == "FEED":
            return shed_wheat + inv_wheat_all > 0
        if j["op"] == "FERTILIZE":
            return shed_fert + sum((i.get("FERTILIZER", 0) for i in invs), 0) > 0
        if j["op"] == "PLACE":
            return True
        return True

    pool = [j for j in jobs if feasible(j)]

    for key in list(_MEM.keys()):
        if key[0] != me or key[1] != day or key[2] >= n_workers:
            del _MEM[key]

    def sig(j):
        return (j["op"], j["pos"][0], j["pos"][1], j.get("arg"))

    def valid(j):
        pos = j["pos"]
        tl = tile_map.get(pos)
        op = j["op"]
        if op in ("BUILD_COOP", "BUILD_PASTURE"):
            return tl is None
        if op == "PLANT":
            return tl is None and int(seeds.get(j.get("arg"), 0)) > 0
        if op == "DIG":
            return isinstance(tl, dict) and tl.get("kind") == "WEED"
        if op == "PLACE":
            return (isinstance(tl, dict) and tl.get("kind") == ANIMAL_STRUCT.get(j.get("arg"))
                    and "animal" not in tl)
        if not isinstance(tl, dict):
            return False
        if op == "WATER":
            if tl.get("kind") != "PLANT" or tl.get("watered_today"):
                return False
            return (day - tl.get("planted_day", day)) <= CROP_MY[tl["crop"]]
        if op == "FERTILIZE":
            return (tl.get("kind") == "PLANT" and tl.get("crop") == "WHEAT"
                    and (day - tl.get("planted_day", day)) in (1, 2)
                    and tl.get("fertilized_until_day", -1) < day)
        if op == "HARVEST":
            return tl.get("yield_units", 0) > 0
        if op == "FEED":
            return "animal" in tl and not tl.get("fed_today", True)
        if op == "CARE":
            return "animal" in tl and not tl.get("cared_today", True)
        if op == "COLLECT_FERTILIZER":
            return "animal" in tl and bool(tl.get("fertilizer_available"))
        return False

    def cost_for(w, j):
        pos = worker_pos[w]
        c = _man(pos, j["pos"]) + j["prio"] * 6
        if j["needs"]:
            have = int(invs[w].get(j["needs"], 0)) if w < len(invs) else 0
            if have < 1:
                ns = _nearest_shed(pos)
                c += _man(pos, ns) + _man(ns, j["pos"])
        return c

    kept = {}
    claimed = set()
    for w in range(n_workers):
        j = _MEM.get((me, day, w))
        if j is not None and valid(j) and feasible(j):
            kept[w] = j
            claimed.add(sig(j))
        else:
            _MEM.pop((me, day, w), None)

    pool = [j for j in pool if sig(j) not in claimed]

    # urgency preemption for prio-0 jobs
    urgent = [j for j in pool if j["prio"] <= 0]
    if urgent:
        urgent.sort(key=lambda j: min(cost_for(w, j) for w in range(n_workers)))
        for j in urgent:
            victim, vc = None, None
            for w, kj in kept.items():
                if kj["prio"] <= 1:
                    continue
                c = cost_for(w, j)
                if vc is None or c < vc:
                    vc, victim = c, w
            if victim is not None:
                kept[victim] = j
                _MEM[(me, day, victim)] = j
                claimed.add(sig(j))
                pool.remove(j)

    free = [w for w in range(n_workers) if w not in kept]
    scored = []
    for idx, j in enumerate(pool):
        best = min((cost_for(w, j) for w in free), default=None)
        if best is not None:
            scored.append((j["prio"], best, idx))
    scored.sort()

    for (_p, _c, idx) in scored:
        j = pool[idx]
        bw, bc = None, None
        for w in free:
            cw = cost_for(w, j)
            if bc is None or cw < bc:
                bc, bw = cw, w
        if bw is not None:
            kept[bw] = j
            _MEM[(me, day, bw)] = j
            free.remove(bw)

    # ---------------- execute ----------------
    actions = []
    for w in range(n_workers):
        pos = worker_pos[w]
        inv = invs[w] if w < len(invs) else {}
        j = kept.get(w)
        inv_total = sum(int(v) for v in inv.values()) if inv else 0
        holds_animal = any(k in ANIMAL_COST for k in inv) if inv else False
        act = ["PASS"]

        if (not shutdown) and (not holds_animal) and inv_total >= 16:
            carry_for_job = j is not None and j["needs"] and int(inv.get(j["needs"], 0)) > 0
            if not carry_for_job:
                if pos in SHED_SET:
                    actions.append(["DROP"])
                    continue
                actions.append(_step_toward(pos, _nearest_shed(pos)))
                continue

        if j is not None:
            if j["needs"] and int(inv.get(j["needs"], 0)) < 1 and not holds_animal:
                avail = int(shed.get(j["needs"], 0))
                if avail > 0:
                    if pos in SHED_SET:
                        act = ["PICKUP", j["needs"], min(avail, j["needs_n"])]
                    else:
                        act = _step_toward(pos, _nearest_shed(pos))
                else:
                    act = ["PASS"]
            elif pos == j["pos"]:
                op = j["op"]
                if op in ("BUILD_COOP", "BUILD_PASTURE", "WATER", "HARVEST", "FEED",
                          "CARE", "COLLECT_FERTILIZER", "FERTILIZE", "DIG"):
                    act = [op]
                elif op in ("PLANT", "PLACE"):
                    act = [op, j["arg"]]
                else:
                    act = ["PASS"]
            else:
                act = _step_toward(pos, j["pos"])
        else:
            if (not shutdown) and holds_animal:
                a_type = next(k for k in ANIMAL_COST if inv.get(k, 0) > 0)
                spots = empty_structs[ANIMAL_STRUCT[a_type]]
                if spots:
                    tgt = _nearest(pos, spots)
                    act = ["PLACE", a_type] if pos == tgt else _step_toward(pos, tgt)
                else:
                    act = ["PASS"]
            elif (not shutdown) and weeds:
                wp = _nearest(pos, [w for w in weeds])
                act = ["DIG"] if pos == wp else _step_toward(pos, wp)
            elif inv_total > 0:
                ns = _nearest_shed(pos)
                act = ["DROP"] if pos in SHED_SET else _step_toward(pos, ns)
            else:
                act = ["PASS"]
        actions.append(act)

    farmer_action = actions[0]
    hands_actions = actions[1:]

    demand = {}
    for a in [farmer_action] + hands_actions:
        if a[0] == "PLANT":
            demand[a[1]] = demand.get(a[1], 0) + 1
    for crop, n in list(demand.items()):
        have = int(seeds.get(crop, 0))
        excess = n - have
        for i in range(len(actions)):
            if excess <= 0:
                break
            if actions[i][0] == "PLANT" and actions[i][1] == crop:
                actions[i] = ["PASS"]
                excess -= 1
    farmer_action = actions[0]
    hands_actions = actions[1:]

    # ---------------- market ----------------
    intents = []
    money = float(farm["money"])

    # wheat supply: keep a rolling buffer; rescue when critical
    inv_wheat = inv_wheat_all
    if (not shutdown) and n_animals > 0:
        want_stock = n_animals + 6
        stock = shed_wheat + inv_wheat
        if stock < want_stock and pr("WHEAT", 25) <= 70 and money >= 60:
            buy = min(10, want_stock - stock)
            if money >= buy * pr("WHEAT", 25):
                money -= buy * pr("WHEAT", 25)
                intents.append((0, ["BUY_PRODUCT", "WHEAT", buy]))

    reserve_wheat = (n_animals + 6) if day < 29 else 0
    reserve_fert = 6 if day <= 25 else 0
    reserves = {"WHEAT": reserve_wheat, "FERTILIZER": reserve_fert}
    for item in SELL_PREF:
        q = int(shed.get(item, 0)) - reserves.get(item, 0)
        if q > 0:
            intents.append((1, ["SELL", item, q]))

    hired = 0
    if day <= 24:
        target_hands = min(12, 3 + day)
    elif day <= 26:
        target_hands = 8
    else:
        target_hands = 3
    while (n_workers - 1 + hired) < target_hands:
        idx = min(n_workers - 1 + hired, len(FIB) - 1)
        c = FIB[idx]
        if money < c + 80:
            break
        money -= c
        intents.append((2, ["HIRE"]))
        hired += 1

    SPEND_FLOOR = 500 if day < 6 else (400 if day < 10 else 150)
    if (not shutdown) and melon_window and pr("MELON", 250) >= 140 and melon_active < melon_cap \
            and 1 <= day <= 16:
        mbuy = min(melon_cap - melon_active, melon_cap)
        if mbuy > 0 and money >= mbuy * 80 + SPEND_FLOOR:
            money -= mbuy * 80
            intents.append((3, ["BUY_SEED", "MELON", mbuy]))

    if not shutdown:
        pk = (me, day)
        bought_today = _PURCH.get(pk, 0)
        total_animals = n_animals + sum(in_shed.values())
        wheat_support = int(n_wheat * 1.2) + 8
        max_buys_today = 3 if money > 3000 else 2
        buys = []
        for a_type, ev, ok, cap in (("COW", cow_ev, cow_ok, cow_cap),
                                    ("GOOSE", goose_ev, goose_ok, goose_cap)):
            if not ok:
                continue
            owned = n_placed[a_type] + in_shed[a_type]
            if owned >= cap or total_animals >= 28:
                continue
            # staggered opening: one cow on day 0, one goose on day 1
            if day == 0 and a_type != "COW":
                continue
            if day == 1 and a_type == "COW" and owned + total_animals >= 2:
                continue
            if total_animals + 1 > wheat_support + 4:
                continue
            empty_for = len(empty_structs[ANIMAL_STRUCT[a_type]])
            pend = 1 if any(o == "BUILD_" + ANIMAL_STRUCT[a_type] for _c, o in reserved_build) else 0
            if empty_for <= 0 and pend <= 0:
                continue
            if money >= ANIMAL_COST[a_type] + SPEND_FLOOR:
                buys.append(((ev / ANIMAL_COST[a_type]), a_type))
        buys.sort(reverse=True)
        for _s, a_type in buys[:2]:
            if bought_today >= max_buys_today:
                break
            money -= ANIMAL_COST[a_type]
            intents.append((4, ["BUY_ANIMAL", a_type, 1]))
            bought_today += 1
        _PURCH[pk] = bought_today

    # land: expand steadily once there is cash flow; animals still claim capital first
    quads = farm.get("unlocked_quadrants", ["NW"])
    n_extra = len(quads) - 1
    if n_extra < 3 and 5 <= day <= 22 and money >= LAND_PRICES[n_extra] + 900 + SPEND_FLOOR:
        money -= LAND_PRICES[n_extra]
        intents.append((5, ["BUY_LAND"]))

    if not shutdown:
        wheat_seed_need = max(0, min(wheat_target - n_wheat - int(seeds.get("WHEAT", 0)), 12))
        if wheat_seed_need > 0 and day <= 25 and money >= wheat_seed_need * 10 + max(100, SPEND_FLOOR - 250):
            money -= wheat_seed_need * 10
            intents.append((6, ["BUY_SEED", "WHEAT", wheat_seed_need]))

    intents.sort(key=lambda x: x[0])
    market = [o for (_p, o) in intents[:10]]

    return {"farmer": farmer_action, "hands": hands_actions, "market": market}
