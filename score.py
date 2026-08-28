import glob
import json
import sys

import pandas as pd

RESULTS = "results"
TOL = 0.02
HARMONICS = [1, 2, 3, 4, 5, 6, 0.5, 1 / 3, 0.25]

# a candidate must clear the SDE threshold (already baked into `verdict`)
# AND be small enough to plausibly be a planet
MAX_RATIO = float(sys.argv[1]) if len(sys.argv) > 1 else 0.15


def tic_int(x):
    return int(str(x).replace("TIC", "").strip())


def classify(found, known):
    ratio = found / known
    for h in HARMONICS:
        if abs(ratio - h) / h < TOL:
            return "exact" if h == 1 else f"x{h:g}"
    return "wrong"


def is_candidate(r, max_ratio):
    return r["verdict"] == "candidate" and r["radius_ratio"] <= max_ratio


known_tbl = pd.read_csv("targets_known.csv")
truth = dict(zip(known_tbl["tic_id"].map(tic_int), known_tbl["pl_orbper"]))

records = []
for path in glob.glob(f"{RESULTS}/*.json"):
    with open(path) as f:
        records.append(json.load(f))

k = [r for r in records if r["group"] == "known"]
k_ok = [r for r in k if r["status"] == "ok" and r["tic_id"] in truth]
k_skip = [r for r in k if r["status"] != "ok"]
stray = [r for r in k if r["status"] == "ok" and r["tic_id"] not in truth]

c_ok = [r for r in records if r["group"] == "control" and r["status"] == "ok"]

if stray:
    print(f"WARNING: {len(stray)} 'known' results have no catalogue entry "
          f"and were excluded: {[r['tic_id'] for r in stray]}\n")


def evaluate(max_ratio):
    rec, har, wrong, missed = [], [], [], []
    for r in k_ok:
        if not is_candidate(r, max_ratio):
            missed.append(r)
            continue
        kind = classify(r["period_days"], truth[r["tic_id"]])
        if kind == "exact":
            rec.append(r)
        elif kind == "wrong":
            wrong.append(r)
        else:
            r["harmonic"] = kind
            har.append(r)
    fa = [r for r in c_ok if is_candidate(r, max_ratio)]
    return rec, har, wrong, missed, fa


n, m = len(k_ok), len(c_ok)

print("TRADE-OFF: how the size cap changes both numbers\n")
print("  max radius ratio   recall   false alarms")
for cap in [1.00, 0.30, 0.25, 0.20, 0.15, 0.12, 0.10]:
    rec, har, wrong, missed, fa = evaluate(cap)
    label = "none" if cap >= 1 else f"{cap:.2f}"
    print(f"  {label:>16}   {(len(rec)+len(har))/n:6.1%}   {len(fa)/m:6.1%}")

rec, har, wrong, missed, fa = evaluate(MAX_RATIO)
found_total = len(rec) + len(har)

print(f"\n=== AT max radius ratio {MAX_RATIO} ===\n")
print("KNOWN PLANETS")
print(f"  attempted           {len(k)}")
print(f"  no usable data      {len(k_skip)}")
print(f"  analysed            {n}")
print(f"  correct period      {len(rec):3d}  {len(rec)/n:6.1%}")
print(f"  harmonic of it      {len(har):3d}  {len(har)/n:6.1%}")
print(f"  wrong period        {len(wrong):3d}  {len(wrong)/n:6.1%}")
print(f"  not detected        {len(missed):3d}  {len(missed)/n:6.1%}")
print(f"  RECALL              {found_total:3d}  {found_total/n:6.1%}")
print("\nCONTROLS")
print(f"  analysed            {m}")
print(f"  false alarms        {len(fa):3d}  {len(fa)/m:6.1%}")

if har:
    print("\nFOUND AT A MULTIPLE OF THE TRUE PERIOD")
    for r in sorted(har, key=lambda r: r["tic_id"]):
        print(f"  TIC {r['tic_id']:<12} {r['harmonic']:>5}  "
              f"found {r['period_days']:.4f}  true {truth[r['tic_id']]:.4f}")

if fa:
    print("\nSURVIVING FALSE ALARMS, STRONGEST FIRST")
    for r in sorted(fa, key=lambda r: -r["sde"]):
        print(f"  TIC {r['tic_id']:<12} SDE={r['sde']:5.1f}  "
              f"P={r['period_days']:.4f}  ratio={r['radius_ratio']:.3f}")

summary = {
    "sde_threshold": 7.0,
    "max_radius_ratio": MAX_RATIO,
    "known_attempted": len(k),
    "known_skipped": len(k_skip),
    "known_analysed": n,
    "correct_period": len(rec),
    "harmonic": len(har),
    "wrong_period": len(wrong),
    "not_detected": len(missed),
    "recall": found_total / n,
    "controls_analysed": m,
    "false_alarms": len(fa),
    "false_alarm_rate": len(fa) / m,
}
with open("summary.json", "w") as f:
    json.dump(summary, f, indent=2)
