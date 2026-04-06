"""Map creation functions for EVA visualisation (extracted from app.py)."""

import pandas as pd
import folium
import folium.plugins
import branca.colormap as cm
from html import escape as html_escape
from eva_config import EVA_5CLASS_BINS, EVA_5CLASS_COLORS, EVA_5CLASS_LABELS, BASEMAP_TILES
import pa_config


def _build_legend_html(title, items):
    """Build an HTML legend string with XSS-safe escaping.

    Args:
        title: Legend title text.
        items: list of (color, label) tuples.

    Returns:
        HTML string for a fixed-position legend overlay.
    """
    safe_title = html_escape(str(title))
    html = (
        '<div style="position: fixed; bottom: 30px; left: 30px; z-index: 1000; '
        'background: white; padding: 12px 16px; border-radius: 8px; '
        'box-shadow: 0 2px 6px rgba(0,0,0,0.3); font-size: 13px;">'
        f'<p style="margin: 0 0 8px; font-weight: 700;">{safe_title}</p>'
    )
    for color, label in items:
        safe_label = html_escape(str(label))
        safe_color = html_escape(str(color))
        html += (
            f'<p style="margin: 2px 0;">'
            f'<span style="background:{safe_color}; width:18px; height:14px; '
            f'display:inline-block; margin-right:6px; border-radius:2px;"></span>'
            f'{safe_label}</p>'
        )
    html += '</div>'
    return html


def auto_zoom_level(bounds):
    """Calculate appropriate zoom level from bounding box [minx, miny, maxx, maxy]."""
    lat_diff = bounds[3] - bounds[1]
    lon_diff = bounds[2] - bounds[0]
    max_diff = max(lat_diff, lon_diff)
    if max_diff > 10:
        return 5
    elif max_diff > 5:
        return 7
    elif max_diff > 1:
        return 9
    elif max_diff > 0.1:
        return 12
    else:
        return 14


def create_grid_only_map(gdf, basemap_name="CartoDB Positron"):
    """Render the spatial grid with no EVA data — shown before CSV is uploaded.

    Args:
        gdf: GeoDataFrame with 'Subzone ID' and geometry columns.
        basemap_name: string key for BASEMAP_TILES lookup.

    Returns:
        Folium map HTML string.
    """
    bounds = gdf.total_bounds
    center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]
    zoom = auto_zoom_level(bounds)
    tiles = BASEMAP_TILES.get(basemap_name, "cartodbpositron")
    m = folium.Map(location=center, zoom_start=zoom, tiles=tiles)

    grid_layer = folium.FeatureGroup(name="Grid", show=True)
    folium.GeoJson(
        gdf.to_json(),
        style_function=lambda _: {
            "fillColor": "#4da6ff",
            "color": "#006994",
            "weight": 1,
            "fillOpacity": 0.15,
        },
        tooltip=folium.GeoJsonTooltip(fields=["Subzone ID"], aliases=["Subzone:"]),
    ).add_to(grid_layer)
    grid_layer.add_to(m)

    legend_html = _build_legend_html("Grid", [("#4da6ff", f"{len(gdf)} subzones — upload CSV to score")])
    m.get_root().html.add_child(folium.Element(legend_html))

    folium.plugins.Fullscreen(position='topright').add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
    return m._repr_html_()


