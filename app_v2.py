import os
import dash
from dash import dcc, html, dash_table, Input, Output, State, ctx
import plotly.express as px
import pandas as pd
import numpy as np
from databricks.sdk import WorkspaceClient

WAREHOUSE_ID = os.environ.get("DATABRICKS_WAREHOUSE_ID", "401941d60f2786b9")
w = WorkspaceClient()


def run_query(sql_text: str) -> pd.DataFrame:
    resp = w.statement_execution.execute_statement(
        warehouse_id=WAREHOUSE_ID, statement=sql_text, wait_timeout="50s"
    )
    if resp.status and resp.status.error:
        raise RuntimeError(f"SQL error: {resp.status.error.message}")
    if resp.manifest is None:
        raise RuntimeError(f"Query returned no manifest. Status: {resp.status}")
    cols = [c.name for c in resp.manifest.schema.columns]
    rows = resp.result.data_array if resp.result and resp.result.data_array else []
    return pd.DataFrame(rows, columns=cols)


print("Loading business data ...")
df = run_query("""
    SELECT business_id, business_name, category, subcategories,
           city, state, address, postal_code,
           latitude, longitude, review_count, rating, checkin_count
    FROM genieology.gold.business
""")
print(f"Loaded {len(df):,} businesses")

for c in ["latitude", "longitude", "rating"]:
    df[c] = pd.to_numeric(df[c], errors="coerce")
for c in ["review_count", "checkin_count"]:
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)


def split_subcats(s):
    """subcategories is stored as a comma-separated string per business."""
    if pd.isna(s) or not str(s).strip():
        return []
    return [x.strip() for x in str(s).split(",") if x.strip()]


df["subcat_list"] = df["subcategories"].apply(split_subcats)

CATEGORIES = sorted(df["category"].dropna().unique())
CITIES = sorted(df["city"].dropna().unique())
STATES = sorted(df["state"].dropna().unique())
ALL_SUBCATS = sorted({sc for lst in df["subcat_list"] for sc in lst})

# ── Theme: warm cream & mauve ──
BG = "#F7F3EF"
CARD = "#FFFFFF"
BORDER = "#DCD4D9"
PRIMARY = "#5B4A5E"
TEXT_DARK = "#2D1F30"
TEXT_MED = "#6B5B6E"
TEXT_LIGHT = "#9B8E9E"
ACCENT = "#8B6B78"
HIGHLIGHT_BG = "#F0EAE6"

# A broad, highly distinguishable qualitative palette for categorical map colors.
# (Mixing two qualitative sets gives enough visually separated hues even when
# there are many categories — same-hue palettes are hard to tell apart on a map.)
PALETTE = px.colors.qualitative.Alphabet + px.colors.qualitative.Dark24
CAT_COLORS = {cat: PALETTE[i % len(PALETTE)] for i, cat in enumerate(CATEGORIES)}

SANS = "'Inter', -apple-system, sans-serif"
SERIF = "'DM Serif Display', serif"

REVIEW_THRESHOLDS = [0, 10, 25, 50, 100, 250, 500, 1000]
CHECKIN_THRESHOLDS = [0, 10, 25, 50, 100, 250, 500]


def kpi_card(label, value, subtitle=""):
    return html.Div([
        html.P(label, style={"color": TEXT_LIGHT, "fontSize": "11px", "margin": "0 0 6px",
                              "textTransform": "uppercase", "letterSpacing": "1.5px", "fontFamily": SANS}),
        html.H3(value, style={"color": TEXT_DARK, "margin": "0", "fontSize": "28px",
                               "fontWeight": "700", "fontFamily": SANS}),
        html.P(subtitle, style={"color": ACCENT, "fontSize": "12px",
                                 "margin": "6px 0 0", "fontFamily": SANS}) if subtitle else None,
    ], style={"background": CARD, "border": f"1px solid {BORDER}",
              "borderRadius": "4px", "padding": "20px 24px",
              "flex": "1", "minWidth": "160px", "textAlign": "center"})


