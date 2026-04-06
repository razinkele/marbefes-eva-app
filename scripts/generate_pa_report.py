"""Generate comprehensive Physical Accounts report for Lithuanian BBT5.

Produces a standalone HTML report with:
- Methodology description
- Input data summary
- Extent Account tables + choropleth map
- Condition Account tables + maps per indicator
- Supply Table with available proxies
- Data gaps analysis
- All maps rendered as embedded folium/plotly
"""
import logging
import os
import sys
from datetime import datetime

import folium
import folium.plugins
import branca.colormap as cm
import geopandas as gpd
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import plotly.io as pio

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

EVA_FINAL = os.path.normpath(
    r"C:\Users\DELL\OneDrive - ku.lt\HORIZON_EUROPE\MARBEFES\EVA_FINAL"
)
CORRECTED = os.path.normpath(
    r"C:\Users\DELL\OneDrive - ku.lt\HORIZON_EUROPE\MARBEFES\EVA_FINAL_corrected"
)
OUTPUT_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "tutorial")
)

HABITAT_COLORS = {
    "Circalittoral sand": "#f4a460",
    "Circalittoral mud": "#8b7355",
    "Circalittoral coarse sediment": "#d2b48c",
    "Infralittoral rock and biogenic reef": "#2e8b57",
    "Infralittoral sand": "#ffe4b5",
    "Circalittoral rock and biogenic reef": "#006400",
}

EVA_COLORS = {
    "Very Low": "#d32f2f",
    "Low": "#ff9800",
    "Medium": "#ffeb3b",
    "High": "#8bc34a",
    "Very High": "#2e7d32",
}


def classify_eva(val):
    if pd.isna(val) or val is None:
        return "No Data"
    if val <= 1: return "Very Low"
    if val <= 2: return "Low"
    if val <= 3: return "Medium"
    if val <= 4: return "High"
    return "Very High"


def load_data():
    """Load all required spatial datasets."""
    logger.info("Loading data...")

    # Habitats
    hab_src = os.path.join(EVA_FINAL, "habitats_EVA", "habitats_final.shp")
    habitats = gpd.read_file(hab_src)
    habitats = habitats[habitats["MSFD_broad"].notna()].copy()
    habitats["area_ha"] = habitats["Shape_Area"] / 10000.0
    logger.info("  Habitats: %d polygons", len(habitats))

    # Hex grid
    grid_src = os.path.join(EVA_FINAL, "EVA Grids", "HexGrid3kmLithuanianBBT.gpkg")
    grid = gpd.read_file(grid_src)
    grid["Subzone_ID"] = [f"R{int(r):03d}_C{int(c):03d}"
                          for r, c in zip(grid["row_index"], grid["col_index"])]
    logger.info("  Grid: %d hexagons", len(grid))

    # Combined EVA (corrected)
    combined_src = os.path.join(CORRECTED, "ALL4EVA_2025_fixed_geometries.gpkg")
    if not os.path.exists(combined_src):
        combined_src = os.path.join(EVA_FINAL, "ALL4EVA_2025_fixed_geometries.gpkg")
    eva = gpd.read_file(combined_src)
    logger.info("  EVA: %d features", len(eva))

    return habitats, grid, eva


def compute_extent(habitats):
    """Compute extent account."""
    extent = habitats.groupby("MSFD_broad").agg(
        polygon_count=("Shape_Area", "count"),
        total_area_ha=("area_ha", "sum"),
    ).reset_index().rename(columns={"MSFD_broad": "Habitat Type"})
    total = extent["total_area_ha"].sum()
    extent["pct_of_total"] = (extent["total_area_ha"] / total * 100).round(1)
    extent["total_area_ha"] = extent["total_area_ha"].round(1)
    extent["total_area_km2"] = (extent["total_area_ha"] / 100).round(1)
    extent = extent.sort_values("total_area_ha", ascending=False).reset_index(drop=True)
    return extent


