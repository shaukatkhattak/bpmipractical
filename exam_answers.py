"""Compute exam answers from Helpdesk-Baltics log (same logic as helpdesk_analysis.py)."""
import pandas as pd
import numpy as np
from collections import defaultdict

LOG_PATH = r"c:\Users\showkat\Downloads\Helpdesk-Baltics.csv\Helpdesk-Baltics.csv"
SLA_DAYS = 90


def load_data():
    df = pd.read_csv(LOG_PATH)
    df["Time"] = pd.to_datetime(df["Time"])
    df = df.sort_values(["Ticket", "Time", "Status"]).reset_index(drop=True)
    closed_tickets = set(df.loc[df["Status"] == "Closed", "Ticket"].unique())
    return df, closed_tickets


def build_cases(df, closed_tickets):
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
            "closed": tid in closed_tickets,
            "approved": "Approved" in ev,
            "country": g["Country"].iloc[0],
            "category": g["Category"].iloc[0],
            "duration_days": dur,
            "dispatched_count": ev.count("Dispatched"),
            "transitions": trans,
        })
    return cases


def compute_answers():
    df, closed_tickets = load_data()
    cases = build_cases(df, closed_tickets)
    closed = [c for c in cases if c["closed"]]

    # Q1
    q1 = sum(1 for c in closed if not c["approved"])

    # Q2
    tw, tc = defaultdict(list), defaultdict(set)
    for c in closed:
        for a, b, w in c["transitions"]:
            tw[(a, b)].append(w)
            tc[(a, b)].add(c["ticket"])
    rows = []
    for k, ws in tw.items():
        rows.append({
            "transition": f"{k[0]} -> {k[1]}",
            "avg_days": np.mean(ws) / 86400,
            "cases": len(tc[k]),
        })
    tdf = pd.DataFrame(rows).sort_values("avg_days", ascending=False)
    top3 = tdf.head(3).to_dict("records")

    # Q3
    impact_rows = []
    for k, ws in tw.items():
        impact_rows.append({
            "transition": f"{k[0]} -> {k[1]}",
            "total_days": sum(ws) / 86400,
            "avg_days": np.mean(ws) / 86400,
            "n": len(ws),
        })
    idf = pd.DataFrame(impact_rows).sort_values("total_days", ascending=False)
    top_impact = idf.head(3).to_dict("records")

    # Q4
    cdf = pd.DataFrame(closed)
    cat = cdf.groupby("category")["duration_days"].agg(["mean", "median", "count"]).sort_values("mean", ascending=False)

    # Q5
    country_counts = df.groupby("Country")["Ticket"].nunique().sort_values(ascending=False)

    # Q6
    multi = [c for c in closed if c["dispatched_count"] > 1]
    single = [c for c in closed if c["dispatched_count"] <= 1]
    q6_multi_avg = np.mean([c["duration_days"] for c in multi])
    q6_single_avg = np.mean([c["duration_days"] for c in single])

    # Q7
    cdf["sla_violation"] = cdf["duration_days"] > SLA_DAYS
    sla = cdf.groupby("country").agg(
        total=("sla_violation", "count"),
        viol=("sla_violation", "sum"),
    ).assign(pct=lambda x: 100 * x["viol"] / x["total"]).sort_values("pct", ascending=False)

    def country_stats(name):
        sub = [c for c in closed if c["country"] == name]
        viol = sum(1 for c in sub if c["duration_days"] > SLA_DAYS)
        cats = pd.Series([c["category"] for c in sub]).value_counts(normalize=True) * 100
        return {
            "closed": len(sub),
            "viol": viol,
            "pct": 100 * viol / len(sub),
            "avg_days": np.mean([c["duration_days"] for c in sub]),
            "sw_pct": cats.get("Software installation", 0),
        }

    ee, lv = country_stats("Estonia"), country_stats("Latvia")
    ev = df[df["Ticket"].isin(closed_tickets)]
    act_ee = ev[ev["Country"] == "Estonia"]["Status"].value_counts(normalize=True) * 100
    act_lv = ev[ev["Country"] == "Latvia"]["Status"].value_counts(normalize=True) * 100

    def trans_avg(country, a, b):
        sub = [c for c in closed if c["country"] == country]
        ws = []
        for c in sub:
            for x, y, w in c["transitions"]:
                if x == a and y == b:
                    ws.append(w)
        return np.mean(ws) / 86400 if ws else 0

    disp_cu_ee = trans_avg("Estonia", "Dispatched", "ChangeUpdate")
    disp_cu_lv = trans_avg("Latvia", "Dispatched", "ChangeUpdate")

    return {
        "q1": q1,
        "top3": top3,
        "top_impact": top_impact,
        "cat": cat,
        "country_counts": country_counts,
        "q6_count": len(multi),
        "q6_multi_avg": q6_multi_avg,
        "q6_single_avg": q6_single_avg,
        "sla": sla,
        "ee": ee,
        "lv": lv,
        "act_ee_cu": act_ee.get("ChangeUpdate", 0),
        "act_lv_cu": act_lv.get("ChangeUpdate", 0),
        "disp_cu_ee": disp_cu_ee,
        "disp_cu_lv": disp_cu_lv,
    }


