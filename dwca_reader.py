"""
Darwin Core Archive (DwC-A) Reader for EVA

Parses DwC-A zip files containing Event core + Occurrence extension
and converts them into the subzone x species matrix format required
by the EVA application.

Supported archive layout (as defined in meta.xml):
  - Core: event.txt  (sampling events = subzones)
  - Extension: occurrence.txt  (species occurrences linked via eventID)
"""

from __future__ import annotations

import io
import logging
import os
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field

import pandas as pd

logger = logging.getLogger(__name__)

# DwC namespace used in meta.xml
_DWC_NS = "http://rs.tdwg.org/dwc/text/"

# Maximum allowed uncompressed size for any single file inside the archive (200 MB)
_MAX_DECOMPRESSED_BYTES = 200 * 1024 * 1024


@dataclass
class DwCAMetadata:
    """Parsed metadata from a DwC-A meta.xml."""

    core_file: str
    core_id_index: int
    core_separator: str
    core_header_lines: int
    core_fields: dict[int, str]  # index -> term URI

    extension_file: str | None = None
    ext_coreid_index: int = 0
    ext_separator: str = "\t"
    ext_header_lines: int = 1
    ext_fields: dict[int, str] = field(default_factory=dict)


def is_dwca_zip(file_path: str) -> bool:
    """Check whether a zip file is a Darwin Core Archive (contains meta.xml)."""
    try:
        with zipfile.ZipFile(file_path, "r") as zf:
            return "meta.xml" in zf.namelist()
    except (zipfile.BadZipFile, OSError):
        return False


def _parse_separator(raw: str | None) -> str:
    """Convert meta.xml separator strings to actual characters."""
    if raw is None:
        return "\t"
    return raw.replace("\\t", "\t").replace("\\n", "\n")


def _safe_filename(name: str) -> str:
    """Validate that a filename from meta.xml is a plain basename (no path traversal)."""
    basename = os.path.basename(name)
    if basename != name or ".." in name:
        raise ValueError(f"Suspicious filename in meta.xml: {name!r}")
    return basename


def _safe_read(zf: zipfile.ZipFile, filename: str) -> bytes:
    """Read a file from the zip with decompressed-size guard against zip bombs."""
    info = zf.getinfo(filename)
    if info.file_size > _MAX_DECOMPRESSED_BYTES:
        raise ValueError(
            f"File {filename!r} in archive would decompress to "
            f"{info.file_size / 1024 / 1024:.0f} MB, exceeding the "
            f"{_MAX_DECOMPRESSED_BYTES / 1024 / 1024:.0f} MB limit."
        )
    return zf.read(filename)


def parse_meta_xml(zf: zipfile.ZipFile) -> DwCAMetadata:
    """Parse the meta.xml descriptor inside a DwC-A zip."""
    # Read once; reuse for both the security check and XML parsing
    raw_bytes = _safe_read(zf, "meta.xml")
    raw_xml = raw_bytes.decode("utf-8", errors="replace")

    # Reject entity declarations before parsing (prevents XXE / billion-laughs)
    if "<!ENTITY" in raw_xml.upper():
        raise ValueError("meta.xml contains entity declarations — rejected for security")

    tree = ET.parse(io.BytesIO(raw_bytes))
    root = tree.getroot()

    # --- Core ---
    core_el = root.find(f"{{{_DWC_NS}}}core")
    if core_el is None:
        raise ValueError("meta.xml missing <core> element")

    core_file_el = core_el.find(f"{{{_DWC_NS}}}files/{{{_DWC_NS}}}location")
    if core_file_el is None or core_file_el.text is None:
        raise ValueError("meta.xml core missing <files><location>")

    core_id_el = core_el.find(f"{{{_DWC_NS}}}id")
    core_id_index = int(core_id_el.get("index", "0")) if core_id_el is not None else 0

    core_fields: dict[int, str] = {}
    for f_el in core_el.findall(f"{{{_DWC_NS}}}field"):
        idx = int(f_el.get("index", "0"))
        term = f_el.get("term", "")
        core_fields[idx] = term

    meta = DwCAMetadata(
        core_file=_safe_filename(core_file_el.text.strip()),
        core_id_index=core_id_index,
        core_separator=_parse_separator(core_el.get("fieldsTerminatedBy")),
        core_header_lines=int(core_el.get("ignoreHeaderLines", "0")),
        core_fields=core_fields,
    )

    # --- Extension: find the Occurrence extension (archives may have multiple) ---
    for ext_el in root.findall(f"{{{_DWC_NS}}}extension"):
        row_type = ext_el.get("rowType", "")
        ext_file_el = ext_el.find(f"{{{_DWC_NS}}}files/{{{_DWC_NS}}}location")
        if ext_file_el is None or not ext_file_el.text:
            continue
        # Prefer the Occurrence extension; fall back to first extension if none match
        is_occurrence = "Occurrence" in row_type
        if meta.extension_file is None or is_occurrence:
            meta.extension_file = _safe_filename(ext_file_el.text.strip())
            coreid_el = ext_el.find(f"{{{_DWC_NS}}}coreid")
            meta.ext_coreid_index = (
                int(coreid_el.get("index", "0")) if coreid_el is not None else 0
            )
            meta.ext_separator = _parse_separator(
                ext_el.get("fieldsTerminatedBy")
            )
            meta.ext_header_lines = int(ext_el.get("ignoreHeaderLines", "0"))
            meta.ext_fields = {}
            for f_el in ext_el.findall(f"{{{_DWC_NS}}}field"):
                idx = int(f_el.get("index", "0"))
                term = f_el.get("term", "")
                meta.ext_fields[idx] = term
            if is_occurrence:
                break  # Found the Occurrence extension, stop searching

    return meta


