import json
import os
import sys

import numpy as np
import lightkurve as lk
import matplotlib
matplotlib.use("Agg")          # no screen needed — matters in a container
import matplotlib.pyplot as plt

RESULTS = "results"
PLOTS = os.path.join(RESULTS, "plots")

PERIOD_MIN = 0.5
PERIOD_MAX = 10.0
PERIOD_STEPS = 20000
DURATIONS = [0.04, 0.06, 0.08, 0.12, 0.16]
SDE_THRESHOLD = 7.0
MIN_POINTS = 500


def as_float(x):
    """Some lightkurve values carry units, some don't. Get a plain number."""
    return float(getattr(x, "value", x))


def sector_number(mission_string):
    """'TESS Sector 02' -> 2"""
    return int(mission_string.split()[-1])


def process_star(tic, group):
    os.makedirs(PLOTS, exist_ok=True)
    rec = {"tic_id": int(tic), "group": group, "status": "ok", "reason": None}

    search = lk.search_lightcurve(
        f"TIC {tic}", mission="TESS", author="SPOC", exptime=120
    )
    if len(search) == 0:
        rec.update(status="skipped", reason="no SPOC 120s data")
        return rec

    sectors = [sector_number(m) for m in search.table["mission"]]
    i = int(np.argmin(sectors))
    rec["sector"] = sectors[i]

    lc = search[i].download().remove_nans().normalize()
    rec["n_points"] = len(lc)
    rec["span_days"] = as_float(lc.time.value.max() - lc.time.value.min())

    if len(lc) < MIN_POINTS:
        rec.update(status="skipped", reason=f"only {len(lc)} usable points")
        return rec

    periods = np.linspace(PERIOD_MIN, PERIOD_MAX, PERIOD_STEPS)
    pg = lc.to_periodogram(method="bls", period=periods, duration=DURATIONS)

    power = np.asarray(pg.power.value)
    sde = float((power.max() - power.mean()) / power.std())

    rec["period_days"] = as_float(pg.period_at_max_power)
    rec["depth"] = as_float(pg.depth_at_max_power)
    rec["duration_days"] = as_float(pg.duration_at_max_power)
    rec["transit_time"] = as_float(pg.transit_time_at_max_power)
    rec["sde"] = sde
    rec["radius_ratio"] = float(np.sqrt(max(rec["depth"], 0.0)))
    rec["verdict"] = "candidate" if sde >= SDE_THRESHOLD else "none"

    lc.scatter()
    plt.savefig(f"{PLOTS}/{tic}_raw.png", dpi=110)
    plt.close()

    pg.plot()
    plt.savefig(f"{PLOTS}/{tic}_periodogram.png", dpi=110)
    plt.close()

    lc.fold(
        period=pg.period_at_max_power,
        epoch_time=pg.transit_time_at_max_power,
    ).scatter()
    plt.savefig(f"{PLOTS}/{tic}_folded.png", dpi=110)
    plt.close()

    return rec


if __name__ == "__main__":
    tic = sys.argv[1]
    group = sys.argv[2] if len(sys.argv) > 2 else "known"
    result = process_star(tic, group)
    os.makedirs(RESULTS, exist_ok=True)
    with open(f"{RESULTS}/{tic}.json", "w") as f:
        json.dump(result, f, indent=2)
    print(json.dumps(result, indent=2))
