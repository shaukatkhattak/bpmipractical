"""Detailed report metrics for Helpdesk-Baltics."""
import pandas as pd
import numpy as np
from collections import defaultdict

LOG = r"c:\Users\showkat\Downloads\Helpdesk-Baltics.csv\Helpdesk-Baltics.csv"
SLA_DAYS = 90

df = pd.read_csv(LOG)
df["Time"] = pd.to_datetime(df["Time"])
df = df.sort_values(["Ticket", "Time"]).reset_index(drop=True)
closed = set(df.loc[df["Status"] == "Closed", "Ticket"])

def case_info(tid):
    g = df[df["Ticket"] == tid].sort_values("Time")
    ev, tm = g["Status"].tolist(), g["Time"].tolist()
    ct = g.loc[g["Status"] == "Closed", "Time"]
    end = ct.max() if len(ct) else tm[-1]
    dur = (end - tm[0]).total_seconds() / 86400
    trans = [(ev[i], ev[i+1], (tm[i+1]-tm[i]).total_seconds()) for i in range(len(ev)-1)]
    return {
        "ticket": tid, "events": ev, "duration_days": dur,
        "country": g["Country"].iloc[0], "category": g["Category"].iloc[0],
        "trans": trans, "disp": ev.count("Dispatched"),
        "approved": "Approved" in ev,
    }

cases = [case_info(t) for t in df["Ticket"].unique()]
closed_cases = [c for c in cases if c["ticket"] in closed]

# Q1 detail
skipped = [c["ticket"] for c in closed_cases if not c["approved"]]
print("Q1 skipped Approved tickets:", skipped)

# Q2 - all transitions + filter >= 10 cases
tw = defaultdict(list)
tc = defaultdict(set)
for c in closed_cases:
    for a, b, w in c["trans"]:
        k = (a, b)
        tw[k].append(w)
        tc[k].add(c["ticket"])

rows = []
for k, ws in tw.items():
    rows.append({
        "transition": f"{k[0]} -> {k[1]}",
        "avg_days": np.mean(ws) / 86400,
        "median_days": np.median(ws) / 86400,
        "cases": len(tc[k]),
        "n": len(ws),
        "total_days": sum(ws) / 86400,
    })
tdf = pd.DataFrame(rows).sort_values("avg_days", ascending=False)
print("\nQ2 TOP 3 (raw avg wait):")
print(tdf.head(3)[["transition","avg_days","cases","n"]].to_string(index=False))
print("\nQ2 TOP 3 (min 10 cases):")
print(tdf[tdf["cases"]>=10].head(3)[["transition","avg_days","cases","n"]].to_string(index=False))
print("\nQ2 TOP 3 by total waiting time:")
print(tdf.sort_values("total_days", ascending=False).head(5)[["transition","avg_days","cases","total_days"]].to_string(index=False))

# Q3 - impact score
tdf["impact"] = tdf["avg_days"] * tdf["n"]
print("\nQ3 top impact:")
print(tdf.sort_values("impact", ascending=False).head(6)[["transition","avg_days","n","impact"]].to_string(index=False))

# Category full stats
cdf = pd.DataFrame([{k:v for k,v in c.items() if k!="trans" and k!="events"} for c in closed_cases])
print("\nQ4 categories:")
print(cdf.groupby("category")["duration_days"].agg(["mean","median","count"]).sort_values("mean", ascending=False))

# Q6
m = [c for c in closed_cases if c["disp"] > 1]
s = [c for c in closed_cases if c["disp"] <= 1]
print(f"\nQ6: {len(m)} cases, multi avg {np.mean([x['duration_days'] for x in m]):.2f}, single avg {np.mean([x['duration_days'] for x in s]):.2f}")

# Q7 Estonia vs Latvia
for country in ["Estonia", "Latvia", "Lithuania"]:
    sub = [c for c in closed_cases if c["country"] == country]
    viol = sum(1 for c in sub if c["duration_days"] > SLA_DAYS)
    print(f"\n{country}: closed={len(sub)}, SLA viol={viol} ({100*viol/len(sub):.2f}%)")
    print(f"  avg duration: {np.mean([c['duration_days'] for c in sub]):.2f} days")
    print(f"  median duration: {np.median([c['duration_days'] for c in sub]):.2f} days")
    cats = pd.Series([c["category"] for c in sub]).value_counts(normalize=True)
    print("  category mix:", (cats*100).round(1).to_dict())

# Activity counts Estonia vs Latvia (closed cases events)
ev = df[df["Ticket"].isin(closed)]
for pair in [("Estonia","Latvia"), ("Estonia","Lithuania")]:
    a, b = pair
    ca = ev[ev["Country"]==a]["Status"].value_counts(normalize=True)
    cb = ev[ev["Country"]==b]["Status"].value_counts(normalize=True)
    diff = (ca - cb.reindex(ca.index, fill_value=0)).abs().sort_values(ascending=False)
    print(f"\nActivity diff {a} vs {b} (top):")
    for act in diff.head(6).index:
        print(f"  {act}: {a}={ca.get(act,0)*100:.1f}% {b}={cb.get(act,0)*100:.1f}%")

# Transition comparison EE vs LV (min 20 occurrences per country)
def country_trans(country):
    sub = [c for c in closed_cases if c["country"]==country]
    d = defaultdict(list)
    for c in sub:
        for a,b,w in c["trans"]:
            d[(a,b)].append(w)
    return {f"{a}->{b}": (np.mean(v)/86400, len(v)) for (a,b),v in d.items()}

ee, lv = country_trans("Estonia"), country_trans("Latvia")
common = set(ee)&set(lv)
cmp = []
for t in common:
    if ee[t][1]>=20 and lv[t][1]>=20:
        cmp.append((t, ee[t][0], lv[t][0], ee[t][0]-lv[t][0], ee[t][1], lv[t][1]))
cmp.sort(key=lambda x: abs(x[3]), reverse=True)
print("\nTransition duration diff EE vs LV (both n>=20):")
for row in cmp[:10]:
    print(f"  {row[0]}: EE {row[1]:.2f}d (n={row[4]}) vs LV {row[2]:.2f}d (n={row[5]}) diff={row[3]:+.2f}d")