def _short_term(uri: str) -> str:
    """Extract the short term name from a DwC URI."""
    return uri.rsplit("/", 1)[-1] if "/" in uri else uri


def _read_txt(zf: zipfile.ZipFile, filename: str, sep: str, skip: int) -> pd.DataFrame:
    """Read a tab/csv text file from inside the zip with decompression guard."""
    raw = _safe_read(zf, filename)
    # keep_default_na=False to preserve values like "NA" (Namibia country code)
    # that would otherwise be coerced to NaN by pandas
    return pd.read_csv(io.BytesIO(raw), sep=sep, header=0 if skip >= 1 else None,
                       dtype=str, keep_default_na=False)


def _rename_columns(
    df: pd.DataFrame, fields: dict[int, str], id_index: int, id_name: str
) -> pd.DataFrame:
    """Rename DataFrame columns using meta.xml field mapping, with warnings."""
    col_renames: dict[str, str] = {}
    for idx, term in fields.items():
        short = _short_term(term)
        if idx < len(df.columns):
            col_renames[df.columns[idx]] = short
        else:
            logger.warning(
                "meta.xml declares field at index %d but file only has %d columns",
                idx, len(df.columns),
            )
    id_col = df.columns[id_index]
    if id_col not in col_renames:
        col_renames[id_col] = id_name
    return df.rename(columns=col_renames)


def read_dwca(file_path: str, value_column: str = "abundance") -> pd.DataFrame:
    """
    Read a DwC-A zip and return a subzone x species pivot table.

    Parameters
    ----------
    file_path : str
        Path to the DwC-A zip file.
    value_column : str
        How to fill the pivot cells:
        - "abundance": use individualCount (quantitative)
        - "presence": 1/0 presence-absence (qualitative)

    Returns
    -------
    pd.DataFrame
        DataFrame with 'Subzone ID' column and one column per species,
        ready for the EVA pipeline.
    """
    with zipfile.ZipFile(file_path, "r") as zf:
        meta = parse_meta_xml(zf)

        # Read core (events)
        events = _read_txt(zf, meta.core_file, meta.core_separator,
                           meta.core_header_lines)
        events = _rename_columns(events, meta.core_fields, meta.core_id_index, "id")

        if meta.extension_file is None:
            raise ValueError(
                "DwC-A archive has no Occurrence extension — cannot build "
                "species matrix."
            )

        # Read extension (occurrences)
        occurrences = _read_txt(zf, meta.extension_file, meta.ext_separator,
                                meta.ext_header_lines)
        occurrences = _rename_columns(
            occurrences, meta.ext_fields, meta.ext_coreid_index, "coreid"
        )

    # Ensure the join key column name is consistent
    if "coreid" not in occurrences.columns:
        # Fallback: first column of extension is the coreid
        occurrences = occurrences.rename(
            columns={occurrences.columns[0]: "coreid"}
        )

    event_id_col = "eventID" if "eventID" in events.columns else "id"

    # Determine species name column
    species_col = None
    for candidate in ("scientificName", "verbatimIdentification", "taxonID"):
        if candidate in occurrences.columns:
            species_col = candidate
            break
    if species_col is None:
        raise ValueError(
            "Cannot find species name column in occurrence data. "
            "Expected 'scientificName', 'verbatimIdentification', or 'taxonID'."
        )

    # Filter out empty species names
    occurrences = occurrences[occurrences[species_col].str.strip() != ""]

    # Build the pivot
    if value_column == "abundance" and "individualCount" in occurrences.columns:
        occurrences["_count"] = pd.to_numeric(
            occurrences["individualCount"], errors="coerce"
        ).fillna(1)
    else:
        occurrences["_count"] = 1

    # Link occurrences to events via eventID
    link_col = "eventID" if "eventID" in occurrences.columns else "coreid"

    pivot = occurrences.pivot_table(
        index=link_col,
        columns=species_col,
        values="_count",
        aggfunc="sum",
        fill_value=0,
    )

    if value_column == "presence":
        pivot = (pivot > 0).astype(int)

    pivot = pivot.reset_index()
    pivot = pivot.rename(columns={link_col: "Subzone ID"})
    pivot["Subzone ID"] = pivot["Subzone ID"].astype(str).str.strip()
    pivot = pivot.sort_values("Subzone ID").reset_index(drop=True)

    return pivot


