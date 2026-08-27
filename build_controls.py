import os
import pandas as pd
import lightkurve as lk

OUT = "targets_control.csv"


def tic_int(x):
    """'TIC 102264230' or 102264230 -> 102264230"""
    return int(str(x).replace("TIC", "").strip())


targets = pd.read_csv("targets_known.csv")
hosts = pd.read_csv("known_hosts.csv")
host_ids = set(hosts["tic_id"].map(tic_int))

done = {}
if os.path.exists(OUT):
    prev = pd.read_csv(OUT)
    done = dict(zip(prev["matched_to"], prev["tic_id"]))
    print(f"resuming — {len(done)} controls already found")

used = set(done.values())

for _, row in targets.iterrows():
    target = tic_int(row["tic_id"])
    if target in done:
        continue

    try:
        res = lk.search_lightcurve(
            f"{row['ra']} {row['dec']}",
            radius=3600, mission="TESS", author="SPOC", exptime=120,
        )
    except Exception as e:
        print(f"  search failed near TIC {target}: {e}")
        continue

    found = None
    for name in res.table["target_name"]:
        tic = tic_int(name)
        if tic in host_ids or tic in used:
            continue
        found = tic
        break

    if found is None:
        print(f"  no control found near TIC {target}")
        continue

    used.add(found)
    done[target] = found
    pd.DataFrame([{"tic_id": found, "matched_to": target}]).to_csv(
        OUT, mode="a", header=not os.path.exists(OUT), index=False
    )
    print(f"{len(done):3d}  TIC {found}  matched to TIC {target}")

print("total controls:", len(done))
