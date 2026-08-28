import json
import os
import time

import pandas as pd

from worker import process_star, RESULTS


def tic_int(x):
    return int(str(x).replace("TIC", "").strip())


known = pd.read_csv("targets_known.csv")
control = pd.read_csv("targets_control.csv")

stars = [(tic_int(t), "known") for t in known["tic_id"]]
stars += [(tic_int(t), "control") for t in control["tic_id"]]

os.makedirs(RESULTS, exist_ok=True)
print(f"{len(stars)} stars to process")

start = time.time()
done = failed = skipped = 0

for n, (tic, group) in enumerate(stars, 1):
    path = f"{RESULTS}/{tic}.json"
    if os.path.exists(path):
        done += 1
        continue

    try:
        rec = process_star(tic, group)
    except Exception as e:
        failed += 1
        print(f"[{n:3d}/{len(stars)}] TIC {tic:<12} FAILED  {type(e).__name__}: {e}")
        continue

    with open(path, "w") as f:
        json.dump(rec, f, indent=2)

    done += 1
    if rec["status"] != "ok":
        skipped += 1
        print(f"[{n:3d}/{len(stars)}] TIC {tic:<12} skipped  {rec['reason']}")
    else:
        print(f"[{n:3d}/{len(stars)}] TIC {tic:<12} {rec['verdict']:<9} "
              f"P={rec['period_days']:.4f}d  SDE={rec['sde']:.1f}")

elapsed = time.time() - start
print(f"\n{done} results, {skipped} skipped, {failed} failed, {elapsed/60:.1f} min")
