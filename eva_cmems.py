"""
eva_cmems.py — Copernicus Marine Service covariate extraction for SDM.

Fetches climatological marine environmental variables for each hexagon centroid
using the copernicusmarine Python package with:
  - GLORYS12V1 global ocean physics reanalysis (GLOBAL_MULTIYEAR_PHY_001_030)
    → monthly climatology dataset (12-month means, 1993-2020 baseline)
  - PISCES global ocean biogeochemistry hindcast (GLOBAL_MULTIYEAR_BGC_001_029)
    → monthly reanalysis; subset to a user-defined year range

Credentials: free registration at https://marine.copernicus.eu
Set COPERNICUSMARINE_SERVICE_USERNAME and COPERNICUSMARINE_SERVICE_PASSWORD
environment variables, or pass username/password explicitly.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import geopandas as gpd
import numpy as np

logger = logging.getLogger(__name__)

# ── Dataset IDs ───────────────────────────────────────────────────────────────
_PHY_CLIM = "cmems_mod_glo_phy_my_0.083deg-climatology_P1M-m"
_BGC_MONTHLY = "cmems_mod_glo_bgc_my_0.25deg_P1M-m"

# ── Layer catalogue ───────────────────────────────────────────────────────────
# depth_dim: True  → variable has (time, depth, lat, lon); extract surface
# depth_dim: False → 2D variable (time, lat, lon); use directly
# combine: "speed" → sqrt(u² + v²) from variable list; None → single variable
CMEMS_LAYERS: dict[str, dict] = {
    "sst": {
        "dataset_id": _PHY_CLIM,
        "variable":   "thetao",
        "depth_dim":  True,
        "combine":    None,
        "col":        "sst_mean_c",
        "label":      "🌡️ Sea Surface Temperature (SST)",
        "unit":       "°C",
        "description": "Climatological mean SST from GLORYS12V1 reanalysis",
    },
    "bottom_temp": {
        "dataset_id": _PHY_CLIM,
        "variable":   "bottomT",
        "depth_dim":  False,
        "combine":    None,
        "col":        "bottom_temp_c",
        "label":      "🌡️ Bottom Temperature",
        "unit":       "°C",
        "description": "Climatological mean sea-floor temperature from GLORYS12V1",
    },
    "salinity": {
        "dataset_id": _PHY_CLIM,
        "variable":   "so",
        "depth_dim":  True,
        "combine":    None,
        "col":        "sss_mean",
        "label":      "🧂 Sea Surface Salinity (SSS)",
        "unit":       "PSU",
        "description": "Climatological mean surface salinity from GLORYS12V1",
    },
    "mld": {
        "dataset_id": _PHY_CLIM,
        "variable":   "mlotst",
        "depth_dim":  False,
        "combine":    None,
        "col":        "mld_mean_m",
        "label":      "📏 Mixed Layer Depth (MLD)",
        "unit":       "m",
        "description": "Climatological mean mixed layer thickness from GLORYS12V1",
    },
    "current_speed": {
        "dataset_id": _PHY_CLIM,
        "variable":   ["uo", "vo"],
        "depth_dim":  True,
        "combine":    "speed",
        "col":        "current_speed_ms",
        "label":      "🌊 Surface Current Speed",
        "unit":       "m/s",
        "description": "Climatological mean surface current speed √(u²+v²) from GLORYS12V1",
    },
    "chlorophyll": {
        "dataset_id": _BGC_MONTHLY,
        "variable":   "chl",
        "depth_dim":  True,
        "combine":    None,
        "col":        "chl_mean",
        "label":      "🟢 Chlorophyll-a (Chl-a)",
        "unit":       "mg/m³",
        "description": "Annual mean surface Chl-a from PISCES biogeochemistry model",
    },
    "oxygen": {
        "dataset_id": _BGC_MONTHLY,
        "variable":   "o2",
        "depth_dim":  True,
        "combine":    None,
        "col":        "o2_mean_mmol",
        "label":      "💧 Dissolved Oxygen (O₂)",
        "unit":       "mmol/m³",
        "description": "Annual mean surface dissolved oxygen from PISCES",
    },
    "nitrate": {
        "dataset_id": _BGC_MONTHLY,
        "variable":   "no3",
        "depth_dim":  True,
        "combine":    None,
        "col":        "no3_mean_mmol",
        "label":      "⚗️ Nitrate (NO₃)",
        "unit":       "mmol/m³",
        "description": "Annual mean surface nitrate from PISCES",
    },
    "ph": {
        "dataset_id": _BGC_MONTHLY,
        "variable":   "ph",
        "depth_dim":  True,
        "combine":    None,
        "col":        "ph_mean",
        "label":      "🧪 Sea Water pH",
        "unit":       "pH units",
        "description": "Annual mean surface pH from PISCES (ocean acidification indicator)",
    },
    "npp": {
        "dataset_id": _BGC_MONTHLY,
        "variable":   "nppv",
        "depth_dim":  True,
        "combine":    None,
        "col":        "npp_mean",
        "label":      "🌱 Net Primary Production (NPP)",
        "unit":       "mg C/m³/d",
        "description": "Annual mean surface net primary production from PISCES",
    },
}

# Col → display label for map layer selector
CMEMS_MAP_COLS: dict[str, str] = {
    cfg["col"]: f"{cfg['label']} [{cfg['unit']}]"
    for cfg in CMEMS_LAYERS.values()
}


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_cmems_covariates(
    grid_gdf: gpd.GeoDataFrame,
    layers: list[str],
    username: str = "",
    password: str = "",
    bgc_start_year: int = 2016,
    bgc_end_year: int = 2020,
) -> gpd.GeoDataFrame:
    """Fetch Copernicus Marine climatological covariates for each hexagon.

    For PHY variables the 12-month climatology product is used (all months
    averaged).  For BGC variables, monthly data from *bgc_start_year* to
    *bgc_end_year* is downloaded and averaged.

    Returns a copy of *grid_gdf* with one new numeric column per layer.
    Hexagons with no data receive NaN.

    Parameters
    ----------
    grid_gdf:
        Hexagon grid GeoDataFrame (any CRS; internally reprojected to WGS-84).
    layers:
        List of keys from :data:`CMEMS_LAYERS` to fetch.
    username / password:
        Copernicus Marine credentials.  Falls back to environment variables
        ``COPERNICUSMARINE_SERVICE_USERNAME`` / ``…_PASSWORD`` if empty.
    bgc_start_year / bgc_end_year:
        Year range for BGC monthly averaging (default 2016–2020).
    """
    try:
        import copernicusmarine  # noqa: F401
        import xarray as xr
    except ImportError as exc:
        raise ImportError(
            "copernicusmarine and xarray are required. "
            "Install: pip install copernicusmarine xarray"
        ) from exc

    if not layers:
        raise ValueError("No CMEMS layers specified.")

    # Resolve credentials
    username, password = _resolve_credentials(username, password)

    # Bounding box with buffer (1° margin)
    gdf_wgs = grid_gdf.to_crs(4326) if grid_gdf.crs and grid_gdf.crs.to_epsg() != 4326 else grid_gdf
    bounds = gdf_wgs.total_bounds  # [minx, miny, maxx, maxy]
    buf = 1.0
    lon_min = float(bounds[0]) - buf
    lat_min = float(bounds[1]) - buf
    lon_max = float(bounds[2]) + buf
    lat_max = float(bounds[3]) + buf

    # Compute centroids on a projected CRS to avoid geographic CRS warning
    centroids = gdf_wgs.to_crs(3857).geometry.centroid.to_crs(4326)
    lons = centroids.x.values
    lats = centroids.y.values

    result = grid_gdf.copy()

    # Group layers by dataset so we download each dataset only once
    dataset_groups: dict[str, list[str]] = {}
    for lk in layers:
        if lk not in CMEMS_LAYERS:
            logger.warning("Unknown CMEMS layer '%s' — skipped.", lk)
            continue
        ds_id = CMEMS_LAYERS[lk]["dataset_id"]
        dataset_groups.setdefault(ds_id, []).append(lk)

    for dataset_id, layer_keys in dataset_groups.items():
        all_vars: list[str] = []
        for lk in layer_keys:
            v = CMEMS_LAYERS[lk]["variable"]
            if isinstance(v, list):
                all_vars.extend(v)
            else:
                all_vars.append(v)
        all_vars = list(dict.fromkeys(all_vars))  # unique, preserve order

        # Temporal range differs per dataset type
        is_clim = "climatology" in dataset_id
        t_kwargs: dict = {}
        if not is_clim:
            t_kwargs = {
                "start_datetime": f"{bgc_start_year}-01-01",
                "end_datetime":   f"{bgc_end_year}-12-31",
            }

        logger.info(
            "Opening CMEMS %s — vars=%s bbox=[%.2f,%.2f,%.2f,%.2f]%s",
            dataset_id, all_vars, lon_min, lat_min, lon_max, lat_max,
            f" years={bgc_start_year}-{bgc_end_year}" if not is_clim else " (climatology)",
        )

        try:
            import copernicusmarine
            ds = copernicusmarine.open_dataset(
                dataset_id=dataset_id,
                variables=all_vars,
                minimum_longitude=lon_min,
                maximum_longitude=lon_max,
                minimum_latitude=lat_min,
                maximum_latitude=lat_max,
                minimum_depth=0.49,  # first available depth level (~0.49–0.51m in PHY/BGC)
                maximum_depth=2.0,   # surface only; avoids full water-column download
                coordinates_selection_method="nearest",  # snap to available depth; no boundary warning
                username=username,
                password=password,
                **t_kwargs,
            )
        except Exception as exc:
            logger.error("Failed to open CMEMS dataset %s: %s", dataset_id, exc)
            for lk in layer_keys:
                result[CMEMS_LAYERS[lk]["col"]] = np.nan
            continue

        # Time-mean over all loaded time steps
        time_dim = next((d for d in ds.dims if "time" in d.lower()), None)
        ds_mean = ds.mean(dim=time_dim) if time_dim else ds

        for lk in layer_keys:
            cfg = CMEMS_LAYERS[lk]
            col = cfg["col"]
            variable = cfg["variable"]
            depth_dim = cfg["depth_dim"]
            combine = cfg["combine"]

            try:
                if combine == "speed":
                    u = _to_surface(ds_mean[variable[0]], depth_dim)
                    v = _to_surface(ds_mean[variable[1]], depth_dim)
                    u_vals = _sample_at(u, lons, lats)
                    v_vals = _sample_at(v, lons, lats)
                    values = np.sqrt(u_vals ** 2 + v_vals ** 2)
                else:
                    da = _to_surface(ds_mean[variable], depth_dim)
                    values = _sample_at(da, lons, lats)

                result[col] = values
                n_valid = int(np.sum(~np.isnan(values)))
                logger.info(
                    "CMEMS '%s': %d/%d hexagons with data",
                    lk, n_valid, len(lons),
                )
            except Exception as exc:
                logger.warning("Failed to extract CMEMS layer '%s': %s", lk, exc)
                result[col] = np.nan

        try:
            ds.close()
        except Exception:
            pass

    return result


def get_credentials_from_env() -> tuple[str, str]:
    """Return (username, password) from environment variables, or ('', '')."""
    return (
        os.environ.get("COPERNICUSMARINE_SERVICE_USERNAME", ""),
        os.environ.get("COPERNICUSMARINE_SERVICE_PASSWORD", ""),
    )


# ── Internal helpers ──────────────────────────────────────────────────────────

def _resolve_credentials(username: str, password: str) -> tuple[str, str]:
    if not username or not password:
        env_u, env_p = get_credentials_from_env()
        username = username or env_u
        password = password or env_p
    if not username or not password:
        raise ValueError(
            "Copernicus Marine credentials required. Provide username/password "
            "or set COPERNICUSMARINE_SERVICE_USERNAME / "
            "COPERNICUSMARINE_SERVICE_PASSWORD environment variables. "
            "Register free at https://marine.copernicus.eu"
        )
    return username, password


def _to_surface(da, depth_dim: bool):
    """Return surface slice of DataArray (isel depth=0) if it has a depth dim."""
    if not depth_dim:
        return da
    for dim in ("depth", "deptht", "lev", "z", "elevation"):
        if dim in da.dims:
            return da.isel({dim: 0})
    return da


def _sample_at(da, lons: np.ndarray, lats: np.ndarray) -> np.ndarray:
    """Nearest-neighbour sample of 2-D DataArray at given lon/lat points."""
    import xarray as xr

    lon_coord = _find_coord(da, ["longitude", "lon", "x"])
    lat_coord = _find_coord(da, ["latitude", "lat", "y"])

    pts_lon = xr.DataArray(lons, dims="points")
    pts_lat = xr.DataArray(lats, dims="points")

    sampled = da.interp(
        {lon_coord: pts_lon, lat_coord: pts_lat},
        method="nearest",
    )
    return np.asarray(sampled.values, dtype=float)


def _find_coord(da, candidates: list[str]) -> str:
    for c in candidates:
        if c in da.coords or c in da.dims:
            return c
    raise KeyError(
        f"No coordinate matching {candidates} found in {list(da.coords)}"
    )