def highlight_card(label, name, detail):
    return html.Div([
        html.P(label, style={"color": TEXT_LIGHT, "fontSize": "10px", "textTransform": "uppercase",
                              "letterSpacing": "1.5px", "margin": "0 0 6px", "fontFamily": SANS}),
        html.P(name, style={"color": TEXT_DARK, "fontWeight": "600", "fontSize": "14px",
                             "margin": "0 0 4px", "whiteSpace": "nowrap",
                             "overflow": "hidden", "textOverflow": "ellipsis",
                             "fontFamily": SANS}, title=name),
        html.P(detail, style={"color": ACCENT, "fontSize": "12px", "margin": "0", "fontFamily": SANS}),
    ], style={"background": CARD, "border": f"1px solid {BORDER}",
              "borderRadius": "4px", "padding": "16px", "marginBottom": "10px"})


def filter_field(label, children):
    return html.Div(style={"flex": "1", "minWidth": "180px"}, children=[
        html.Label(label, style={"color": TEXT_MED, "fontSize": "11px",
                    "display": "block", "marginBottom": "4px",
                    "textTransform": "uppercase", "letterSpacing": "0.5px", "fontFamily": SANS}),
        children,
    ])


app = dash.Dash(__name__, title="Blanche Lifestyle Magazine")
app.config.suppress_callback_exceptions = True

app.index_string = """<!DOCTYPE html>
<html>
<head>
    {%metas%}
    <title>{%title%}</title>
    {%favicon%}
    {%css%}
    <link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body { margin: 0; background: #F7F3EF; }
        .Select-control { background-color: #FFFFFF !important; border-color: #DCD4D9 !important; color: #2D1F30 !important; border-radius: 2px !important; }
        .Select-menu-outer { background-color: #FFFFFF !important; border-color: #DCD4D9 !important; }
        .VirtualizedSelectOption { background-color: #FFFFFF; color: #2D1F30; }
        .VirtualizedSelectFocusedOption { background-color: #F0EAE6 !important; }
        .Select-value-label { color: #2D1F30 !important; }
        .Select-placeholder { color: #9B8E9E !important; }
        .Select-input input { color: #2D1F30 !important; }
        .Select--multi .Select-value { background-color: #5B4A5E !important; border-color: #5B4A5E !important; color: white !important; border-radius: 2px !important; }
        .Select--multi .Select-value-icon { border-color: rgba(255,255,255,0.3) !important; }
        .Select--multi .Select-value-icon:hover { background-color: #4A3A4D !important; color: white !important; }
        .Select-arrow { border-color: #9B8E9E transparent transparent !important; }
        .Select.is-open > .Select-control .Select-arrow { border-color: transparent transparent #9B8E9E !important; }
        .Select-clear { color: #9B8E9E !important; }
        .Select-noresults { color: #9B8E9E; background: #FFFFFF; }
        .dash-spreadsheet .dash-filter input { background-color: #FFFFFF !important; color: #2D1F30 !important; border-color: #DCD4D9 !important; }
        .previous-next-container button { color: #5B4A5E !important; background: transparent !important; }
        .page-number { color: #2D1F30 !important; }
        .genie-input::placeholder { color: #9B8E9E; }
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: #F7F3EF; }
        ::-webkit-scrollbar-thumb { background: #DCD4D9; border-radius: 3px; }
    </style>
</head>
<body>
    {%app_entry%}
    <footer>
        {%config%}
        {%scripts%}
        {%renderer%}
    </footer>
</body>
</html>"""