def extract_geodataframe(file_path: str) -> "gpd.GeoDataFrame | None":
    """
    Extract a GeoDataFrame of event locations from a DwC-A zip.

    Child events without coordinates inherit them from their parent event
    via the parentEventID field.  Only events that appear in the occurrence
    table are included (matching the pivot subzones).

    Returns None if no coordinates are available.
    """
    import geopandas as gpd
    from shapely.geometry import Point

    with zipfile.ZipFile(file_path, "r") as zf:
        meta = parse_meta_xml(zf)
        events = _read_txt(zf, meta.core_file, meta.core_separator,
                           meta.core_header_lines)
        events = _rename_columns(events, meta.core_fields, meta.core_id_index, "id")

        # Read occurrences to know which eventIDs are actual subzones
        if meta.extension_file:
            occurrences = _read_txt(zf, meta.extension_file, meta.ext_separator,
                                    meta.ext_header_lines)
            occurrences = _rename_columns(
                occurrences, meta.ext_fields, meta.ext_coreid_index, "coreid"
            )
            link_col = "eventID" if "eventID" in occurrences.columns else "coreid"
            subzone_ids = set(occurrences[link_col].unique())
        else:
            subzone_ids = set(events["eventID"].unique()) if "eventID" in events.columns else set(events["id"].unique())

    if "decimalLatitude" not in events.columns or "decimalLongitude" not in events.columns:
        return None

    event_id_col = "eventID" if "eventID" in events.columns else "id"

    # Build coordinate lookup from events that have coordinates
    events["_lat"] = pd.to_numeric(events["decimalLatitude"], errors="coerce")
    events["_lon"] = pd.to_numeric(events["decimalLongitude"], errors="coerce")
    has_coords = events[events["_lat"].notna() & events["_lon"].notna()]

    if has_coords.empty:
        return None

    coord_lookup = has_coords.set_index(event_id_col)[["_lat", "_lon"]]

    # Propagate coordinates from parents to children
    parent_col = "parentEventID" if "parentEventID" in events.columns else None
    rows = []
    for _, ev in events.iterrows():
        eid = ev[event_id_col]
        if eid not in subzone_ids:
            continue
        lat, lon = ev["_lat"], ev["_lon"]
        if pd.isna(lat) and parent_col and ev.get(parent_col):
            parent_id = str(ev[parent_col]).strip()
            if parent_id in coord_lookup.index:
                lat = coord_lookup.loc[parent_id, "_lat"]
                lon = coord_lookup.loc[parent_id, "_lon"]
        if pd.notna(lat) and pd.notna(lon):
            rows.append({"Subzone ID": str(eid).strip(), "lat": lat, "lon": lon})

    if not rows:
        return None

    df = pd.DataFrame(rows)
    geometry = [Point(lon, lat) for lon, lat in zip(df["lon"], df["lat"])]
    gdf = gpd.GeoDataFrame(df[["Subzone ID"]], geometry=geometry, crs="EPSG:4326")
    gdf = gdf.sort_values("Subzone ID").reset_index(drop=True)
    return gdf


def get_dwca_summary(file_path: str) -> dict:
    """
    Return a summary of a DwC-A archive without fully pivoting.

    Returns dict with keys: event_count, occurrence_count, species_count,
    core_file, extension_file, has_coordinates, has_abundance.
    """
    with zipfile.ZipFile(file_path, "r") as zf:
        meta = parse_meta_xml(zf)

        events = _read_txt(zf, meta.core_file, meta.core_separator,
                           meta.core_header_lines)

        summary: dict = {
            "core_file": meta.core_file,
            "extension_file": meta.extension_file,
            "event_count": len(events),
        }

        # Check for coordinates
        events = _rename_columns(events, meta.core_fields, meta.core_id_index, "id")
        summary["has_coordinates"] = bool(
            "decimalLatitude" in events.columns
            and "decimalLongitude" in events.columns
            and events["decimalLatitude"].str.strip().ne("").any()
        )

        if meta.extension_file:
            occurrences = _read_txt(zf, meta.extension_file, meta.ext_separator,
                                    meta.ext_header_lines)
            occurrences = _rename_columns(
                occurrences, meta.ext_fields, meta.ext_coreid_index, "coreid"
            )

            summary["occurrence_count"] = len(occurrences)
            species_col = None
            for c in ("scientificName", "verbatimIdentification", "taxonID"):
                if c in occurrences.columns:
                    species_col = c
                    break
            summary["species_count"] = (
                occurrences[species_col].nunique() if species_col else 0
            )
            summary["has_abundance"] = bool(
                "individualCount" in occurrences.columns
                and pd.to_numeric(
                    occurrences["individualCount"], errors="coerce"
                ).notna().any()
            )
        else:
            summary["occurrence_count"] = 0
            summary["species_count"] = 0
            summary["has_abundance"] = False

    return summary
