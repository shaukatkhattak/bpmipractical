"""
Process mining analysis: Helpdesk-Baltics event log
"""
import pandas as pd
import numpy as np
from collections import defaultdict

LOG_PATH = r"c:\Users\showkat\Downloads\Helpdesk-Baltics.csv\Helpdesk-Baltics.csv"
SLA_DAYS = 90  # 3 months

df = pd.read_csv(LOG_PATH)
df["Time"] = pd.to_datetime(df["Time"])
df = df.sort_values(["Ticket", "Time", "Status"]).reset_index(drop=True)

# Closed cases: at least one Closed event
closed_tickets = set(df.loc[df["Status"] == "Closed", "Ticket"].unique())
print(f"Total tickets: {df['Ticket'].nunique()}")
print(f"Closed tickets: {len(closed_tickets)}")

# --- Q1: Closed cases that skipped Approved ---
def case_skipped_approved(ticket_events):
    statuses = set(ticket_events["Status"].tolist())
    return "Approved" not in statuses

closed_df = df[df["Ticket"].isin(closed_tickets)]
q1_count = sum(
    1
    for tid, g in closed_df.groupby("Ticket")
    if case_skipped_approved(g)
)
print("\n=== Q1: Closed cases skipping Approved ===")
print(q1_count)

# --- Build per-case event sequences and transition waiting times ---
def build_case_data(ticket, g):
    g = g.sort_values("Time")
    events = g["Status"].tolist()
    times = g["Time"].tolist()
    attrs = g.iloc[0][["Category", "Country"]].to_dict()

    # Case duration: first to last event (or first to Closed?)
    # Standard: first event to last Closed (or last event if multiple Closed)
    closed_times = g.loc[g["Status"] == "Closed", "Time"]
    if len(closed_times) > 0:
        end_time = closed_times.max()
    else:
        end_time = times[-1]
    duration = (end_time - times[0]).total_seconds()

    transitions = []
    for i in range(len(events) - 1):
        wait = (times[i + 1] - times[i]).total_seconds()
        transitions.append((events[i], events[i + 1], wait))

    dispatched_count = sum(1 for e in events if e == "Dispatched")

    return {
        "ticket": ticket,
        "events": events,
        "duration_sec": duration,
        "duration_days": duration / 86400,
        "transitions": transitions,
        "dispatched_count": dispatched_count,
        "has_approved": "Approved" in events,
        **attrs,
    }

cases = []
for tid in df["Ticket"].unique():
    g = df[df["Ticket"] == tid]
    cases.append(build_case_data(tid, g))

cases_df = pd.DataFrame(
    [
        {
            "ticket": c["ticket"],
            "duration_days": c["duration_days"],
            "dispatched_count": c["dispatched_count"],
            "Category": c["Category"],
            "Country": c["Country"],
            "closed": c["ticket"] in closed_tickets,
            "has_approved": c["has_approved"],
        }
        for c in cases
    ]
)

closed_cases = [c for c in cases if c["ticket"] in closed_tickets]

# --- Q2: Top 3 waiting bottlenecks (transitions with highest avg waiting time) ---
# Aggregate: for each transition (A -> B), collect all waiting times across cases
transition_waits = defaultdict(list)
transition_case_count = defaultdict(set)

for c in closed_cases:
    for a, b, wait in c["transitions"]:
        key = (a, b)
        transition_waits[key].append(wait)
        transition_case_count[key].add(c["ticket"])

transition_stats = []
for key, waits in transition_waits.items():
    transition_stats.append(
        {
            "from": key[0],
            "to": key[1],
            "transition": f"{key[0]} -> {key[1]}",
            "avg_wait_sec": np.mean(waits),
            "avg_wait_days": np.mean(waits) / 86400,
            "median_wait_days": np.median(waits) / 86400,
            "case_count": len(transition_case_count[key]),
            "occurrence_count": len(waits),
        }
    )

trans_df = pd.DataFrame(transition_stats).sort_values("avg_wait_sec", ascending=False)

print("\n=== Q2: Top 10 transitions by average waiting time (closed cases) ===")
print(trans_df.head(10).to_string(index=False))

top3 = trans_df.head(3)
print("\nTop 3 bottlenecks:")
for _, row in top3.iterrows():
    print(
        f"  {row['transition']}: avg {row['avg_wait_days']:.2f} days, "
        f"in {row['case_count']} cases ({row['occurrence_count']} occurrences)"
    )