def create_ev_map(map_gdf, variable, color_scheme_name, classification, basemap_name, opacity, eunis_gdf=None):
    """Create a folium choropleth map from a GeoDataFrame with EVA results."""
    bounds = map_gdf.total_bounds
    center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]
    zoom = auto_zoom_level(bounds)

    tiles = BASEMAP_TILES.get(basemap_name, "cartodbpositron")
    m = folium.Map(location=center, zoom_start=zoom, tiles=tiles)

    # Optional EUNIS habitat base layer
    if eunis_gdf is not None and not eunis_gdf.empty:
        eunis_colors = {
            "A5.26 or A5.35 or A5.36": "#8b7355",
            "A5.23": "#ffe4b5", "A5.25": "#f4a460",
            "A5.14": "#d2b48c", "A4.4": "#2e8b57",
            "A3.4": "#006400", "A5.24 or A5.33 or A5.34": "#cd853f",
            "A5.27 or A5.37": "#a0522d", "A5.13": "#deb887",
        }
        eunis_layer = folium.FeatureGroup(name="EUNIS Habitats", show=True)
        eunis_plot = eunis_gdf.to_crs(epsg=4326) if eunis_gdf.crs and eunis_gdf.crs.to_epsg() != 4326 else eunis_gdf

        def eunis_style(feature):
            code = feature["properties"].get("dominant_EUNIS", "")
            return {
                "fillColor": eunis_colors.get(code, "#999"),
                "color": "#666", "weight": 0.3,
                "fillOpacity": 0.3,
            }

        eunis_plot_data = eunis_plot[["Subzone_ID", "dominant_EUNIS", "dominant_EUNIS_name", "geometry"]].copy()
        folium.GeoJson(
            eunis_plot_data.to_json(),
            style_function=eunis_style,
            tooltip=folium.GeoJsonTooltip(
                fields=["dominant_EUNIS", "dominant_EUNIS_name"],
                aliases=["EUNIS:", "Habitat:"],
            ),
            name="EUNIS Habitats",
        ).add_to(eunis_layer)
        eunis_layer.add_to(m)

    # Prepare variable data
    map_gdf = map_gdf.copy()
    if variable in map_gdf.columns:
        map_gdf[variable] = pd.to_numeric(map_gdf[variable], errors='coerce').fillna(0)
    else:
        map_gdf[variable] = 0

    vmin = float(map_gdf[variable].min())
    vmax = float(map_gdf[variable].max())
    if vmax == vmin:
        vmax = vmin + 1

    use_5class = classification.startswith("EVA")

    if use_5class:
        def style_fn(feature):
            val = feature['properties'].get(variable, 0)
            if val is None:
                val = 0
            color = EVA_5CLASS_COLORS[-1]
            for i in range(len(EVA_5CLASS_BINS) - 1):
                if val <= EVA_5CLASS_BINS[i + 1]:
                    color = EVA_5CLASS_COLORS[i]
                    break
            return {
                'fillColor': color,
                'color': '#333333',
                'weight': 0.5,
                'fillOpacity': opacity
            }
    else:
        color_schemes = {
            "YlOrRd": cm.linear.YlOrRd_09,
            "Viridis": cm.linear.viridis,
            "Blues": cm.linear.Blues_09,
            "RdYlGn": cm.linear.RdYlGn_11,
            "Plasma": cm.linear.plasma,
        }
        colormap = color_schemes.get(color_scheme_name, cm.linear.YlOrRd_09)
        colormap = colormap.scale(vmin, vmax)
        colormap.caption = variable

        def style_fn(feature):
            val = feature['properties'].get(variable, 0)
            if val is None:
                val = 0
            return {
                'fillColor': colormap(val),
                'color': '#333333',
                'weight': 0.5,
                'fillOpacity': opacity
            }

    # Build tooltip fields
    tooltip_fields = ['Subzone ID', variable]
    tooltip_aliases = ['Subzone:', f'{variable}:']
    if variable != 'EV' and 'EV' in map_gdf.columns:
        tooltip_fields.append('EV')
        tooltip_aliases.append('EV:')

    # Round numeric columns for tooltips
    for col in tooltip_fields:
        if col in map_gdf.columns and col != 'Subzone ID':
            map_gdf[col] = map_gdf[col].round(3)

    eva_layer = folium.FeatureGroup(name=f"EVA: {variable}", show=True)
    folium.GeoJson(
        map_gdf.to_json(),
        style_function=style_fn,
        tooltip=folium.GeoJsonTooltip(
            fields=tooltip_fields,
            aliases=tooltip_aliases,
            sticky=True,
            style="font-size: 13px; padding: 8px;"
        )
    ).add_to(eva_layer)
    eva_layer.add_to(m)

    # Add legend
    if use_5class:
        items = list(zip(EVA_5CLASS_COLORS, EVA_5CLASS_LABELS))
        legend_html = _build_legend_html(variable, items)
        m.get_root().html.add_child(folium.Element(legend_html))
    else:
        colormap.add_to(m)

    folium.plugins.Fullscreen(position='topright').add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])

    return m._repr_html_()


def create_habitat_map(gdf, assignments, basemap_name, opacity):
    """Create habitat type map from PA assignments.

    Args:
        gdf: GeoDataFrame with geometry and 'Subzone ID' column.
        assignments: dict mapping Subzone ID -> habitat_code.
        basemap_name: string key for BASEMAP_TILES lookup.
        opacity: float fill opacity for polygons.

    Returns:
        Folium map HTML string.
    """
    map_gdf = gdf.merge(
        pd.DataFrame(list(assignments.items()), columns=["Subzone ID", "habitat_code"]),
        on="Subzone ID", how="inner"
    )
    map_gdf["habitat_name"] = map_gdf["habitat_code"].map(lambda c: pa_config.EUNIS_LOOKUP.get(c, c))

    unique_habitats = map_gdf["habitat_code"].unique().tolist()
    color_map = {h: pa_config.HABITAT_PALETTE[i % len(pa_config.HABITAT_PALETTE)]
                for i, h in enumerate(unique_habitats)}

    bounds = map_gdf.total_bounds
    center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]
    zoom = auto_zoom_level(bounds)
    tiles = BASEMAP_TILES.get(basemap_name, "cartodbpositron")
    m = folium.Map(location=center, zoom_start=zoom, tiles=tiles)

    def habitat_style(feature):
        code = feature["properties"].get("habitat_code", "")
        return {
            "fillColor": color_map.get(code, "#999999"),
            "color": "#333333",
            "weight": 0.5,
            "fillOpacity": opacity,
        }

    folium.GeoJson(
        map_gdf.to_json(),
        style_function=habitat_style,
        tooltip=folium.GeoJsonTooltip(
            fields=["Subzone ID", "habitat_code", "habitat_name"],
            aliases=["Subzone:", "EUNIS Code:", "Habitat:"],
        )
    ).add_to(m)

    items = [(color_map[code], f"{code} - {pa_config.EUNIS_LOOKUP.get(code, code)}")
             for code in unique_habitats]
    legend_html = _build_legend_html("Habitat Types", items)
    m.get_root().html.add_child(folium.Element(legend_html))

    folium.plugins.Fullscreen(position='topright').add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
    return m._repr_html_()
