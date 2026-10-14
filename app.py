import json
import time

import matplotlib.pyplot as plt
import streamlit as st
from matplotlib.patches import Rectangle

from planner import (W, H, START, BEACON, DEPOTS, FRIEND, WALLS,
                     make_hordes, make_runners, find_route, risk_map)

st.set_page_config(page_title="Apocalypse: The Last Beacon", layout="wide")

PRESETS = {"Easy": (7, 8, 4), "Crowded": (7, 22, 6), "Stress test": (7, 40, 8)}

st.markdown("""
<style>
.stApp { background: linear-gradient(160deg, #0b1020 0%, #111827 55%, #2a0f18 100%); }
h1 {
  background: linear-gradient(90deg, #f97316, #facc15);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  font-weight: 800 !important;
}
.hero { color: #cbd5e1; font-size: 15px; margin-top: -10px; margin-bottom: 18px; }
.card {
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.09);
  border-radius: 14px; padding: 14px 16px; margin-bottom: 10px;
  box-shadow: 0 6px 18px rgba(0,0,0,0.25);
}
.card .label { color: #94a3b8; font-size: 11px; text-transform: uppercase; letter-spacing: 1.2px; }
.card .value { color: #f8fafc; font-size: 28px; font-weight: 700; }
.badge {
  display: inline-block; padding: 4px 10px; border-radius: 999px;
  font-size: 12px; font-weight: 600; margin-right: 6px;
}
.ok { background: rgba(34,197,94,0.15); color: #4ade80; }
.warn { background: rgba(249,115,22,0.15); color: #fb923c; }
.bad { background: rgba(239,68,68,0.15); color: #f87171; }
.friend { background: rgba(168,85,247,0.15); color: #c084fc; }
</style>
""", unsafe_allow_html=True)

for key, value in {"seed": 7, "count": 18, "runners": 4, "turn": 0, "auto": False}.items():
    st.session_state.setdefault(key, value)


def apply_preset(seed, count, runners):
    st.session_state.seed = seed
    st.session_state.count = count
    st.session_state.runners = runners
    st.session_state.turn = 0


def card(label, value, color="#f8fafc"):
    st.markdown(
        f'<div class="card"><div class="label">{label}</div>'
        f'<div class="value" style="color:{color}">{value}</div></div>',
        unsafe_allow_html=True,
    )


@st.cache_data
def plan(hordes, runners, must_rescue):
    return find_route(list(hordes), list(runners), must_rescue)


def route_stats(res, hs):
    if not res:
        return None
    return {
        "steps": len(res["path"]) - 1,
        "food": res["food_left"],
        "water": res["water_left"],
        "hordes": sum(1 for c in res["path"] if c in hs),
        "runners": res["runner_steps"],
        "depots": res["depot_stops"],
        "rescued": res["rescued"],
    }