def format_answers(a):
    top3_lines = "\n".join(
        f"{i}) {r['transition']}: {r['avg_days']:.1f} days "
        f"({int(r['cases'])} {'case' if int(r['cases']) == 1 else 'cases'})"
        for i, r in enumerate(a["top3"], 1)
    )
    cat = a["cat"]
    longest = cat.index[0]
    sla = a["sla"]
    sla_lines = "\n".join(
        f"- {country}: {row['pct']:.1f}% ({int(row['viol'])}/{int(row['total'])})"
        for country, row in sla.iterrows()
    )
    highest = sla.index[0]
    lowest = sla.index[-1]

    return [
        {
            "num": 1,
            "answer": f"{a['q1']} closed cases skipped the Approved activity.",
            "images": ["Q1_skipped_approved.png"],
        },
        {
            "num": 2,
            "answer": (
                "Three main waiting bottlenecks (closed cases, highest mean waiting time "
                "on directly-follows transitions):\n"
                f"{top3_lines}"
            ),
            "images": ["Q2_top3_bottlenecks.png"],
        },
        {
            "num": 3,
            "answer": (
                f"Bottleneck to target: {a['top_impact'][0]['transition']}.\n\n"
                "Why: rank by total accumulated waiting time (sum of all waits on the arc). "
                f"{a['top_impact'][0]['transition']} has the largest impact "
                f"({a['top_impact'][0]['total_days']:.0f} days total). "
                f"Also prioritize {a['top_impact'][1]['transition']} "
                f"({a['top_impact'][1]['avg_days']:.1f} days mean, {int(a['top_impact'][1]['n'])} occurrences) "
                f"and {a['top_impact'][2]['transition']} "
                f"({a['top_impact'][2]['avg_days']:.1f} days mean, {int(a['top_impact'][2]['n'])} occurrences) "
                "because they affect many cases before closure.\n\n"
                "Suggestion: reduce ChangeUpdate rework loops and shorten the finalization "
                "phase (updates to Closed)."
            ),
            "images": ["Q3_bottleneck_impact.png"],
        },
        {
            "num": 4,
            "answer": (
                f"Longest average time to close: {longest} "
                f"({cat.loc[longest, 'mean']:.1f} days mean, "
                f"{cat.loc[longest, 'median']:.1f} days median, "
                f"{int(cat.loc[longest, 'count'])} closed cases).\n\n"
                "Mean cycle time by category:\n"
                + "\n".join(
                    f"- {idx}: {cat.loc[idx, 'mean']:.1f} days"
                    for idx in cat.index
                )
                + f"\n\nFocus improvement on {longest} (slowest category)."
            ),
            "images": ["Q4_category_cycle_time.png"],
        },
        {
            "num": 5,
            "answer": (
                f"Country with the highest number of issues: {a['country_counts'].index[0]} "
                f"({int(a['country_counts'].iloc[0])} cases).\n\n"
                + "\n".join(
                    f"- {c}: {int(n)}"
                    for c, n in a["country_counts"].items()
                )
            ),
            "images": ["Q5_issues_per_country.png"],
        },
        {
            "num": 6,
            "answer": (
                f"Closed cases with Dispatched more than once: {a['q6_count']}.\n"
                f"Average case duration (Dispatched > 1): {a['q6_multi_avg']:.1f} days.\n"
                f"Average case duration (Dispatched <= 1): {a['q6_single_avg']:.1f} days.\n"
                f"Difference: {a['q6_multi_avg'] - a['q6_single_avg']:.1f} days.\n\n"
                "Repeated dispatch is associated with much longer case duration (rework)."
            ),
            "images": ["Q6_dispatched_duration.png"],
        },
        {
            "num": 7,
            "answer": (
                "SLA: case must close within 90 days (3 months). Violation if cycle time > 90 days "
                "(closed cases only).\n\n"
                f"SLA violation rate by country:\n{sla_lines}\n"
                f"Highest: {highest}. Lowest: {lowest}.\n\n"
                "Estonia vs Latvia:\n"
                f"- Mean cycle time: Estonia {a['ee']['avg_days']:.1f} d vs Latvia {a['lv']['avg_days']:.1f} d.\n"
                f"- Category mix: Estonia has more Software installation "
                f"({a['ee']['sw_pct']:.1f}% vs {a['lv']['sw_pct']:.1f}%).\n"
                f"- Activity mix: Estonia has more ChangeUpdate events "
                f"({a['act_ee_cu']:.1f}% vs {a['act_lv_cu']:.1f}%).\n"
                f"- After Dispatched: Dispatched -> ChangeUpdate mean wait "
                f"{a['disp_cu_ee']:.1f} d (Estonia) vs {a['disp_cu_lv']:.1f} d (Latvia).\n"
                "Skipping Approved is rare in both countries and is not the main SLA driver."
            ),
            "images": ["Q7_sla_by_country.png", "Q7_EE_vs_LV_activities.png"],
        },
    ]


if __name__ == "__main__":
    for q in format_answers(compute_answers()):
        print(f"\n=== Question {q['num']} ===\n{q['answer']}")
