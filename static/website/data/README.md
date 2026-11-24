# India boundary data

`india-geo.json` is a compact, pre-built dataset of India's country outline and
every state/UT boundary, sourced from **Natural Earth 1:50m admin-0 / admin-1**
(public domain — safe for commercial use, no attribution required):
https://www.naturalearthdata.com/about/terms-of-use/

It replaces hand-drawn polygon approximations with real geographic boundaries.

Rebuild it (e.g. after a Natural Earth update) with:

```bash
python -m pip install shapely
python scripts/build_india_geo.py
```

The script downloads the source files into `public/data/*_raw.geojson` first
(not committed — delete them after running), simplifies each polygon with
Shapely, and writes the compact `india-geo.json` consumed by
`src/components/cinema/earth/globe.ts`.