def draw_grid(hordes, runners, path, rescue_path, risk):
    hs = set(hordes)
    fig, ax = plt.subplots(figsize=(7, 7))
    fig.patch.set_facecolor("#0b1020")
    ax.set_facecolor("#0b1020")
    for x in range(W):
        for y in range(H):
            if (x, y) in WALLS:
                ax.add_patch(Rectangle((x, y), 1, 1, facecolor="#374151", edgecolor="#111827", linewidth=1.5))
                continue
            ax.add_patch(Rectangle((x, y), 1, 1, facecolor="#1f2937", edgecolor="#0b1020", linewidth=1.2))
            if (x, y) in hs:
                ax.add_patch(Rectangle((x, y), 1, 1, facecolor="#dc2626", edgecolor="#0b1020", linewidth=1.2))
            elif risk.get((x, y), 0):
                alpha = min(0.10 * risk[(x, y)], 0.40)
                ax.add_patch(Rectangle((x, y), 1, 1, facecolor="#f59e0b", alpha=alpha, edgecolor="none"))
    for dx, dy in DEPOTS:
        ax.add_patch(Rectangle((dx, dy), 1, 1, facecolor="#16a34a", edgecolor="#0b1020", linewidth=1.2))
        ax.text(dx + 0.5, dy + 0.5, "D", ha="center", va="center", color="white", fontsize=12, weight="bold")
    ax.add_patch(Rectangle(FRIEND, 1, 1, facecolor="#7c3aed", edgecolor="#0b1020", linewidth=1.2))
    ax.text(FRIEND[0] + 0.5, FRIEND[1] + 0.5, "F", ha="center", va="center", color="white", fontsize=12, weight="bold")
    if runners:
        ax.scatter([r[0] + 0.5 for r in runners], [r[1] + 0.5 for r in runners],
                   s=160, color="#fb923c", edgecolor="white", linewidth=1.2, zorder=5)
    ax.text(START[0] + 0.5, START[1] + 0.5, "S", ha="center", va="center", color="white", fontsize=13, weight="bold")
    ax.text(BEACON[0] + 0.5, BEACON[1] + 0.5, "B", ha="center", va="center", color="#facc15", fontsize=13, weight="bold")
    if rescue_path:
        xs = [x + 0.5 for x, _ in rescue_path]
        ys = [y + 0.5 for _, y in rescue_path]
        ax.plot(xs, ys, color="#c084fc", linewidth=2, linestyle="--", marker="o", markersize=3, zorder=4)
    if path:
        xs = [x + 0.5 for x, _ in path]
        ys = [y + 0.5 for _, y in path]
        ax.plot(xs, ys, color="#38bdf8", linewidth=8, alpha=0.2, solid_capstyle="round", zorder=3)
        ax.plot(xs, ys, color="#38bdf8", linewidth=3, marker="o", markersize=4, zorder=3)
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.set_aspect("equal")
    ax.axis("off")
    return fig


def draw_timeline(states):
    food = [s[0] for s in states]
    water = [s[1] for s in states]
    fig, ax = plt.subplots(figsize=(7, 3))
    fig.patch.set_facecolor("#0b1020")
    ax.set_facecolor("#0b1020")
    ax.plot(food, color="#f97316", linewidth=2.5, label="Food")
    ax.plot(water, color="#38bdf8", linewidth=2.5, label="Water")
    ax.axhline(0, color="#ef4444", linestyle="--", linewidth=1)
    ax.set_xlabel("Step", color="#cbd5e1")
    ax.set_ylabel("Supplies", color="#cbd5e1")
    ax.tick_params(colors="#94a3b8")
    for spine in ax.spines.values():
        spine.set_color("#334155")
    ax.legend(facecolor="#111827", edgecolor="#334155", labelcolor="#e2e8f0")
    fig.tight_layout()
    return fig