# --- Q3: Which bottleneck to target ---
print("\n=== Q3: Bottleneck recommendation ===")
top1 = trans_df.iloc[0]
# Also consider impact = avg_wait * case_count (total waiting time contributed)
trans_df["total_wait_days"] = trans_df["avg_wait_days"] * trans_df["occurrence_count"]
trans_df_impact = trans_df.sort_values("total_wait_days", ascending=False)
print("Top by total accumulated waiting (avg * occurrences):")
print(trans_df_impact.head(5)[["transition", "avg_wait_days", "occurrence_count", "total_wait_days"]].to_string(index=False))

# --- Q4: Category with longest average cycle time (closed cases) ---
closed_cases_df = cases_df[cases_df["closed"]]
cat_stats = (
    closed_cases_df.groupby("Category")["duration_days"]
    .agg(["mean", "median", "count"])
    .sort_values("mean", ascending=False)
)
print("\n=== Q4: Average case duration by Category (closed cases) ===")
print(cat_stats.to_string())

# --- Q5: Country with highest number of issues ---
country_counts = df.groupby("Country")["Ticket"].nunique().sort_values(ascending=False)
print("\n=== Q5: Issues per country (unique tickets) ===")
print(country_counts.to_string())

# --- Q6: Dispatched more than once in closed cases ---
def dispatched_more_than_once(c):
    return c["dispatched_count"] > 1

multi_disp = [c for c in closed_cases if dispatched_more_than_once(c)]
single_or_none = [
    c for c in closed_cases if c["dispatched_count"] <= 1
]

print("\n=== Q6: Multiple Dispatched in closed cases ===")
print(f"Closed cases with Dispatched > 1: {len(multi_disp)}")
avg_multi = np.mean([c["duration_days"] for c in multi_disp]) if multi_disp else 0
avg_single = np.mean([c["duration_days"] for c in single_or_none]) if single_or_none else 0
print(f"Avg duration (multi dispatched): {avg_multi:.2f} days")
print(f"Avg duration (<=1 dispatched): {avg_single:.2f} days")
print(f"Difference: {avg_multi - avg_single:.2f} days")

# --- Q7: SLA violations by country ---
closed_cases_df["sla_violation"] = closed_cases_df["duration_days"] > SLA_DAYS
sla_by_country = (
    closed_cases_df.groupby("Country")
    .agg(
        total=("sla_violation", "count"),
        violations=("sla_violation", "sum"),
    )
    .assign(pct=lambda x: 100 * x["violations"] / x["total"])
    .sort_values("pct", ascending=False)
)
print("\n=== Q7: SLA violation % by country (3 months = 90 days) ===")
print(sla_by_country.to_string())

# Country comparison for Q7
for country in ["Estonia", "Latvia", "Lithuania"]:
    if country not in sla_by_country.index:
        # try partial match
        pass

# Activity frequency by country (closed cases only)
print("\n=== Q7 supplement: Activity frequency by country (closed cases) ===")
closed_events = df[df["Ticket"].isin(closed_tickets)]
act_by_country = (
    closed_events.groupby(["Country", "Status"])
    .size()
    .unstack(fill_value=0)
)
# Normalize to relative frequency per country
act_rel = act_by_country.div(act_by_country.sum(axis=1), axis=0)
print("\nRelative activity frequencies (top differences):")
for c1, c2 in [("Estonia", "Latvia"), ("Estonia", "Lithuania"), ("Latvia", "Lithuania")]:
    if c1 in act_rel.index and c2 in act_rel.index:
        diff = (act_rel.loc[c1] - act_rel.loc[c2]).abs().sort_values(ascending=False)
        print(f"\n{c1} vs {c2} - largest relative freq differences:")
        print(diff.head(8).to_string())

# Transition stats by country for closed cases
print("\n=== Q7 supplement: Top transitions by country (avg wait) ===")
for country in closed_events["Country"].unique():
    country_closed = [c for c in closed_cases if c["Country"] == country]
    tw = defaultdict(list)
    for c in country_closed:
        for a, b, wait in c["transitions"]:
            tw[(a, b)].append(wait)
    stats = [
        (f"{a}->{b}", np.mean(w), len(w))
        for (a, b), w in tw.items()
    ]
    stats.sort(key=lambda x: x[1], reverse=True)
    print(f"\n{country} - top 5 transitions by avg wait:")
    for s in stats[:5]:
        print(f"  {s[0]}: {s[1]/86400:.2f} days avg, {s[2]} occurrences")

# Skip Approved rate by country
print("\n=== Skip Approved rate by country (closed) ===")
for country in closed_cases_df["Country"].unique():
    sub = closed_cases_df[closed_cases_df["Country"] == country]
    skipped = sum(1 for c in closed_cases if c["Country"] == country and not c["has_approved"])
    print(f"{country}: {skipped}/{len(sub)} = {100*skipped/len(sub):.1f}%")
