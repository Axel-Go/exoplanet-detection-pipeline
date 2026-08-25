import numpy as np
import lightkurve as lk
import matplotlib.pyplot as plt

result = lk.search_lightcurve(
    "WASP-18",
    mission="TESS",
    author="SPOC",
    exptime=120,
)

print(result)

lc = result[0].download()

print(lc)
print("Points:", len(lc))

lc.scatter()
plt.savefig("wasp18_sector2.png", dpi=150)

def transit_time(lc, t0, t1):
    sel = lc[(lc.time.value > t0) & (lc.time.value < t1)]
    if len(sel) == 0:
        raise ValueError(f"no data between {t0} and {t1}")

    flux = sel.flux.value
    i = np.argmin(flux)
    depth = (np.median(flux) - flux[i]) / np.median(flux)

    if depth < 0.005:
        raise ValueError(
            f"no transit between {t0} and {t1} — "
            f"deepest point is only {depth:.3%} below the median"
        )

    return sel.time.value[i]


# --- diagnostic: where is the last transit? ---
lc[(lc.time.value > 1379) & (lc.time.value < 1381.6)].scatter()
plt.savefig("last_days.png", dpi=150)

first = transit_time(lc, 1354.0, 1355.0)
last = transit_time(lc, 1380.5, 1381.1)
print("first:   ", first)
print("last    :", last)
print("baseline:", last - first)