def compute_condition(habitats, eva):
    """Compute condition per habitat type via spatial join."""
    hab_proj = habitats.to_crs(eva.crs) if habitats.crs != eva.crs else habitats
    hab_c = hab_proj[["MSFD_broad", "geometry"]].copy()
    hab_c["geometry"] = hab_c.geometry.centroid

    score_cols = ["AQ7_HABITATS", "ZooScore", "PhytoScore", "MaxBenthos", "EVA_all_fish"]
    available = [c for c in score_cols if c in eva.columns]

    joined = gpd.sjoin(hab_c, eva[available + ["geometry"]], how="left", predicate="within")

    cond = joined.groupby("MSFD_broad")[available].agg(["mean", "min", "max", "count"]).round(3)
    cond.columns = [f"{c[0]}_{c[1]}" for c in cond.columns]
    cond = cond.reset_index().rename(columns={"MSFD_broad": "Habitat Type"})

    cond_simple = joined.groupby("MSFD_broad")[available].mean().round(3)
    cond_simple = cond_simple.reset_index().rename(columns={"MSFD_broad": "Habitat Type"})

    return cond_simple, cond, joined


def compute_supply(joined_hab_eva):
    """Compute supply proxies from joined habitat-EVA data."""
    j = joined_hab_eva
    available = [c for c in ["EVA_all_fish", "ZooScore", "PhytoScore"] if c in j.columns]
    supply = j.groupby("MSFD_broad")[available].mean().round(3)
    supply = supply.reset_index().rename(columns={"MSFD_broad": "Habitat Type"})
    return supply


def make_habitat_map(habitats):
    """Create folium map of habitat types."""
    gdf = habitats.to_crs(epsg=4326)
    bounds = gdf.total_bounds
    center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]

    m = folium.Map(location=center, zoom_start=9, tiles="cartodbpositron")

    def style_fn(feature):
        hab = feature["properties"].get("MSFD_broad", "")
        return {
            "fillColor": HABITAT_COLORS.get(hab, "#999999"),
            "color": "#333",
            "weight": 0.3,
            "fillOpacity": 0.7,
        }

    folium.GeoJson(
        gdf[["MSFD_broad", "area_ha", "geometry"]].to_json(),
        style_function=style_fn,
        tooltip=folium.GeoJsonTooltip(
            fields=["MSFD_broad", "area_ha"],
            aliases=["Habitat:", "Area (Ha):"],
        ),
    ).add_to(m)

    # Legend
    legend = '<div style="position:fixed;bottom:30px;left:30px;z-index:1000;background:white;padding:12px;border-radius:8px;box-shadow:0 2px 6px rgba(0,0,0,0.3);font-size:12px;">'
    legend += '<strong>Habitat Types</strong><br>'
    for name, color in HABITAT_COLORS.items():
        legend += f'<span style="background:{color};width:14px;height:14px;display:inline-block;margin-right:5px;border-radius:2px;"></span>{name}<br>'
    legend += '</div>'
    m.get_root().html.add_child(folium.Element(legend))
    folium.plugins.Fullscreen().add_to(m)
    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
    return m._repr_html_()


def make_condition_map(habitats, eva, variable, title):
    """Create folium choropleth map for a condition variable."""
    gdf = habitats.to_crs(eva.crs) if habitats.crs != eva.crs else habitats
    gdf_c = gdf[["MSFD_broad", "geometry"]].copy()
    gdf_c["geometry"] = gdf_c.geometry.centroid

    available = [variable] if variable in eva.columns else []
    if not available:
        return f"<p>Variable {variable} not available</p>"

    joined = gpd.sjoin(gdf_c, eva[[variable, "geometry"]], how="left", predicate="within")
    # Assign score back to original polygons
    gdf_plot = habitats.copy()
    gdf_plot[variable] = joined[variable].values[:len(gdf_plot)]
    gdf_plot = gdf_plot.to_crs(epsg=4326)

    bounds = gdf_plot.total_bounds
    center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]
    m = folium.Map(location=center, zoom_start=9, tiles="cartodbpositron")

    vmin = float(gdf_plot[variable].min()) if gdf_plot[variable].notna().any() else 0
    vmax = float(gdf_plot[variable].max()) if gdf_plot[variable].notna().any() else 5
    if vmax == vmin:
        vmax = vmin + 1

    colormap = cm.linear.YlOrRd_09.scale(vmin, vmax)
    colormap.caption = title

    def style_fn(feature):
        val = feature["properties"].get(variable, None)
        if val is None or pd.isna(val):
            return {"fillColor": "#cccccc", "color": "#333", "weight": 0.3, "fillOpacity": 0.5}
        return {
            "fillColor": colormap(val),
            "color": "#333",
            "weight": 0.3,
            "fillOpacity": 0.7,
        }

    gdf_plot[variable] = gdf_plot[variable].round(3)
    folium.GeoJson(
        gdf_plot[["MSFD_broad", variable, "geometry"]].to_json(),
        style_function=style_fn,
        tooltip=folium.GeoJsonTooltip(
            fields=["MSFD_broad", variable],
            aliases=["Habitat:", f"{title}:"],
        ),
    ).add_to(m)
    colormap.add_to(m)
    folium.plugins.Fullscreen().add_to(m)
    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
    return m._repr_html_()