app.layout = html.Div(
    style={"backgroundColor": BG, "fontFamily": SANS, "minHeight": "100vh", "color": TEXT_DARK},
    children=[
        # ── Header ──
        html.Div(style={"background": PRIMARY, "padding": "28px 40px", "color": "white"}, children=[
            html.H1("BLANCHE", style={"fontFamily": SERIF, "fontSize": "38px",
                     "fontWeight": "400", "margin": "0", "letterSpacing": "6px"}),
            html.P("LIFESTYLE MAGAZINE", style={"fontFamily": SANS, "fontSize": "11px",
                    "letterSpacing": "5px", "margin": "4px 0 0", "opacity": "0.75"}),
            html.P("Yelp Business Overview", style={"fontFamily": SANS, "fontSize": "13px",
                    "margin": "14px 0 0", "opacity": "0.55"}),
        ]),
        # ── KPI Row ──
        html.Div(id="kpi-row", style={"display": "flex", "gap": "16px", "padding": "24px 40px 0"}),
        # ── Map + Highlights ──
        html.Div(style={"display": "flex", "gap": "20px", "padding": "20px 40px", "alignItems": "stretch"}, children=[
            html.Div(style={"flex": "1", "minWidth": "0"}, children=[
                html.P("BUSINESS MAP", style={"color": TEXT_LIGHT, "fontSize": "11px",
                        "letterSpacing": "1.5px", "marginBottom": "8px"}),
                dcc.Graph(id="map-graph", style={"height": "480px", "borderRadius": "4px",
                          "overflow": "hidden", "border": f"1px solid {BORDER}"}),
            ]),
            html.Div(style={"width": "240px", "flexShrink": "0"}, children=[
                html.P("HIGHLIGHTS", style={"color": TEXT_LIGHT, "fontSize": "11px",
                        "letterSpacing": "1.5px", "marginBottom": "8px"}),
                html.Div(id="highlights-panel"),
            ]),
        ]),
        # ── Ask Genie (placeholder) ──
        html.Div(style={"padding": "0 40px 20px"}, children=[
            html.P("ASK GENIE", style={"color": TEXT_LIGHT, "fontSize": "11px",
                    "letterSpacing": "1.5px", "marginBottom": "8px"}),
            html.Div(style={"background": CARD, "border": f"1px solid {BORDER}", "borderRadius": "4px",
                             "padding": "18px 20px"}, children=[
                html.Div(style={"display": "flex", "gap": "10px", "alignItems": "center"}, children=[
                    dcc.Input(
                        id="genie-input",
                        type="text",
                        placeholder="Ask a question about this data in plain English \u2014 e.g. \u201cWhich category has the highest average rating in Austin?\u201d",
                        className="genie-input",
                        style={"flex": "1", "padding": "10px 14px", "borderRadius": "2px",
                               "border": f"1px solid {BORDER}", "fontFamily": SANS,
                               "fontSize": "13px", "color": TEXT_DARK, "background": CARD},
                    ),
                    html.Button("Ask Genie", id="genie-ask-btn", n_clicks=0, style={
                        "background": PRIMARY, "color": "white", "border": "none",
                        "borderRadius": "2px", "padding": "10px 20px", "fontFamily": SANS,
                        "fontSize": "13px", "fontWeight": "600", "cursor": "pointer",
                        "whiteSpace": "nowrap",
                    }),
                ]),
                html.Div(id="genie-output", style={
                    "marginTop": "12px", "fontSize": "12px", "color": TEXT_LIGHT,
                    "fontFamily": SANS, "fontStyle": "italic",
                }),
            ]),
        ]),
        # ── Directory filters + table ──
        html.Div(style={"padding": "0 40px 40px"}, children=[
            html.P("DIRECTORY", style={"color": TEXT_LIGHT, "fontSize": "11px",
                    "letterSpacing": "1.5px", "marginBottom": "12px"}),
            html.Div(style={"display": "flex", "gap": "12px", "flexWrap": "wrap", "marginBottom": "10px"}, children=[
                filter_field("Category", dcc.Dropdown(
                    id="filter-category",
                    options=[{"label": c, "value": c} for c in CATEGORIES],
                    multi=True, placeholder="All")),
                filter_field("Subcategory", dcc.Dropdown(
                    id="filter-subcategory",
                    options=[{"label": s, "value": s} for s in ALL_SUBCATS],
                    multi=True, placeholder="All")),
                filter_field("City", dcc.Dropdown(
                    id="filter-city",
                    options=[{"label": c, "value": c} for c in CITIES],
                    multi=True, placeholder="All")),
                filter_field("State", dcc.Dropdown(
                    id="filter-state",
                    options=[{"label": s, "value": s} for s in STATES],
                    multi=True, placeholder="All")),
            ]),
            html.Div(style={"display": "flex", "gap": "12px", "flexWrap": "wrap", "marginBottom": "16px"}, children=[
                filter_field("Min Rating", dcc.Dropdown(
                    id="filter-rating",
                    options=[{"label": f"{r}+ \u2605", "value": r} for r in [1, 2, 2.5, 3, 3.5, 4, 4.5]],
                    value=1, clearable=False)),
                filter_field("Min Reviews", dcc.Dropdown(
                    id="filter-min-reviews",
                    options=[{"label": f"{r:,}+", "value": r} for r in REVIEW_THRESHOLDS],
                    value=0, clearable=False)),
                filter_field("Min Check-ins", dcc.Dropdown(
                    id="filter-min-checkins",
                    options=[{"label": f"{r:,}+", "value": r} for r in CHECKIN_THRESHOLDS],
                    value=0, clearable=False)),
                filter_field("Search Name", dcc.Input(
                    id="filter-search",
                    type="text",
                    placeholder="Business name contains\u2026",
                    style={"width": "100%", "padding": "8px 10px", "borderRadius": "2px",
                           "border": f"1px solid {BORDER}", "fontFamily": SANS,
                           "fontSize": "13px", "color": TEXT_DARK, "background": CARD,
                           "boxSizing": "border-box"})),
            ]),
            html.Div(id="data-table-container"),
        ]),
    ],
)


