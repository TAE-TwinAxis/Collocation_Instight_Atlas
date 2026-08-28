from pathlib import Path
import math

import folium
import geopandas as gpd
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, Input, Output, callback, ctx, dcc, html

DATA_DIR = Path(__file__).parent / "Data"
LOOKUP_PATH = DATA_DIR / "lookup.csv"
GEOJSON_DIR = DATA_DIR / "Geojson"
JOBS_GROWTH_PATH = DATA_DIR / "Jobs_Growth.csv"
WAGE_BANDS_PATH = DATA_DIR / "Municipal_FTE_Wagebands.csv"
NEIGHBOURS_PATH = DATA_DIR / "ICM_neighbours.csv"
MAIN_TOWNS_PATH = DATA_DIR / "main_towns.csv"
CENSUS_PATH = DATA_DIR / "All_Census.csv"
CENSUS_YEARS = (1996, 2001, 2011, 2022)
WAGE_BAND_ORDER = [
    "0-1600",
    "1600-3200",
    "3200-6400",
    "6400-12800",
    "12800-25600",
    "25600-51200",
    "51200-102400",
    "102400-204800",
    "204800-409600",
    "409600-819200",
    "819200-1638400",
    "1638400-10000000",
]
LOW_FTE_VALUE = 5

CLASSIFICATION_COLOURS = {
    "Large and semi-diverse": "#3F2CCB",
    "Low GVA and high population density": "#FF8C00",
    "Manufacturing": "#66E61A",
    "Mining": "#B7410E",
    "Service centre": "#C218E8",
    "Rest of SA": "#E8E6E6",
}

DEMOGRAPHIC_GROUPS = [
    ("Black African", "Black_%"),
    ("Coloured", "Coloured_%"),
    ("Indian/Asian", "Indian_%"),
    ("White", "White_%"),
    ("Other", "Other_%"),
]


def normalize_municipality_name(name: str) -> str:
    text = str(name).strip().lower().replace("-", " ")
    text = text.replace("local municipality of ", "")
    text = text.replace(" local municipality", "")
    return " ".join(text.split())


lookup = pd.read_csv(LOOKUP_PATH)
neighbours = pd.read_csv(NEIGHBOURS_PATH, sep=";")
main_towns = pd.read_csv(MAIN_TOWNS_PATH)
jobs_growth = pd.read_csv(JOBS_GROWTH_PATH, sep=";")
jobs_growth.columns = jobs_growth.columns.str.strip()
wage_bands = pd.read_csv(WAGE_BANDS_PATH, sep=";")
wage_bands.columns = wage_bands.columns.str.strip()
wage_bands["CAT_B"] = wage_bands["CAT_B"].astype(str)
wage_bands["FTE"] = wage_bands["FTE"].astype(str).str.replace(",", ".").astype(float)
census = pd.read_csv(CENSUS_PATH, sep=";")
census.columns = census.columns.str.strip()
_census_by_key = census.assign(
    _name_key=census["MUNIC_NAME"].map(normalize_municipality_name)
).set_index("_name_key")
municipalities = sorted(lookup["Municipali"].unique())

MUNICIPALITY_CAT_B: dict[str, str] = {}
for _, _lookup_row in lookup.iterrows():
    _ward_gdf = gpd.read_file(GEOJSON_DIR / _lookup_row["GeoJSON"])
    MUNICIPALITY_CAT_B[_lookup_row["Municipali"]] = _ward_gdf["WardLabel"].iloc[0].split("_")[0]

lookup = lookup.assign(CAT_B=lookup["Municipali"].map(MUNICIPALITY_CAT_B))
neighbours = neighbours.assign(CAT_B=neighbours["CAT_B"].astype(str))
municipality_context = lookup.merge(
    neighbours[["CAT_B", "DISTRICT", "NEIGHBOURS"]],
    on="CAT_B",
    how="left",
).merge(main_towns[["Municipali", "Main_Town", "Secondary_Towns"]], on="Municipali", how="left")

_population_rank = (
    lookup.sort_values("Population", ascending=False)
    .reset_index(drop=True)
    .assign(Population_Rank=lambda frame: frame.index + 1)
    .set_index("Municipali")["Population_Rank"]
)

