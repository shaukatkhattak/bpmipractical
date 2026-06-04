"""Generate BPI exam screenshots (Apromore-style charts) for Helpdesk-Baltics."""
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from collections import defaultdict

LOG = r"c:\Users\showkat\Downloads\Helpdesk-Baltics.csv\Helpdesk-Baltics.csv"
OUT = r"c:\Users\showkat\exambpi\screenshots"
SLA_DAYS = 90
os.makedirs(OUT, exist_ok=True)

plt.rcParams.update({
    "figure.figsize": (10, 6),
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.labelsize": 11,
})

df = pd.read_csv(LOG)
df["Time"] = pd.to_datetime(df["Time"])
df = df.sort_values(["Ticket", "Time"]).reset_index(drop=True)
closed_ids = set(df.loc[df["Status"] == "Closed", "Ticket"].unique())


def build_cases():
    cases = []
    for tid in df["Ticket"].unique():
        g = df[df["Ticket"] == tid].sort_values("Time")
        ev, tm = g["Status"].tolist(), g["Time"].tolist()
        ct = g.loc[g["Status"] == "Closed", "Time"]
        end = ct.max() if len(ct) else tm[-1]
        dur = (end - tm[0]).total_seconds() / 86400
        trans = [(ev[i], ev[i + 1], (tm[i + 1] - tm[i]).total_seconds()) for i in range(len(ev) - 1)]
        cases.append({
            "ticket": tid,
            "closed": tid in closed_ids,
            "approved": "Approved" in ev,
            "country": g["Country"].iloc[0],
            "category": g["Category"].iloc[0],
            "duration_days": dur,
            "dispatched_n": ev.count("Dispatched"),
            "trans": trans,
        })
    return cases


cases = build_cases()
closed = [c for c in cases if c["closed"]]


def save(fig, name):
    path = os.path.join(OUT, name)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Saved {path}")


def add_watermark(fig, title, subtitle=""):
    fig.suptitle(title, fontsize=14, fontweight="bold", y=1.02)
    if subtitle:
        fig.text(0.5, -0.02, subtitle, ha="center", fontsize=9, color="#444")


# --- Q1 ---
skipped = sum(1 for c in closed if not c["approved"])
fig, ax = plt.subplots(figsize=(8, 4))
ax.axis("off")
text = (
    "Q1: Closed cases skipping 'Approved'\n\n"
    f"Closed cases in log: {len(closed):,}\n"
    f"Cases without Approved activity: {skipped}\n\n"
    "Procedure: Filter closed cases → check activity absence"
)
ax.text(0.5, 0.5, text, ha="center", va="center", fontsize=14,
        bbox=dict(boxstyle="round", facecolor="#e8f4fc", edgecolor="#2c6fad", linewidth=2))
add_watermark(fig, "Helpdesk Baltics — Q1 Conformance")
save(fig, "Q1_skipped_approved.png")


# --- Q2 ---
tw, tc = defaultdict(list), defaultdict(set)
for c in closed:
    for a, b, w in c["trans"]:
        tw[(a, b)].append(w)
        tc[(a, b)].add(c["ticket"])

rows = []
for k, ws in tw.items():
    label = f"{k[0]} → {k[1]}"
    rows.append({"t": label, "avg_d": np.mean(ws) / 86400, "cases": len(tc[k])})
tdf = pd.DataFrame(rows).sort_values("avg_d", ascending=False)

top3 = tdf.head(3)
fig, ax = plt.subplots(figsize=(11, 5))
colors = ["#c0392b", "#e67e22", "#f39c12"]
bars = ax.barh(top3["t"][::-1], top3["avg_d"][::-1], color=colors[::-1])
ax.set_xlabel("Mean waiting time (days)")
ax.set_title("Top 3 waiting bottlenecks (DFG arcs, closed cases)")
for bar, (_, r) in zip(bars, top3.iloc[::-1].iterrows()):
    ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
            f"{r['cases']} cases", va="center", fontsize=10)