# ── Cascading subcategory options based on selected categories ──
@app.callback(
    Output("filter-subcategory", "options"),
    Input("filter-category", "value"),
)
def update_subcategory_options(categories):
    if categories:
        subs = set()
        for lst in df.loc[df["category"].isin(categories), "subcat_list"]:
            subs.update(lst)
        opts = sorted(subs)
    else:
        opts = ALL_SUBCATS
    return [{"label": s, "value": s} for s in opts]


# ── Genie placeholder callback ──
@app.callback(
    Output("genie-output", "children"),
    Input("genie-ask-btn", "n_clicks"),
    State("genie-input", "value"),
    prevent_initial_call=True,
)
def ask_genie(n_clicks, question):
    if not question or not question.strip():
        return "Enter a question above, then click \u201cAsk Genie.\u201d"
    return (
        "Genie integration coming soon \u2014 this will route natural-language questions "
        "like yours to a Databricks Genie space over the genieology.gold.business table "
        "and return an answer here."
    )


@app.callback(
    Output("kpi-row", "children"),
    Output("map-graph", "figure"),
    Output("highlights-panel", "children"),
    Output("data-table-container", "children"),
    Input("filter-category", "value"),
    Input("filter-subcategory", "value"),
    Input("filter-city", "value"),
    Input("filter-state", "value"),
    Input("filter-rating", "value"),
    Input("filter-min-reviews", "value"),
    Input("filter-min-checkins", "value"),
    Input("filter-search", "value"),
)
def update_dashboard(categories, subcategories, cities, states, min_rating,
                      min_reviews, min_checkins, search_text):
    filtered = df.copy()
    if categories:
        filtered = filtered[filtered["category"].isin(categories)]
    if subcategories:
        filtered = filtered[filtered["subcat_list"].apply(
            lambda lst: any(sc in lst for sc in subcategories))]
    if cities:
        filtered = filtered[filtered["city"].isin(cities)]
    if states:
        filtered = filtered[filtered["state"].isin(states)]
    if min_rating and min_rating > 1:
        filtered = filtered[filtered["rating"] >= min_rating]
    if min_reviews:
        filtered = filtered[filtered["review_count"] >= min_reviews]
    if min_checkins:
        filtered = filtered[filtered["checkin_count"] >= min_checkins]
    if search_text and search_text.strip():
        filtered = filtered[filtered["business_name"].str.contains(
            search_text.strip(), case=False, na=False)]

    n = len(filtered)
    avg_r = filtered["rating"].mean() if n else 0
    tot_rev = int(filtered["review_count"].sum())
    tot_chk = int(filtered["checkin_count"].sum())

    kpis = [
        kpi_card("Total Businesses", f"{n:,}", f"across {filtered['city'].nunique()} cities"),
        kpi_card("Avg Rating", f"{avg_r:.2f} \u2605", f"{filtered['category'].nunique()} categories"),
        kpi_card("Total Reviews", f"{tot_rev:,}", f"{tot_rev // max(n, 1)} avg per business"),
        kpi_card("Total Check-ins", f"{tot_chk:,}", f"{tot_chk // max(n, 1)} avg per business"),
    ]

    map_df = filtered.dropna(subset=["latitude", "longitude"]).copy()
    if len(map_df) > 0:
        map_df["_size"] = np.sqrt(map_df["review_count"].fillna(0).clip(lower=1)) + 2
        # Order categories by frequency so the legend lists the most common first,
        # and only the categories actually present are shown (a cleaner key).
        cat_order = (map_df["category"].value_counts().index.tolist())
        fig = px.scatter_mapbox(
            map_df, lat="latitude", lon="longitude",
            color="category", color_discrete_map=CAT_COLORS,
            category_orders={"category": cat_order},
            hover_name="business_name",
            hover_data={"rating": ":.1f", "review_count": ":,", "city": True,
                        "category": True, "latitude": False, "longitude": False, "_size": False},
            size="_size", size_max=14, zoom=9,
            mapbox_style="open-street-map",
        )
        fig.update_layout(
            margin=dict(l=0, r=170, t=0, b=0), paper_bgcolor=CARD,
            legend=dict(
                orientation="v",
                yanchor="top", y=0.98,
                xanchor="left", x=1.01,
                bgcolor="rgba(255,255,255,0.95)",
                bordercolor=BORDER, borderwidth=1,
                font=dict(color=TEXT_DARK, size=10, family="Inter"),
                title=dict(text="Category", font=dict(color=TEXT_MED, size=10, family="Inter")),
                itemsizing="constant",
                itemwidth=30,
                tracegroupgap=2,
            ),
            mapbox_center=dict(lat=map_df["latitude"].mean(), lon=map_df["longitude"].mean()),
        )
    else:
        fig = px.scatter_mapbox(pd.DataFrame({"lat": [39.5], "lon": [-98.35]}),
                                lat="lat", lon="lon", zoom=3, mapbox_style="open-street-map")
        fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor=CARD)

    highlights = []
    if n > 0:
        top = filtered.nlargest(1, "rating").iloc[0]
        most_rev = filtered.nlargest(1, "review_count").iloc[0]
        most_act = filtered.nlargest(1, "checkin_count").iloc[0]
        highlights = [
            highlight_card("Top Rated", str(top["business_name"]),
                           f"\u2605 {top['rating']:.1f} \u00b7 {top['category']}"),
            highlight_card("Most Reviewed", str(most_rev["business_name"]),
                           f"{most_rev['review_count']:,} reviews \u00b7 {most_rev['city']}"),
            highlight_card("Most Active", str(most_act["business_name"]),
                           f"{most_act['checkin_count']:,} check-ins \u00b7 {most_act['city']}"),
        ]

    t = filtered[["business_name", "category", "city", "state", "rating",
                   "review_count", "checkin_count"]].copy()
    t.columns = ["Business", "Category", "City", "State", "Rating", "Reviews", "Check-ins"]
    t = t.sort_values("Reviews", ascending=False).head(200)

    table = dash_table.DataTable(
        data=t.to_dict("records"),
        columns=[{"name": c, "id": c} for c in t.columns],
        page_size=12, sort_action="native", filter_action="native",
        style_header={"backgroundColor": HIGHLIGHT_BG, "color": TEXT_MED, "fontWeight": "600",
                       "fontSize": "11px", "border": f"1px solid {BORDER}",
                       "textTransform": "uppercase", "letterSpacing": "0.5px", "fontFamily": SANS},
        style_cell={"backgroundColor": CARD, "color": TEXT_DARK, "border": f"1px solid {BORDER}",
                     "fontSize": "13px", "padding": "10px 14px", "textAlign": "left",
                     "maxWidth": "200px", "overflow": "hidden", "textOverflow": "ellipsis",
                     "fontFamily": SANS},
        style_data_conditional=[{"if": {"row_index": "odd"}, "backgroundColor": "#FAF7F4"}],
        style_table={"borderRadius": "4px", "overflow": "hidden", "border": f"1px solid {BORDER}"},
    )

    return kpis, fig, highlights, table


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=False)