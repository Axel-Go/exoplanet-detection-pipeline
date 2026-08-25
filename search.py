import numpy as np
import lightkurve as lk
import matplotlib.pyplot as plt

result = lk.search_lightcurve(
    "WASP-18", mission="TESS", author="SPOC", exptime=120,
)
lc = result[0].download().remove_nans().normalize()

periods = np.linspace(0.5, 5.0, 20000)
pg = lc.to_periodogram(
    method="bls",
    period=periods,
    duration=[0.05, 0.08, 0.12],
)

print("best period:  ", pg.period_at_max_power)
print("depth:        ", pg.depth_at_max_power)
print("duration:     ", pg.duration_at_max_power)
print("transit time: ", pg.transit_time_at_max_power)

pg.plot()
plt.savefig("periodogram.png", dpi=150)

folded = lc.fold(
    period=pg.period_at_max_power,
    epoch_time=pg.transit_time_at_max_power,
)
folded.scatter()
plt.savefig("folded.png", dpi=150)