def make_extent_chart(extent):
    """Create plotly bar chart for extent."""
    fig = go.Figure(data=[
        go.Bar(
            x=extent["Habitat Type"],
            y=extent["total_area_km2"],
            marker_color=[HABITAT_COLORS.get(h, "#999") for h in extent["Habitat Type"]],
            text=extent["total_area_km2"].astype(str) + " km2",
            textposition="outside",
        )
    ])
    fig.update_layout(
        title="Ecosystem Extent by Habitat Type",
        xaxis_title="", yaxis_title="Area (km2)",
        height=450, plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(b=150),
        xaxis_tickangle=-30,
    )
    return fig.to_html(include_plotlyjs="cdn", full_html=False)


def make_condition_chart(cond_simple):
    """Create grouped bar chart for condition scores."""
    indicators = {
        "AQ7_HABITATS": "Habitat Diversity",
        "ZooScore": "Zooplankton",
        "PhytoScore": "Phytoplankton",
        "MaxBenthos": "Benthos",
        "EVA_all_fish": "Fish",
    }
    available = {k: v for k, v in indicators.items() if k in cond_simple.columns}

    fig = go.Figure()
    colors = px.colors.qualitative.Set2
    for i, (col, name) in enumerate(available.items()):
        fig.add_trace(go.Bar(
            name=name,
            x=cond_simple["Habitat Type"],
            y=cond_simple[col],
            marker_color=colors[i % len(colors)],
        ))

    fig.update_layout(
        title="Ecosystem Condition by Habitat Type",
        xaxis_title="", yaxis_title="Condition Score (0-5)",
        yaxis=dict(range=[0, 5.5]),
        barmode="group", height=500,
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(b=150),
        xaxis_tickangle=-30,
    )
    return fig.to_html(include_plotlyjs="cdn", full_html=False)


def make_condition_heatmap(cond_simple):
    """Create heatmap of condition scores."""
    indicators = {
        "AQ7_HABITATS": "Habitat Diversity",
        "ZooScore": "Zooplankton",
        "PhytoScore": "Phytoplankton",
        "MaxBenthos": "Benthos",
        "EVA_all_fish": "Fish",
    }
    available = {k: v for k, v in indicators.items() if k in cond_simple.columns}
    cols = list(available.keys())
    labels = list(available.values())

    z = cond_simple[cols].values
    fig = go.Figure(data=go.Heatmap(
        z=z, x=labels, y=cond_simple["Habitat Type"],
        colorscale="RdYlGn", zmin=0, zmax=5,
        text=np.round(z, 2), texttemplate="%{text}",
        textfont={"size": 11},
        colorbar=dict(title="Score (0-5)"),
    ))
    fig.update_layout(
        title="Condition Heatmap: Habitat Type x Indicator",
        height=400, margin=dict(l=250),
    )
    return fig.to_html(include_plotlyjs="cdn", full_html=False)


