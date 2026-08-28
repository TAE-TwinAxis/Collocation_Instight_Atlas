# Collocation Insights Atlas

*Supporting decision-making on people, places and economic potential through data*

Interactive Dash dashboard for exploring South Africa’s 39 Intermediary Cities (ICM) municipalities — classification, demographics, population change, employment, wage bands, and ward-level maps.

## What the dashboard shows

- **Municipality selector** with summary cards for classification, wards, demographics, and total population
- **Population Over Time** — census totals for 1996, 2001, 2011, and 2022
- **Municipality Ward Map** — ward boundaries coloured by ICM classification
- **Employment Trend** — full-time equivalent (FTE) jobs by tax year
- **FTE by Wage Band 2025** — municipal employment by real wage band
- **Municipality at a Glance** — main town, district, province, neighbours, and population rank among the 39 ICMs

## Data components

| File / folder | Used for |
|---------------|----------|
| `Data/lookup.csv` | Municipality list, classification, province, ward count, population, demographic shares, GeoJSON filenames |
| `Data/All_Census.csv` | Population over time (`Tot_pop_1996` … `Tot_pop_2022`) |
| `Data/Jobs_Growth.csv` | Employment trend by tax year (linked via `CAT_B`) |
| `Data/Municipal_FTE_Wagebands.csv` | FTE employment by real wage band (linked via `CAT_B`) |
| `Data/ICM_neighbours.csv` | District and neighbouring municipalities (linked via `CAT_B`) |
| `Data/main_towns.csv` | Main and secondary towns for the glance panel |
| `Data/Geojson/` | Ward boundary GeoJSON files (one per municipality; filenames from `lookup.csv`) |

## Data sources

Sources are shown in the dashboard footnotes where applicable:

| Component | Source (as shown in app) |
|-----------|--------------------------|
| Population Over Time | **StatsSA** |
| Municipality Ward Map | **StatsSA** |
| Employment Trend | **SEAD-SA** |
| FTE by Wage Band 2025 | **SEAD-SA** |

The `main_towns.csv` file includes a `Source` column per municipality (e.g. Wikipedia, municipal profiles, gov.za). Other bundled CSV files are pre-processed datasets prepared for this dashboard; no additional external source is labelled in the application for those files.

## Requirements

- Python 3.10+
- Packages listed in `requirements.txt`:
  - `dash`, `pandas`, `plotly` — web app and charts
  - `geopandas`, `folium` — geospatial data and maps
  - `gunicorn` — production deployment (Linux)

## Installation

Clone the repository and install dependencies from the project root:

```bash
git clone https://github.com/Majaha-collocation/Collocation_Insight_Atlas.git
cd Collocation_Insight_Atlas
pip install -r requirements.txt
```

On Windows, if `geopandas` fails to install via pip, use Conda for geospatial dependencies first:

```bash
conda install geopandas
pip install -r requirements.txt
```

## Run locally

From the repository root (the folder containing `app.py`):

```bash
python app.py
```

Open [http://127.0.0.1:8050/](http://127.0.0.1:8050/) in your browser.

## Production deployment

On Linux, serve with Gunicorn:

```bash
gunicorn app:server
```

Gunicorn does not run natively on Windows; use `python app.py` for local development.

## Project structure

```
Collocation_Insight_Atlas/
├── app.py
├── requirements.txt
├── README.md
├── assets/
│   ├── styles.css
│   ├── new_logo_design_collocation.png
│   └── collocation_logo_inline_colour.png
└── Data/
    ├── lookup.csv
    ├── All_Census.csv
    ├── Jobs_Growth.csv
    ├── Municipal_FTE_Wagebands.csv
    ├── ICM_neighbours.csv
    ├── main_towns.csv
    └── Geojson/
        └── *.geojson
```

## ICM classification colours

| Classification | Colour |
|---|---|
| Large and semi-diverse | `#3F2CCB` |
| Low GVA and high population density | `#FF8C00` |
| Manufacturing | `#66E61A` |
| Mining | `#B7410E` |
| Service centre | `#C218E8` |
| Rest of SA | `#E8E6E6` |

## Troubleshooting

**GeoJSON file not found** — Confirm ward files are in `Data/Geojson/` and that `lookup.csv` references them in the `GeoJSON` column.

**Maps appear in the wrong location** — Ward GeoJSON files may need CRS review. Contact the repository maintainer if boundaries look misaligned.

**Slow startup** — The app loads all 39 municipality GeoJSON files at startup to build ward maps and municipality keys. This is expected on first run.