st.title("Apocalypse: The Last Beacon")
st.markdown(
    '<div class="hero">Boy 1 and Boy 2 must reach the beacon through a zombie-filled city, '
    'and they can rescue a friend trapped on the way. Phones are offline. Packs of zombies '
    'and fast runners move every turn, and the route re-plans.</div>',
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Scenario")
    p1, p2, p3 = st.columns(3)
    for col, (name, (s, c, r)) in zip((p1, p2, p3), PRESETS.items()):
        col.button(name, on_click=apply_preset, args=(s, c, r), use_container_width=True)

    st.number_input("World seed", step=1, key="seed")
    st.slider("Zombie packs", 0, 40, key="count")
    st.slider("Fast runners", 0, 12, key="runners")

    st.header("Simulation")
    b1, b2 = st.columns(2)
    if b1.button("Advance turn", use_container_width=True):
        st.session_state.turn += 1
    if b2.button("Reset turns", use_container_width=True):
        st.session_state.turn = 0
    st.toggle("Auto-advance (1 turn / 2 s)", key="auto")
    st.markdown(f"**Turn {st.session_state.turn}**")

    st.header("Legend")
    st.markdown(
        "- 🟥 Zombie pack (2 extra food, big time penalty)\n"
        "- 🟧 Runner (fast zombie, penalty on nearby tiles)\n"
        "- ⬛ Building (impassable)\n"
        "- 🟪 F: friend, rescue for food and water\n"
        "- 🟩 D: supply depot\n"
        "- 🟦 Solid blue: safest route\n"
        "- 🟣 Dashed purple: rescue route (picks up the friend)"
    )

seed = int(st.session_state.seed)
count = int(st.session_state.count)
nrun = int(st.session_state.runners)
turn = st.session_state.turn

hordes = make_hordes(seed, count, turn)
runners = make_runners(seed, nrun, turn)
hs = set(hordes)
safest = plan(tuple(hordes), tuple(runners), False)
fastest = plan((), (), False)
rescue = plan(tuple(hordes), tuple(runners), True)
s_stats = route_stats(safest, hs)
f_stats = route_stats(fastest, hs)
r_stats = route_stats(rescue, hs)
risk = risk_map(hordes + runners)

if safest:
    status = '<span class="badge ok">Route found</span>'
elif fastest:
    status = '<span class="badge warn">Only risky routes</span>'
else:
    status = '<span class="badge bad">No route to beacon</span>'
friend_badge = (
    '<span class="badge friend">Friend reachable</span>' if rescue
    else '<span class="badge bad">Friend unreachable</span>'
)
st.markdown(
    f"{status}{friend_badge}"
    f"<span class='badge ok'>{count} packs</span>"
    f"<span class='badge warn'>{nrun} runners</span>"
    f"<span class='badge ok'>Seed {seed}</span>",
    unsafe_allow_html=True,
)

m1, m2, m3, m4 = st.columns(4)
with m1:
    card("Turn", turn)
with m2:
    card("Zombies", count + nrun, "#f87171")
with m3:
    card("Food left", s_stats["food"] if s_stats else "-", "#fb923c")
with m4:
    card("Water left", s_stats["water"] if s_stats else "-", "#38bdf8")

left, right = st.columns([3, 2])
with left:
    st.subheader("Live city map")
    st.pyplot(draw_grid(hordes, runners,
                        safest["path"] if safest else None,
                        rescue["path"] if rescue else None,
                        risk))

with right:
    st.subheader("Route comparison")
    if f_stats and s_stats:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**Fastest**")
            card("Steps", f_stats["steps"])
            card("Packs crossed", f_stats["hordes"], "#f87171")
        with c2:
            st.markdown("**Safest**")
            card("Steps", s_stats["steps"])
            card("Packs crossed", s_stats["hordes"], "#4ade80")
        with c3:
            st.markdown("**Rescue friend**")
            if r_stats:
                card("Steps", r_stats["steps"], "#c084fc")
                card("Food left", r_stats["food"], "#c084fc")
            else:
                card("Steps", "-", "#c084fc")
        saved = f_stats["hordes"] - s_stats["hordes"]
        if saved > 0:
            st.success(f"Planner avoids {saved} pack tile(s) compared with the fastest route.")
        else:
            st.info("This world has no shortcut to avoid. Both routes cross the same packs.")
        if not s_stats["rescued"] and r_stats:
            st.warning("The safest route skips the friend. The dashed purple route rescues them for extra supplies.")
        st.caption(f"Safest route uses {s_stats['depots']} depot stop(s) and passes {s_stats['runners']} runner-threatened tile(s).")
    elif safest is None:
        st.error("No route reaches the beacon with current supplies. Try fewer zombies, another seed, or the Easy preset.")

if safest:
    st.subheader("Supply timeline (safest route)")
    st.pyplot(draw_timeline(safest["states"]))

    report = {
        "seed": seed,
        "turn": turn,
        "zombie_packs": hordes,
        "runners": runners,
        "route": safest["path"],
        "rescued_friend": safest["rescued"],
        "food_left": safest["food_left"],
        "water_left": safest["water_left"],
        "depot_stops": safest["depot_stops"],
    }
    st.download_button(
        "Download route report (JSON)",
        json.dumps(report, indent=2),
        file_name="route_report.json",
        mime="application/json",
    )

with st.expander("How it works and assumptions"):
    st.write(
        "The city is a 15x15 grid with buildings that block movement. Each step costs 1 food and 1 water. "
        "Zombie packs cost 2 extra food and a large time penalty. Runners move two tiles per turn, and tiles next to "
        "a runner carry a smaller penalty. The friend gives 4 food and 4 water when rescued. Depots refill both supplies. "
        "The planner runs Dijkstra over (position, food, water, rescued), so it only returns routes that never run out. "
        "The app makes no network calls and runs fully offline."
    )

if st.session_state.auto:
    time.sleep(2)
    st.session_state.turn += 1
    st.rerun()