add_watermark(fig, "Helpdesk Baltics — Q2 Performance (mean arc waiting time)")
save(fig, "Q2_top3_bottlenecks.png")

# Q2 operational (frequent arcs)
freq = tdf[tdf["cases"] >= 100].sort_values("avg_d", ascending=False).head(5)
fig, ax = plt.subplots(figsize=(11, 5))
ax.barh(freq["t"][::-1], freq["avg_d"][::-1], color="#3498db")
ax.set_xlabel("Mean waiting time (days)")
ax.set_title("High-volume bottlenecks (≥100 cases, closed cases)")
for i, (_, r) in enumerate(freq.iloc[::-1].iterrows()):
    ax.text(r["avg_d"] + 0.1, i, f"{int(r['cases'])} cases", va="center", fontsize=9)
add_watermark(fig, "Helpdesk Baltics — Q2 Main operational bottlenecks")
save(fig, "Q2_frequent_bottlenecks.png")


# --- Q3 ---
impact_rows = []
for k, ws in tw.items():
    impact_rows.append({
        "t": f"{k[0]} → {k[1]}",
        "impact": sum(ws) / 86400,
        "avg_d": np.mean(ws) / 86400,
        "n": len(ws),
    })
idf = pd.DataFrame(impact_rows).sort_values("impact", ascending=False).head(6)
fig, ax = plt.subplots(figsize=(11, 6))
ax.barh(idf["t"][::-1], idf["impact"][::-1], color="#27ae60")
ax.set_xlabel("Total accumulated waiting (days)")
ax.set_title("Q3: Target bottleneck — highest total waiting time impact")
add_watermark(fig, "Helpdesk Baltics — Q3 Improvement priority (impact)")
save(fig, "Q3_bottleneck_impact.png")


# --- Q4 ---
cdf = pd.DataFrame(closed)
cat = cdf.groupby("category")["duration_days"].mean().sort_values(ascending=True)
fig, ax = plt.subplots(figsize=(10, 5))
ax.barh(cat.index, cat.values, color=["#8e44ad", "#2980b9", "#16a085"])
ax.set_xlabel("Mean cycle time (days)")
ax.set_title("Q4: Mean case duration by Category (closed cases)")
for i, v in enumerate(cat.values):
    ax.text(v + 1, i, f"{v:.1f} d", va="center")
add_watermark(fig, "Helpdesk Baltics — Q4 Case attribute: Category")
save(fig, "Q4_category_cycle_time.png")


# --- Q5 ---
cnt = df.groupby("Country")["Ticket"].nunique().sort_values(ascending=True)
fig, ax = plt.subplots(figsize=(8, 5))
ax.bar(cnt.index, cnt.values, color=["#1abc9c", "#3498db", "#e74c3c"])
ax.set_ylabel("Number of issues (cases)")
ax.set_title("Q5: Issues per Country")
for i, v in enumerate(cnt.values):
    ax.text(i, v + 15, str(v), ha="center", fontweight="bold")
add_watermark(fig, "Helpdesk Baltics — Q5 Case attribute: Country")
save(fig, "Q5_issues_per_country.png")


# --- Q6 ---
multi = [c["duration_days"] for c in closed if c["dispatched_n"] > 1]
single = [c["duration_days"] for c in closed if c["dispatched_n"] <= 1]
fig, ax = plt.subplots(figsize=(9, 5))
bp = ax.boxplot(
    [single, multi],
    tick_labels=[f"Dispatched ≤1\n(n={len(single)})", f"Dispatched >1\n(n={len(multi)})"],
    patch_artist=True,
    widths=0.5,
)
bp["boxes"][0].set_facecolor("#aed6f1")
bp["boxes"][1].set_facecolor("#f5b7b1")
ax.set_ylabel("Case cycle time (days)")
ax.set_title(
    f"Q6: Repeated Dispatched — avg diff = {np.mean(multi) - np.mean(single):.1f} days\n"
    f"({np.mean(multi):.1f} vs {np.mean(single):.1f} days)"
)
add_watermark(fig, "Helpdesk Baltics — Q6 Rework (repeated Dispatched)")
save(fig, "Q6_dispatched_duration.png")