_geo_cache: dict[str, object] = {}


def info_card(title: str, card_id: str) -> html.Div:
    return html.Div(
        [
            html.P(title, className="card-label"),
            html.Div("—", className="card-value", id=card_id),
        ],
        className="info-card",
    )


def format_demographics(row: pd.Series) -> html.Div:
    return html.Div(
        [
            html.P(f"{label}: {row[column]:.1f}%", className="demographic-line")
            for label, column in DEMOGRAPHIC_GROUPS
        ],
        className="demographic-list",
    )


def get_municipality_gdf(municipality: str):
    if municipality not in _geo_cache:
        row = lookup.loc[lookup["Municipali"] == municipality].iloc[0]
        gdf = gpd.read_file(GEOJSON_DIR / row["GeoJSON"])
        _geo_cache[municipality] = gdf
    return _geo_cache[municipality]


def classification_colour(classification: str) -> str:
    return CLASSIFICATION_COLOURS.get(classification, "#808080")


def colour_with_alpha(hex_colour: str, alpha: float) -> str:
    hex_colour = hex_colour.lstrip("#")
    red, green, blue = (int(hex_colour[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({red},{green},{blue},{alpha})"


def format_population_count(value) -> str:
    return f"{round(round(float(value), 1)):,}"


def ordinal_rank(rank: int) -> str:
    if 11 <= rank % 100 <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(rank % 10, "th")
    return f"{rank}{suffix}"


def format_neighbouring_municipalities(raw) -> str:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)) or not str(raw).strip():
        return "—"

    text = str(raw).replace("-", ", ")
    for broken, fixed in (
        ("Kou, Kamma", "Kou-Kamma"),
        ("Ba, Phalaborwa", "Ba-Phalaborwa"),
    ):
        text = text.replace(broken, fixed)
    return text


def glance_row(label: str, value: str) -> html.Div:
    return html.Div(
        [
            html.Span(label, className="glance-label"),
            html.Span(value, className="glance-value"),
        ],
        className="glance-row",
    )


def build_glance_panel(municipality: str) -> html.Div:
    row = municipality_context.loc[municipality_context["Municipali"] == municipality].iloc[0]
    rank = int(_population_rank[municipality])
    main_town = row["Main_Town"]
    if pd.isna(main_town) or not str(main_town).strip():
        main_town = "—"
    else:
        secondary = row.get("Secondary_Towns")
        if pd.notna(secondary) and str(secondary).strip():
            main_town = f"{main_town} ({secondary})"

    return html.Div(
        [
            html.P("Municipality at a Glance", className="panel-label glance-heading"),
            html.Div(
                [
                    glance_row("Main Town", str(main_town)),
                    glance_row("District", str(row["DISTRICT"]) if pd.notna(row["DISTRICT"]) else "—"),
                    glance_row("Province", str(row["Province"])),
                    glance_row(
                        "Neighbours",
                        format_neighbouring_municipalities(row["NEIGHBOURS"]),
                    ),
                    glance_row(
                        "Population rank among 39 ICMs:",
                        ordinal_rank(rank),
                    ),
                ],
                className="glance-rows",
            ),
        ],
        className="glance-panel",
    )


def census_population_series(municipality: str) -> dict[int, float]:
    row = _census_by_key.loc[normalize_municipality_name(municipality)]
    return {year: float(row[f"Tot_pop_{year}"]) for year in CENSUS_YEARS}


def format_population_k(value: float) -> str:
    return f"{value / 1000:.1f}K"


def population_change_rows(year: int, series: dict[int, float]) -> list[tuple[str, str, str]]:
    current = series[year]
    rows: list[tuple[str, str, str]] = []
    for other in sorted(series, reverse=True):
        if other == year:
            continue
        other_value = series[other]
        if other_value == 0:
            continue
        change = (current - other_value) / other_value * 100
        connector = "since" if other < year else "from"
        if change > 0:
            direction = "up"
        elif change < 0:
            direction = "down"
        else:
            direction = "flat"
        rows.append((direction, f"{abs(change):.1f}%", f"{connector} {other}"))
    return rows


def build_population_tooltip(
    year: int,
    series: dict[int, float],
    colour: str,
    residents_display: str | None = None,
) -> html.Div:
    if residents_display is None:
        residents_display = f"{int(round(series[year])):,}"
    change_rows = []
    for direction, percent, phrase in population_change_rows(year, series):
        triangle = {"up": "▲", "down": "▼"}.get(direction, "•")
        change_rows.append(
            html.Div(
                [
                    html.Span(f"{triangle} {percent}", className=f"pop-tip-change-{direction}"),
                    html.Span(f" {phrase}", className="pop-tip-change-phrase"),
                ],
                className="pop-tip-change",
            )
        )

    return html.Div(
        [
            html.Div(str(year), className="pop-tip-year", style={"color": colour}),
            html.Div(
                [
                    html.Span("Residents", className="pop-tip-residents-label"),
                    html.Span(residents_display, className="pop-tip-residents-value"),
                ],
                className="pop-tip-residents",
            ),
            *change_rows,
        ],
        className="pop-tip",
    )


def population_tooltip_style(bbox, colour: str) -> dict:
    style = {
        "display": "block",
        "borderLeftColor": colour,
    }
    if not bbox:
        style.update({"right": "16px", "top": "12px"})
        return style

    left = bbox.get("x1", 0) + 12
    top = max(bbox.get("y0", 0) - 8, 8)
    style.update({"left": f"{left}px", "top": f"{top}px"})
    return style


def jobs_cat_b(municipali: str) -> str:
    return MUNICIPALITY_CAT_B[municipali]


def format_wage_band_label(band: str) -> str:
    low, high = band.split("-")
    return f"R{int(low):,}-R{int(high):,}"


def build_wage_band_chart(municipality: str, classification: str) -> go.Figure:
    cat_b = jobs_cat_b(municipality)
    data = wage_bands[wage_bands["CAT_B"] == cat_b].copy()
    band_order = {band: index for index, band in enumerate(WAGE_BAND_ORDER)}
    data["band_order"] = data["RealWageBand"].map(band_order)
    data = data.sort_values("band_order")
    data = data[data["FTE"] != LOW_FTE_VALUE]

    total_fte = float(data["FTE"].sum())
    data["share"] = data["FTE"] / total_fte * 100 if total_fte > 0 else 0
    data["label"] = data["RealWageBand"].map(format_wage_band_label)
    band_colour = classification_colour(classification)
    hover_fte = [f"{fte:,.0f}" for fte in data["FTE"]]

    ymax = float(data["FTE"].max()) if not data.empty else 0
    y_ticks = employment_y_ticks(ymax)
    y_top = y_ticks[-1]

    fig = go.Figure(
        go.Bar(
            x=data["label"],
            y=data["FTE"],
            marker_color=band_colour,
            customdata=data["share"],
            hovertext=hover_fte,
            hovertemplate=(
                "FTE Jobs: %{hovertext}<br>"
                "<span style='font-size:smaller'>"
                "Share of Total: %{customdata:.1f}%"
                "</span><extra></extra>"
            ),
        )
    )
    fig.update_layout(
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        margin=dict(l=56, r=32, t=32, b=72),
        autosize=True,
        hovermode="closest",
        xaxis=dict(
            title=None,
            tickfont=dict(size=10),
            tickangle=-35,
            gridcolor="rgba(0,0,0,0)",
            showline=False,
            zeroline=False,
        ),
        yaxis=dict(
            title=None,
            range=[0, y_top],
            tickvals=y_ticks,
            ticktext=[f"{tick:,}" for tick in y_ticks],
            tickfont=dict(size=11),
            gridcolor="#e5e7eb",
            griddash="dot",
            showline=False,
            zeroline=False,
        ),
        showlegend=False,
    )
    return fig


def employment_y_ticks(ymax: float, target_ticks: int = 5) -> list[int]:
    if ymax <= 0:
        return [0]

    upper = ymax * 1.08
    raw_step = upper / max(target_ticks - 1, 1)
    magnitude = 10 ** math.floor(math.log10(raw_step))
    fraction = raw_step / magnitude

    if fraction <= 1:
        nice_fraction = 1
    elif fraction <= 2:
        nice_fraction = 2
    elif fraction <= 5:
        nice_fraction = 5
    else:
        nice_fraction = 10

    step = int(nice_fraction * magnitude)
    top = math.ceil(upper / step) * step
    return list(range(0, top + 1, step))


def build_employment_chart(municipality: str, classification: str) -> go.Figure:
    cat_b = jobs_cat_b(municipality)
    data = jobs_growth[jobs_growth["CAT_B"] == cat_b].sort_values("TaxYear")
    line_colour = classification_colour(classification)
    year_min = int(data["TaxYear"].min())
    year_max = int(data["TaxYear"].max())
    ymax = float(data["FTE"].max())
    y_ticks = employment_y_ticks(ymax)
    y_top = y_ticks[-1]

    fig = go.Figure(
        go.Scatter(
            x=data["TaxYear"],
            y=data["FTE"],
            mode="lines",
            line=dict(color=line_colour, width=2, shape="spline"),
            fill="tozeroy",
            fillcolor=colour_with_alpha(line_colour, 0.18),
            hovertemplate="Year: %{x}<br>Total Jobs: %{y:,.0f}<extra></extra>",
        )
    )
    fig.update_layout(
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        margin=dict(l=56, r=32, t=32, b=40),
        autosize=True,
        hovermode="x",
        xaxis=dict(
            title=None,
            range=[year_min - 0.65, year_max + 0.65],
            tickmode="linear",
            dtick=2,
            tickfont=dict(size=11),
            gridcolor="rgba(0,0,0,0)",
            showline=False,
            zeroline=False,
            showspikes=True,
            spikemode="across+marker",
            spikesnap="cursor",
            spikecolor="rgba(107,114,128,0.55)",
            spikethickness=1,
            spikedash="dot",
        ),
        yaxis=dict(
            title=None,
            range=[0, y_top],
            tickvals=y_ticks,
            ticktext=[f"{tick:,}" for tick in y_ticks],
            tickfont=dict(size=11),
            gridcolor="#e5e7eb",
            griddash="dot",
            showline=False,
            zeroline=False,
        ),
        showlegend=False,
    )
    return fig


def build_population_chart(municipality: str, classification: str) -> go.Figure:
    series = census_population_series(municipality)
    years = list(CENSUS_YEARS)
    values = [series[year] for year in years]
    line_colour = classification_colour(classification)
    ymax = max(values)
    y_ticks = employment_y_ticks(ymax)
    y_top = y_ticks[-1]

    fig = go.Figure(
        go.Scatter(
            x=years,
            y=values,
            mode="lines+markers+text",
            line=dict(color=line_colour, width=2.5, shape="spline"),
            marker=dict(size=10, color=line_colour),
            fill="tozeroy",
            fillcolor=colour_with_alpha(line_colour, 0.18),
            text=[format_population_k(value) for value in values],
            textposition="top center",
            textfont=dict(size=11, color="#1a1a2e"),
            hoverinfo="none",
        )
    )
    fig.update_layout(
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        margin=dict(l=56, r=32, t=36, b=40),
        autosize=True,
        hovermode="closest",
        xaxis=dict(
            title=None,
            range=[1993, 2025],
            tickmode="array",
            tickvals=years,
            tickfont=dict(size=11),
            gridcolor="rgba(0,0,0,0)",
            showline=False,
            zeroline=False,
        ),
        yaxis=dict(
            title=None,
            range=[0, y_top],
            tickvals=y_ticks,
            ticktext=["0" if tick == 0 else format_population_k(tick) for tick in y_ticks],
            tickfont=dict(size=11),
            gridcolor="#e5e7eb",
            griddash="dot",
            showline=False,
            zeroline=False,
        ),
        showlegend=False,
    )
    return fig


def ward_style(feature: dict) -> dict:
    colour = classification_colour(feature["properties"]["CLASSIFICATION"])
    return {
        "fillColor": colour,
        "color": "white",
        "weight": 1,
        "fillOpacity": 0.7,
    }


def ward_highlight(feature: dict) -> dict:
    colour = classification_colour(feature["properties"]["CLASSIFICATION"])
    return {
        "fillColor": colour,
        "color": "black",
        "weight": 3,
        "fillOpacity": 0.9,
    }


def build_map(municipality: str) -> str:
    subset = get_municipality_gdf(municipality).copy()

    pop_cols = [
        "PopGBlack",
        "PopGColour",
        "PopGIndian",
        "PopGWhite",
        "PopGOther",
        "PopGTotal",
    ]
    for col in pop_cols:
        if col == "PopGTotal":
            subset[col] = subset[col].map(format_population_count)
        else:
            subset[col] = subset[col].map("{:,.0f}".format)

    centre = subset.geometry.union_all().centroid
    folium_map = folium.Map(
        location=[centre.y, centre.x],
        zoom_start=10,
        tiles=None,
        zoom_control=True,
        scrollWheelZoom=False,
    )

    folium.GeoJson(
        subset,
        style_function=ward_style,
        highlight_function=ward_highlight,
        tooltip=folium.GeoJsonTooltip(
            fields=[
                "WardNo",
                "CLASSIFICATION",
                "PopGBlack",
                "PopGColour",
                "PopGIndian",
                "PopGWhite",
                "PopGOther",
                "PopGTotal",
            ],
            aliases=[
                "Ward:",
                "Classification:",
                "Black African:",
                "Coloured:",
                "Indian/Asian:",
                "White:",
                "Other:",
                "Total Population:",
            ],
            sticky=True,
            labels=True,
            localize=True,
        ),
    ).add_to(folium_map)

    bounds = subset.total_bounds
    folium_map.fit_bounds(
        [[bounds[1], bounds[0]], [bounds[3], bounds[2]]],
        padding=(12, 12),
    )

    return folium_map._repr_html_()


app = Dash(__name__)
server = app.server

app.layout = html.Div(
    [
        html.Header(
            html.Div(
                [
                    html.Div(
                        html.Img(
                            src="/assets/new_logo_design_collocation.png",
                            alt="Collocation",
                            className="header-logo header-logo-left",
                        ),
                        className="header-brand-left",
                    ),
                    html.Div(
                        [
                            html.H1("Collocation Insights Atlas", className="page-header"),
                            html.P(
                                "Supporting decision-making on people, places and economic potential through data",
                                className="page-subtitle",
                            ),
                        ],
                        className="header-copy",
                    ),
                    html.Div(
                        [
                            html.Span("Powered by", className="powered-by"),
                            html.Img(
                                src="/assets/collocation_logo_inline_colour.png",
                                alt="Collocation",
                                className="header-logo header-logo-right",
                            ),
                        ],
                        className="header-brand-right",
                    ),
                ],
                className="header-inner",
            ),
            className="header-bar",
        ),
        html.Main(
            [
                html.Section(
                    [
                        html.Label("Municipality", htmlFor="municipality-dropdown"),
                        dcc.Dropdown(
                            id="municipality-dropdown",
                            options=[
                                {"label": name, "value": name} for name in municipalities
                            ],
                            value=municipalities[0],
                            clearable=False,
                            className="municipality-dropdown",
                        ),
                    ],
                    className="controls-section",
                ),
                html.Section(
                    [
                        info_card("Classification", "card-classification"),
                        info_card("Total Wards", "card-wards"),
                        info_card("Demographic", "card-demographics"),
                        info_card("Total Population", "card-population"),
                    ],
                    className="cards-grid",
                ),
                html.Section(
                    [
                        html.Div(
                            [
                                html.P("Population Over Time", className="panel-label"),
                                html.Div(
                                    [
                                        dcc.Graph(
                                            id="population-chart",
                                            figure=build_population_chart(
                                                municipalities[0],
                                                lookup.loc[
                                                    lookup["Municipali"] == municipalities[0],
                                                    "Classification",
                                                ].iloc[0],
                                            ),
                                            config={"displayModeBar": False, "responsive": True},
                                            className="chart-frame",
                                            clear_on_unhover=True,
                                        ),
                                        html.Div(
                                            id="population-tooltip",
                                            className="population-tooltip",
                                            style={"display": "none"},
                                        ),
                                    ],
                                    className="chart-hover-wrap",
                                ),
                                html.P("Source: StatsSA", className="panel-footnote"),
                            ],
                            className="chart-panel",
                        ),
                        html.Div(
                            [
                                html.P("Municipality Ward Map", className="panel-label"),
                                html.Iframe(
                                    id="municipality-map",
                                    className="map-frame",
                                    sandbox="allow-scripts allow-same-origin",
                                ),
                                html.P("Source: StatsSA", className="panel-footnote"),
                            ],
                            className="map-panel",
                        ),
                        html.Div(
                            [
                                html.P("Employment Trend", className="panel-label"),
                                dcc.Graph(
                                    id="employment-chart",
                                    config={"displayModeBar": False, "responsive": True},
                                    className="chart-frame",
                                ),
                                html.P("Source: SEAD-SA", className="panel-footnote"),
                                html.P(
                                    "Number of FTE employees per municipality recorded per tax year",
                                    className="panel-footnote-secondary",
                                ),
                            ],
                            className="chart-panel",
                        ),
                        html.Div(
                            [
                                html.P("FTE by Wage Band 2025", className="panel-label"),
                                dcc.Graph(
                                    id="wage-band-chart",
                                    figure=build_wage_band_chart(
                                        municipalities[0],
                                        lookup.loc[
                                            lookup["Municipali"] == municipalities[0],
                                            "Classification",
                                        ].iloc[0],
                                    ),
                                    config={"displayModeBar": False, "responsive": True},
                                    className="chart-frame",
                                ),
                                html.P("Source: SEAD-SA", className="panel-footnote"),
                                html.P(
                                    "Number of FTE Employees per Wage Band",
                                    className="panel-footnote-secondary",
                                ),
                            ],
                            className="chart-panel",
                        ),
                    ],
                    className="insights-grid",
                ),
                html.Section(
                    html.Div(id="glance-panel"),
                    className="glance-section",
                ),
            ],
            className="page-content",
        ),
    ],
    className="app-shell",
)


@callback(
    Output("card-classification", "children"),
    Output("card-wards", "children"),
    Output("card-demographics", "children"),
    Output("card-population", "children"),
    Output("population-chart", "figure"),
    Output("employment-chart", "figure"),
    Output("wage-band-chart", "figure"),
    Output("municipality-map", "srcDoc"),
    Output("glance-panel", "children"),
    Input("municipality-dropdown", "value"),
)
def update_dashboard(selected_municipality):
    if selected_municipality is None:
        return "—", "—", "—", "—", go.Figure(), go.Figure(), go.Figure(), "", html.Div()

    row = lookup.loc[lookup["Municipali"] == selected_municipality].iloc[0]

    return (
        row["Classification"],
        f"{int(row['Wards']):,}",
        format_demographics(row),
        format_population_count(row["Population"]),
        build_population_chart(selected_municipality, row["Classification"]),
        build_employment_chart(selected_municipality, row["Classification"]),
        build_wage_band_chart(selected_municipality, row["Classification"]),
        build_map(selected_municipality),
        build_glance_panel(selected_municipality),
    )


@callback(
    Output("population-tooltip", "children"),
    Output("population-tooltip", "style"),
    Input("population-chart", "hoverData"),
    Input("municipality-dropdown", "value"),
)
def update_population_tooltip(hover_data, selected_municipality):
    hidden = {"display": "none"}
    if ctx.triggered_id == "municipality-dropdown" or not hover_data or selected_municipality is None:
        return None, hidden

    year = int(hover_data["points"][0]["x"])
    series = census_population_series(selected_municipality)
    if year not in series:
        return None, hidden

    classification = lookup.loc[lookup["Municipali"] == selected_municipality, "Classification"].iloc[0]
    colour = classification_colour(classification)
    bbox = hover_data["points"][0].get("bbox")
    residents_display = None
    if year == 2022:
        residents_display = format_population_count(
            lookup.loc[lookup["Municipali"] == selected_municipality, "Population"].iloc[0]
        )
    return build_population_tooltip(year, series, colour, residents_display), population_tooltip_style(bbox, colour)


if __name__ == "__main__":
    app.run(debug=True)