def df_to_html_table(df, highlight_col=None):
    """Convert DataFrame to styled HTML table."""
    html = '<table style="width:100%;border-collapse:collapse;font-size:14px;margin:1em 0;">'
    html += '<thead><tr style="background:linear-gradient(135deg,#006994,#00b8d4);color:white;">'
    for col in df.columns:
        html += f'<th style="padding:10px 12px;text-align:left;border-bottom:2px solid #ddd;">{col}</th>'
    html += '</tr></thead><tbody>'
    for i, (_, row) in enumerate(df.iterrows()):
        bg = "#f8f9fa" if i % 2 == 0 else "white"
        html += f'<tr style="background:{bg};">'
        for col in df.columns:
            val = row[col]
            style = "padding:8px 12px;border-bottom:1px solid #eee;"
            if highlight_col and col == highlight_col and isinstance(val, str) and val in EVA_COLORS:
                style += f"background:{EVA_COLORS[val]};color:{'white' if val in ['Very Low','Very High'] else 'black'};font-weight:600;"
            html += f'<td style="{style}">{val}</td>'
        html += '</tr>'
    html += '</tbody></table>'
    return html


def generate_report(habitats, grid, eva):
    """Generate the full HTML report."""
    logger.info("Computing accounts...")
    extent = compute_extent(habitats)
    cond_simple, cond_detailed, joined = compute_condition(habitats, eva)
    supply = compute_supply(joined)

    # Add classification columns to condition
    indicator_names = {
        "AQ7_HABITATS": "Habitat Diversity",
        "ZooScore": "Zooplankton",
        "PhytoScore": "Phytoplankton",
        "MaxBenthos": "Benthos",
        "EVA_all_fish": "Fish",
    }
    cond_display = cond_simple.copy()
    for col in list(indicator_names.keys()):
        if col in cond_display.columns:
            cond_display = cond_display.rename(columns={col: indicator_names[col]})
            cond_display[f"{indicator_names[col]} Class"] = cond_display[indicator_names[col]].apply(classify_eva)

    # Supply display
    supply_display = supply.rename(columns={
        "EVA_all_fish": "Fisheries (proxy score)",
        "ZooScore": "Food Web Support (proxy)",
        "PhytoScore": "Primary Production (proxy)",
    })

    logger.info("Generating maps...")
    habitat_map = make_habitat_map(habitats)
    condition_maps = {}
    for var, name in [("AQ7_HABITATS", "Habitat Diversity"),
                      ("MaxBenthos", "Benthos Condition"),
                      ("ZooScore", "Zooplankton Condition"),
                      ("PhytoScore", "Phytoplankton Condition")]:
        condition_maps[name] = make_condition_map(habitats, eva, var, name)

    logger.info("Generating charts...")
    extent_chart = make_extent_chart(extent)
    condition_chart = make_condition_chart(cond_simple)
    condition_heatmap = make_condition_heatmap(cond_simple)

    logger.info("Assembling report...")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Build data sources table outside f-string (avoids dict-in-fstring issue)
    data_sources_table = df_to_html_table(pd.DataFrame({
        "Component": ["Habitats", "Benthos", "Fish", "Zooplankton", "Phytoplankton"],
        "Source": [
            "Lithuanian EPA habitat mapping (HELCOM HUB L3, 2019)",
            "SDM (Siaulys & Bucas, 2012) + video surveys (2021-2023)",
            "ICES BITS trawl surveys (2004-2023) + EPA catch statistics",
            "MRI surveys (1996-2020) + BIO-C3/RETRO projects (2014-2016)",
            "EPA monthly monitoring (2017-2023)",
        ],
        "Type": ["Spatial polygons", "Modelled + observed", "Survey CPUE",
                 "Station abundance", "Station biomass"],
        "Coverage": ["Full EAA", "Baltic Sea coast", "Baltic Sea + Curonian Lagoon",
                     "21 stations", "18 stations"],
    }))

    # Extent table for display (no internal columns)
    extent_display = extent[["Habitat Type", "total_area_ha", "total_area_km2", "pct_of_total"]].copy()
    extent_display.columns = ["Habitat Type", "Area (Ha)", "Area (km2)", "% of Total"]

    # Data gaps table
    gaps = pd.DataFrame({
        "Ecosystem Service": ["Fisheries", "Food Web Support", "Primary Production",
                              "Carbon Sequestration", "Coastal Protection",
                              "Tourism & Recreation", "Nutrient Cycling"],
        "Data Status": ["Proxy available", "Proxy available", "Proxy available",
                       "NOT AVAILABLE", "NOT AVAILABLE", "NOT AVAILABLE", "NOT AVAILABLE"],
        "Units Needed": ["tonnes/yr", "mg C/m3", "g C/m2/yr",
                        "t C/ha/yr", "wave attenuation index",
                        "visits/yr", "kg N-P/ha/yr"],
        "Potential Source": [
            "Lithuanian EPA fisheries statistics",
            "HELCOM COMBINE monitoring",
            "Copernicus Marine satellite remote sensing",
            "Sediment core studies, IPCC factors",
            "SHYFEM hydrodynamic model",
            "Tourism statistics, visitor surveys",
            "HELCOM PLC, biogeochemical models",
        ],
    })

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Physical Accounts — Lithuanian BBT5</title>
<style>
  body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; background: #f5f7fa; color: #333; }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
  .header {{ background: linear-gradient(135deg, #006994, #00b8d4); color: white; padding: 40px; border-radius: 12px; margin-bottom: 30px; }}
  .header h1 {{ margin: 0; font-size: 2.2em; font-weight: 700; }}
  .header p {{ margin: 10px 0 0; font-size: 1.1em; opacity: 0.9; }}
  .section {{ background: white; border-radius: 12px; padding: 30px; margin-bottom: 25px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
  .section h2 {{ color: #006994; font-size: 1.6em; margin-top: 0; border-bottom: 3px solid #00b8d4; padding-bottom: 10px; }}
  .section h3 {{ color: #006994; font-size: 1.2em; margin-top: 25px; }}
  .map-container {{ border-radius: 8px; overflow: hidden; border: 1px solid #ddd; margin: 15px 0; }}
  .chart-container {{ margin: 15px 0; }}
  .info-box {{ background: linear-gradient(135deg, #e3f2fd, #bbdefb); border-left: 4px solid #006994; padding: 15px 20px; border-radius: 8px; margin: 15px 0; }}
  .warning-box {{ background: linear-gradient(135deg, #fff3e0, #ffe0b2); border-left: 4px solid #ff9800; padding: 15px 20px; border-radius: 8px; margin: 15px 0; }}
  .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
  .footer {{ text-align: center; color: #6c757d; padding: 20px; font-size: 0.9em; }}
  @media (max-width: 768px) {{ .two-col {{ grid-template-columns: 1fr; }} }}
  @media print {{ .map-container {{ page-break-inside: avoid; }} }}
</style>
</head>
<body>
<div class="container">

<div class="header">
  <h1>SEEA EA Physical Accounts</h1>
  <p>Lithuanian BBT5 — Curonian Lagoon and Baltic Sea Coast</p>
  <p style="font-size:0.9em; opacity:0.8;">MARBEFES WP4 | Generated: {now}</p>
</div>

<!-- 1. INTRODUCTION -->
<div class="section">
  <h2>1. Introduction</h2>
  <p>This report presents the <strong>Physical Natural Capital Accounts</strong> for the Lithuanian
  Broad Biotope Type 5 (BBT5), covering the Curonian Lagoon and Baltic Sea coast. The accounts
  follow the <strong>UN System of Environmental-Economic Accounting — Ecosystem Accounting</strong>
  (SEEA EA) framework as adapted for marine environments under the MARBEFES project.</p>

  <p>Three account components are presented:</p>
  <ul>
    <li><strong>Extent Account</strong> — area (hectares) per benthic habitat type</li>
    <li><strong>Condition Account</strong> — ecological condition per habitat type using EVA scores</li>
    <li><strong>Supply Table</strong> — ecosystem service provision proxies where data permits</li>
  </ul>

  <div class="info-box">
    <strong>Ecosystem Accounting Area (EAA):</strong> Lithuanian Exclusive Economic Zone,
    Territorial Sea, and Curonian Lagoon<br>
    <strong>Accounting period:</strong> 2017–2023 (monitoring data period)<br>
    <strong>Spatial resolution:</strong> 310 habitat polygons (HELCOM HUB Level 3 / EUNIS Level 2)
  </div>
</div>

<!-- 2. INPUT DATA -->
<div class="section">
  <h2>2. Input Data and Methodology</h2>

  <h3>2.1 Habitat Classification</h3>
  <p>Benthic habitats were classified according to HELCOM HUB Level 3 / EUNIS Level 2,
  derived from the Lithuanian Environmental Protection Agency's 2019 habitat mapping.
  Six broad habitat types were identified in the Baltic Sea portion of the EAA.</p>

  <h3>2.2 Ecological Value Assessment (EVA)</h3>
  <p>Condition scores are derived from the MARBEFES EVA framework (Franco &amp; Amorim, 2025),
  which assesses 15 Assessment Questions (AQ1–AQ15) across 5 ecosystem components:
  zoobenthos, fish, benthic habitats, zooplankton, and phytoplankton. Scores range from
  0 (Very Low) to 5 (Very High). The EVA scores were computed using the MARBEFES EVA
  application v3.3 with sentinel-corrected data (September 2025).</p>

  <h3>2.3 Data Sources</h3>
  {data_sources_table}

  <h3>2.4 Methodology</h3>
  <div class="info-box">
    <strong>Extent:</strong> Computed from polygon areas (Shape_Area in m2, converted to Ha)
    grouped by MSFD broad habitat type.<br>
    <strong>Condition:</strong> EVA scores spatially joined to habitat polygons via centroid-in-hexagon
    matching. Mean score per indicator per habitat type.<br>
    <strong>Supply:</strong> Fish CPUE and plankton scores used as ecosystem service proxies
    (relative indices, not physical units).
  </div>
</div>

<!-- 3. EXTENT ACCOUNT -->
<div class="section">
  <h2>3. Extent Account</h2>
  <p>The total marine habitat extent within the Lithuanian EAA is <strong>{extent_display['Area (Ha)'].iloc[-1] if 'TOTAL' in extent_display['Habitat Type'].values else extent_display['Area (Ha)'].sum():,.0f} hectares</strong>
  ({extent_display['Area (km2)'].iloc[-1] if 'TOTAL' in extent_display['Habitat Type'].values else extent_display['Area (km2)'].sum():,.0f} km2).
  Sandy substrates dominate, covering nearly 43% of the seabed.</p>

  <h3>3.1 Extent Table</h3>
  {df_to_html_table(extent_display)}

  <h3>3.2 Extent Chart</h3>
  <div class="chart-container">
    {extent_chart}
  </div>

  <h3>3.3 Habitat Distribution Map</h3>
  <div class="map-container" style="height:600px;">
    {habitat_map}
  </div>
</div>

<!-- 4. CONDITION ACCOUNT -->
<div class="section">
  <h2>4. Condition Account</h2>
  <p>Ecological condition is assessed using EVA scores (0–5 scale) across five indicators.
  Each habitat polygon is assigned the EVA score of the hexagonal grid cell containing its centroid.</p>

  <div class="warning-box">
    <strong>Note on confidence:</strong> All condition scores have <em>Low</em> confidence
    (each EC answered only 1–4 of 7–8 possible Assessment Questions). Scores should be
    interpreted as preliminary indicators, not definitive assessments.
  </div>

  <h3>4.1 Condition Summary Table</h3>
  {df_to_html_table(cond_display)}

  <h3>4.2 Condition Comparison Chart</h3>
  <div class="chart-container">
    {condition_chart}
  </div>

  <h3>4.3 Condition Heatmap</h3>
  <div class="chart-container">
    {condition_heatmap}
  </div>

  <h3>4.4 Condition Maps</h3>
"""
    for name, map_html in condition_maps.items():
        html += f"""
  <h4>{name}</h4>
  <div class="map-container" style="height:500px;">
    {map_html}
  </div>
"""

    html += f"""
</div>

<!-- 5. SUPPLY TABLE -->
<div class="section">
  <h2>5. Ecosystem Service Supply Table</h2>
  <p>The supply table presents available proxy indicators for ecosystem services per habitat type.
  Full SEEA EA compliance requires physical units (tonnes, m3, etc.); the values below are
  relative EVA scores (0–5) serving as provisional indicators.</p>

  <h3>5.1 Available Service Proxies</h3>
  {df_to_html_table(supply_display)}

  <div class="warning-box">
    <strong>Interpretation:</strong> Fish scores represent relative CPUE (Catch Per Unit Effort)
    across habitats, not absolute catch. NaN indicates no fish survey data for that habitat type
    (infralittoral and coarse sediment areas were not covered by bottom trawl surveys).
  </div>

  <h3>5.2 Data Gaps and Recommendations</h3>
  <p>The following ecosystem services require additional data for full physical accounting:</p>
  {df_to_html_table(gaps)}
</div>

<!-- 6. SUMMARY -->
<div class="section">
  <h2>6. Summary and Conclusions</h2>

  <h3>Key Findings</h3>
  <ul>
    <li><strong>Extent:</strong> Sandy substrates (circalittoral + infralittoral sand) dominate
    at 43% of total area. Rock and biogenic reef habitats cover only 9.6% but are ecologically
    the most diverse.</li>
    <li><strong>Condition:</strong> Zooplankton scores are Very High across all habitats (3.5–4.3),
    dominating the overall condition assessment. Habitat diversity is highest in infralittoral
    rock/reef areas (Medium, 2.3) and lowest in circalittoral mud (Very Low, 0.6).</li>
    <li><strong>Supply:</strong> Fish provisioning data is available for only 3 of 6 habitat types
    (circalittoral only). Carbon sequestration, tourism, and nutrient cycling data are entirely absent.</li>
  </ul>

  <h3>Limitations</h3>
  <ul>
    <li>Condition scores have Low confidence due to limited AQ coverage per ecosystem component</li>
    <li>No temporal baseline exists — this is a single-period snapshot, not a trend analysis</li>
    <li>Curonian Lagoon habitats are not included (different classification system)</li>
    <li>Supply table uses proxy scores, not physical units required by SEEA EA</li>
  </ul>

  <h3>Next Steps</h3>
  <ol>
    <li>Acquire fisheries catch data in physical units (tonnes/year) per habitat type</li>
    <li>Integrate satellite-derived primary production estimates (Copernicus Marine)</li>
    <li>Establish temporal baselines for condition trend monitoring</li>
    <li>Extend to Curonian Lagoon habitats using the EUNIS Level 2 classification</li>
    <li>Connect with ARIES platform for automated natural capital accounting</li>
  </ol>
</div>

<!-- REFERENCES -->
<div class="section">
  <h2>References</h2>
  <ul>
    <li>Franco A. &amp; Amorim E. (2025) <em>Ecological Value Assessment (EVA) — Guidance
    including FAQs.</em> MARBEFES WP4.1.</li>
    <li>Razinkovas-Baziukas A. et al. (2025) <em>Curonian Lagoon and Baltic Sea coast
    Lithuanian BBT EVA report.</em> Klaipeda University / MARBEFES.</li>
    <li>UN (2021) <em>System of Environmental-Economic Accounting — Ecosystem Accounting
    (SEEA EA).</em> United Nations.</li>
    <li>Luisetti T. &amp; Burdon D. (2023) <em>Draft Guidance on Socio-Economic Frameworks
    and Methods — Physical Accounts Section.</em> MARBEFES Deliverable D4.2.</li>
  </ul>
</div>

<div class="footer">
  MARBEFES — Marine Biodiversity and Ecosystem Functioning | EU Horizon Europe<br>
  Report generated by MARBEFES EVA v3.3.1 | {now}
</div>

</div>
</body>
</html>"""

    output_path = os.path.join(OUTPUT_DIR, "PhysicalAccounts_Report_LithuanianBBT5.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info("Report written to %s", output_path)
    return output_path


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    habitats, grid, eva = load_data()
    path = generate_report(habitats, grid, eva)
    logger.info("Done. Open in browser: %s", path)


if __name__ == "__main__":
    main()
