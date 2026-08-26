#!/usr/bin/env bash
# Confirmed transiting planets from the NASA Exoplanet Archive.
#
# Filters:
#   tran_flag=1        transiting, so a dip exists to find
#   tic_id not null    has a TESS identifier we can look up
#   pl_orbper < 10     at least two transits fit in one 27-day sector
#   sy_tmag < 14       bright enough that 2-minute TESS data likely exists
set -euo pipefail

curl -s -G "https://exoplanetarchive.ipac.caltech.edu/TAP/sync" \
  --data-urlencode "query=select tic_id,pl_name,hostname,pl_orbper,pl_trandur,pl_trandep,pl_tranmid,pl_rade,st_rad,ra,dec,sy_dist,sy_tmag from pscomppars where tran_flag=1 and tic_id is not null and pl_orbper < 10 and sy_tmag < 14" \
  --data-urlencode "format=csv" \
  -o known_planets.csv

echo "rows: $(wc -l < known_planets.csv)"
