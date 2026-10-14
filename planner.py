import heapq
import random

W, H = 15, 15
START = (0, 0)
BEACON = (14, 14)
DEPOTS = ((7, 7), (3, 11), (11, 3))
FRIEND = (2, 5)                                   # friend trapped in a shop
WALLS = (
    {(5, y) for y in range(0, 10)}                # building with a gap at the bottom
    | {(10, y) for y in range(5, 15)}             # building with a gap at the top
    | {(8, 2), (8, 3), (8, 4)}                    # ruins
)
RESERVED = {START, BEACON, FRIEND, *DEPOTS}
MAX_FOOD = 20
MAX_WATER = 20
HORDE_FOOD_COST = 2
HORDE_TIME_COST = 5
RUNNER_TIME_COST = 2
FRIEND_FOOD = 4
FRIEND_WATER = 4


def neighbors(cell):
    x, y = cell
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = x + dx, y + dy
        if 0 <= nx < W and 0 <= ny < H and (nx, ny) not in WALLS:
            yield (nx, ny)


def free_cells():
    return [(x, y) for x in range(W) for y in range(H)
            if (x, y) not in RESERVED and (x, y) not in WALLS]


def move_one(cell, rng):
    options = [c for c in neighbors(cell) if c not in RESERVED] + [cell]
    return rng.choice(options)


def make_hordes(seed, count, turn=0):
    """Slow zombie packs. Each moves one step per turn."""
    rng = random.Random(seed)
    hordes = rng.sample(free_cells(), count)
    for _ in range(turn):
        hordes = list(dict.fromkeys(move_one(h, rng) for h in hordes))
    return hordes


def make_runners(seed, count, turn=0):
    """Fast runners. They move two steps per turn."""
    rng = random.Random(seed + 1000)
    runners = rng.sample(free_cells(), count)
    for _ in range(turn * 2):
        runners = [move_one(r, rng) for r in runners]
    return runners


def runner_zone(runners):
    """Tiles a runner can reach or attack in one step."""
    zone = set()
    for r in runners:
        zone.add(r)
        zone.update(neighbors(r))
    return zone


def find_route(hordes, runners=(), must_rescue=False):
    """Dijkstra over (cell, food, water, rescued). Returns the lowest-risk route, or None."""
    horde_set = set(hordes)
    zone = runner_zone(runners)
    start = (START, MAX_FOOD, MAX_WATER, False)
    best = {start: 0}
    came_from = {start: None}
    heap = [(0, START, MAX_FOOD, MAX_WATER, False)]

    while heap:
        cost, cell, food, water, rescued = heapq.heappop(heap)
        state = (cell, food, water, rescued)
        if cost > best[state]:
            continue
        if cell == BEACON and (rescued or not must_rescue):
            return build_result(came_from, state, cost, horde_set, zone)
        for nb in neighbors(cell):
            step = 1
            f, w = food - 1, water - 1
            if nb in horde_set:
                f -= HORDE_FOOD_COST
                step += HORDE_TIME_COST
            if nb in zone:
                step += RUNNER_TIME_COST
            r = rescued
            if nb == FRIEND and not rescued:
                r = True
                f += FRIEND_FOOD
                w += FRIEND_WATER
            if nb in DEPOTS:
                f, w = MAX_FOOD, MAX_WATER
            f, w = min(f, MAX_FOOD), min(w, MAX_WATER)
            if f < 0 or w < 0:
                continue
            ns = (nb, f, w, r)
            nc = cost + step
            if nc < best.get(ns, float("inf")):
                best[ns] = nc
                came_from[ns] = state
                heapq.heappush(heap, (nc, nb, f, w, r))
    return None


def build_result(came_from, state, cost, horde_set, zone):
    path, states = [], []
    s = state
    while s is not None:
        path.append(s[0])
        states.append((s[1], s[2]))
        s = came_from[s]
    path.reverse()
    states.reverse()
    _, food, water, rescued = state
    return {
        "path": path,
        "states": states,
        "cost": cost,
        "food_left": food,
        "water_left": water,
        "rescued": rescued,
        "hordes_on_route": sum(1 for c in path if c in horde_set),
        "runner_steps": sum(1 for c in path if c in zone),
        "depot_stops": sum(1 for c in path if c in DEPOTS),
    }


def risk_map(cells, radius=2):
    """How many threats could reach each tile within `radius` steps."""
    risk = {}
    for hx, hy in cells:
        for x in range(W):
            for y in range(H):
                if abs(x - hx) + abs(y - hy) <= radius:
                    risk[(x, y)] = risk.get((x, y), 0) + 1
    return risk