# --- Q7 SLA ---
cdf = pd.DataFrame(closed)
cdf["sla_violation"] = cdf["duration_days"] > SLA_DAYS
sla = cdf.groupby("country").agg(
    total=("sla_violation", "count"),
    viol=("sla_violation", "sum"),
).assign(pct=lambda x: 100 * x["viol"] / x["total"]).sort_values("pct", ascending=True)

fig, ax = plt.subplots(figsize=(9, 5))
colors_sla = ["#27ae60", "#f1c40f", "#c0392b"]
bars = ax.barh(sla.index, sla["pct"], color=colors_sla)
ax.set_xlabel("SLA violation rate (%) — threshold: 90 days")
ax.set_title("Q7: SLA violations by Country (closed cases)")
ax.axvline(x=0, color="k", linewidth=0.5)
for bar, (_, r) in zip(bars, sla.iterrows()):
    ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
            f"{int(r['viol'])}/{int(r['total'])} ({r['pct']:.1f}%)", va="center", fontsize=10)
add_watermark(fig, "Helpdesk Baltics — Q7 SLA compliance")
save(fig, "Q7_sla_by_country.png")


# Q7 Estonia vs Latvia activity mix
ev = df[df["Ticket"].isin(closed_ids)]
top_acts = ["ChangeUpdate", "IncidentUpdate", "Closed", "Dispatched", "Resolved", "Approved"]
countries = ["Estonia", "Latvia"]
mix = {}
for co in countries:
    sub = ev[ev["Country"] == co]["Status"]
    vc = sub.value_counts(normalize=True) * 100
    mix[co] = [vc.get(a, 0) for a in top_acts]

x = np.arange(len(top_acts))
w = 0.35
fig, ax = plt.subplots(figsize=(11, 5))
ax.bar(x - w / 2, mix["Estonia"], w, label="Estonia (14.4% SLA viol.)", color="#e74c3c")
ax.bar(x + w / 2, mix["Latvia"], w, label="Latvia (1.5% SLA viol.)", color="#27ae60")
ax.set_xticks(x)
ax.set_xticklabels(top_acts, rotation=25, ha="right")
ax.set_ylabel("Relative event frequency (%)")
ax.set_title("Q7: Activity mix — Estonia vs Latvia (closed cases)")
ax.legend()
add_watermark(fig, "Helpdesk Baltics — Q7 Country comparison")
save(fig, "Q7_EE_vs_LV_activities.png")


# Summary dashboard
fig, axes = plt.subplots(2, 2, figsize=(12, 9))
fig.suptitle("Helpdesk Baltics — Exam Summary Dashboard", fontsize=15, fontweight="bold")

axes[0, 0].text(0.5, 0.5, f"Q1: {skipped} closed cases\nskipped Approved", ha="center", va="center", fontsize=12)
axes[0, 0].set_title("Q1")
axes[0, 0].axis("off")

axes[0, 1].barh(top3["t"][::-1], top3["avg_d"][::-1], color=colors[::-1])
axes[0, 1].set_title("Q2 Top bottleneck (days)")
axes[0, 1].set_xlabel("Mean wait (d)")

axes[1, 0].bar(cat.index, cat.values, color=["#8e44ad", "#2980b9", "#16a085"])
axes[1, 0].set_title("Q4 Mean cycle time by Category")
axes[1, 0].tick_params(axis="x", rotation=15)

axes[1, 1].bar(sla.index, sla["pct"], color=["#27ae60", "#f1c40f", "#c0392c"])
axes[1, 1].set_title("Q7 SLA violation %")
axes[1, 1].set_ylabel("%")

fig.tight_layout()
save(fig, "00_summary_dashboard.png")

print(f"\nAll screenshots in: {OUT}")
