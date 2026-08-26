import pandas as pd

known = pd.read_csv("known_planets.csv")
print("planets:     ", len(known))
print("unique stars:", known["tic_id"].nunique())

# one row per star — keep the shortest-period planet, the easiest to catch
known = known.sort_values("pl_orbper").drop_duplicates("tic_id", keep="first")
print("after dedupe:", len(known))

targets = known.sample(n=100, random_state=42).sort_values("tic_id")
targets.to_csv("targets_known.csv", index=False)
print("wrote", len(targets), "targets")