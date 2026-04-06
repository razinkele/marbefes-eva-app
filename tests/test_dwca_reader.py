"""
Tests for the Darwin Core Archive reader module.

Uses the real dwca-macrosoft-v2.1.zip file in data/.
"""

import os
import sys
import zipfile
import tempfile

import pandas as pd
import pytest

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dwca_reader

# Path to the real test archive
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DWCA_PATH = os.path.join(DATA_DIR, "dwca-macrosoft-v2.1.zip")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def dwca_path():
    """Return path to the real DwC-A test file, skip if not present."""
    if not os.path.exists(DWCA_PATH):
        pytest.skip("dwca-macrosoft-v2.1.zip not found in data/")
    return DWCA_PATH


@pytest.fixture
def minimal_dwca(tmp_path):
    """Create a minimal synthetic DwC-A zip for unit tests."""
    meta_xml = """\
<archive xmlns="http://rs.tdwg.org/dwc/text/" metadata="eml.xml">
  <core encoding="UTF-8" fieldsTerminatedBy="\\t" linesTerminatedBy="\\n" ignoreHeaderLines="1" rowType="http://rs.tdwg.org/dwc/terms/Event">
    <files><location>event.txt</location></files>
    <id index="0" />
    <field index="1" term="http://rs.tdwg.org/dwc/terms/eventID"/>
    <field index="2" term="http://rs.tdwg.org/dwc/terms/decimalLatitude"/>
    <field index="3" term="http://rs.tdwg.org/dwc/terms/decimalLongitude"/>
  </core>
  <extension encoding="UTF-8" fieldsTerminatedBy="\\t" linesTerminatedBy="\\n" ignoreHeaderLines="1" rowType="http://rs.tdwg.org/dwc/terms/Occurrence">
    <files><location>occurrence.txt</location></files>
    <coreid index="0" />
    <field index="1" term="http://rs.tdwg.org/dwc/terms/eventID"/>
    <field index="2" term="http://rs.tdwg.org/dwc/terms/scientificName"/>
    <field index="3" term="http://rs.tdwg.org/dwc/terms/individualCount"/>
  </extension>
</archive>"""

    event_txt = "id\teventID\tdecimalLatitude\tdecimalLongitude\n"
    event_txt += "E1\tE1\t55.0\t21.0\n"
    event_txt += "E2\tE2\t55.1\t21.1\n"
    event_txt += "E3\tE3\t55.2\t21.2\n"

    occ_txt = "id\teventID\tscientificName\tindividualCount\n"
    occ_txt += "E1\tE1\tSpecies A\t3\n"
    occ_txt += "E1\tE1\tSpecies B\t1\n"
    occ_txt += "E2\tE2\tSpecies A\t5\n"
    occ_txt += "E2\tE2\tSpecies C\t2\n"
    occ_txt += "E3\tE3\tSpecies B\t4\n"
    occ_txt += "E3\tE3\tSpecies C\t1\n"

    zip_path = str(tmp_path / "test_dwca.zip")
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("meta.xml", meta_xml)
        zf.writestr("eml.xml", "<eml/>")
        zf.writestr("event.txt", event_txt)
        zf.writestr("occurrence.txt", occ_txt)

    return zip_path


# ---------------------------------------------------------------------------
# is_dwca_zip
# ---------------------------------------------------------------------------

class TestIsDwcaZip:
    def test_real_archive(self, dwca_path):
        assert dwca_reader.is_dwca_zip(dwca_path) is True

    def test_minimal_archive(self, minimal_dwca):
        assert dwca_reader.is_dwca_zip(minimal_dwca) is True

    def test_non_dwca_zip(self, tmp_path):
        """A regular zip without meta.xml should return False."""
        zip_path = str(tmp_path / "regular.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("readme.txt", "hello")
        assert dwca_reader.is_dwca_zip(zip_path) is False

    def test_not_a_zip(self, tmp_path):
        """A non-zip file should return False."""
        txt_path = str(tmp_path / "plain.txt")
        with open(txt_path, "w") as f:
            f.write("not a zip")
        assert dwca_reader.is_dwca_zip(txt_path) is False

    def test_nonexistent_file(self):
        assert dwca_reader.is_dwca_zip("/nonexistent/path.zip") is False


# ---------------------------------------------------------------------------
# parse_meta_xml
# ---------------------------------------------------------------------------

class TestParseMetaXml:
    def test_real_archive_meta(self, dwca_path):
        with zipfile.ZipFile(dwca_path) as zf:
            meta = dwca_reader.parse_meta_xml(zf)
        assert meta.core_file == "event.txt"
        assert meta.extension_file == "occurrence.txt"
        assert meta.core_separator == "\t"
        assert meta.core_header_lines == 1
        # Should have field mappings
        assert len(meta.core_fields) > 0
        assert len(meta.ext_fields) > 0

    def test_minimal_meta(self, minimal_dwca):
        with zipfile.ZipFile(minimal_dwca) as zf:
            meta = dwca_reader.parse_meta_xml(zf)
        assert meta.core_file == "event.txt"
        assert meta.extension_file == "occurrence.txt"
        assert meta.core_id_index == 0


# ---------------------------------------------------------------------------
# read_dwca - minimal synthetic archive
# ---------------------------------------------------------------------------

class TestReadDwcaMinimal:
    def test_abundance_mode(self, minimal_dwca):
        df = dwca_reader.read_dwca(minimal_dwca, value_column="abundance")

        assert "Subzone ID" in df.columns
        assert set(df["Subzone ID"]) == {"E1", "E2", "E3"}

        species_cols = [c for c in df.columns if c != "Subzone ID"]
        assert set(species_cols) == {"Species A", "Species B", "Species C"}

        # Check specific values
        row_e1 = df[df["Subzone ID"] == "E1"].iloc[0]
        assert row_e1["Species A"] == 3
        assert row_e1["Species B"] == 1
        assert row_e1["Species C"] == 0

        row_e2 = df[df["Subzone ID"] == "E2"].iloc[0]
        assert row_e2["Species A"] == 5
        assert row_e2["Species C"] == 2

    def test_presence_mode(self, minimal_dwca):
        df = dwca_reader.read_dwca(minimal_dwca, value_column="presence")

        row_e1 = df[df["Subzone ID"] == "E1"].iloc[0]
        assert row_e1["Species A"] == 1
        assert row_e1["Species B"] == 1
        assert row_e1["Species C"] == 0

    def test_sorted_by_subzone(self, minimal_dwca):
        df = dwca_reader.read_dwca(minimal_dwca)
        assert list(df["Subzone ID"]) == sorted(df["Subzone ID"])

    def test_no_duplicate_subzones(self, minimal_dwca):
        df = dwca_reader.read_dwca(minimal_dwca)
        assert df["Subzone ID"].is_unique


# ---------------------------------------------------------------------------
# read_dwca - real archive (dwca-macrosoft-v2.1.zip)
# ---------------------------------------------------------------------------

class TestReadDwcaReal:
    def test_abundance_shape(self, dwca_path):
        df = dwca_reader.read_dwca(dwca_path, value_column="abundance")

        assert "Subzone ID" in df.columns
        species_cols = [c for c in df.columns if c != "Subzone ID"]

        # From exploration: 118 events with occurrences, 315 species
        assert len(df) == 118
        assert len(species_cols) == 315

    def test_presence_shape(self, dwca_path):
        df = dwca_reader.read_dwca(dwca_path, value_column="presence")
        # Same dimensions
        assert len(df) == 118
        # All values should be 0 or 1
        species_cols = [c for c in df.columns if c != "Subzone ID"]
        for col in species_cols:
            assert set(df[col].unique()).issubset({0, 1})

    def test_abundance_values_positive(self, dwca_path):
        df = dwca_reader.read_dwca(dwca_path, value_column="abundance")
        species_cols = [c for c in df.columns if c != "Subzone ID"]
        for col in species_cols:
            assert (df[col] >= 0).all()

    def test_subzone_ids_are_strings(self, dwca_path):
        df = dwca_reader.read_dwca(dwca_path)
        assert pd.api.types.is_string_dtype(df["Subzone ID"])

    def test_known_species_present(self, dwca_path):
        """Spot-check a known species from the data exploration."""
        df = dwca_reader.read_dwca(dwca_path)
        species_cols = [c for c in df.columns if c != "Subzone ID"]
        # Metasychis gotoi was in the first occurrence row
        assert "Metasychis gotoi" in species_cols

    def test_eva_compatible(self, dwca_path):
        """The output should work with the EVA detect_data_type function."""
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        import eva_calculations

        df = dwca_reader.read_dwca(dwca_path, value_column="abundance")
        dtype = eva_calculations.detect_data_type(df)
        assert dtype in ("qualitative", "quantitative")

        df_pres = dwca_reader.read_dwca(dwca_path, value_column="presence")
        dtype_pres = eva_calculations.detect_data_type(df_pres)
        assert dtype_pres in ("qualitative", "quantitative")


# ---------------------------------------------------------------------------
# get_dwca_summary
# ---------------------------------------------------------------------------

class TestGetDwcaSummary:
    def test_real_summary(self, dwca_path):
        summary = dwca_reader.get_dwca_summary(dwca_path)

        assert summary["core_file"] == "event.txt"
        assert summary["extension_file"] == "occurrence.txt"
        assert summary["event_count"] == 153
        assert summary["occurrence_count"] == 1551
        assert summary["species_count"] == 315
        assert summary["has_abundance"] is True
        assert summary["has_coordinates"] is True

    def test_minimal_summary(self, minimal_dwca):
        summary = dwca_reader.get_dwca_summary(minimal_dwca)

        assert summary["event_count"] == 3
        assert summary["occurrence_count"] == 6
        assert summary["species_count"] == 3
        assert summary["has_abundance"] is True
        assert summary["has_coordinates"] is True


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# extract_geodataframe
# ---------------------------------------------------------------------------

class TestExtractGeoDataFrame:
    def test_real_archive_returns_gdf(self, dwca_path):
        gdf = dwca_reader.extract_geodataframe(dwca_path)

        assert gdf is not None
        assert "Subzone ID" in gdf.columns
        assert "geometry" in gdf.columns
        # 118 subzones with occurrences should all get coordinates
        assert len(gdf) == 118

    def test_real_archive_crs(self, dwca_path):
        gdf = dwca_reader.extract_geodataframe(dwca_path)
        assert gdf.crs is not None
        assert gdf.crs.to_epsg() == 4326

    def test_real_archive_coordinates_in_range(self, dwca_path):
        """Coordinates should be in the Mediterranean region."""
        gdf = dwca_reader.extract_geodataframe(dwca_path)
        bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
        # Longitude should be roughly around 25 (Crete area)
        assert 20 < bounds[0] < 30
        assert 20 < bounds[2] < 30
        # Latitude should be roughly around 35
        assert 30 < bounds[1] < 40
        assert 30 < bounds[3] < 40

    def test_real_archive_matches_pivot_ids(self, dwca_path):
        """GeoDataFrame Subzone IDs should match the pivot table IDs."""
        gdf = dwca_reader.extract_geodataframe(dwca_path)
        pivot = dwca_reader.read_dwca(dwca_path)
        geo_ids = set(gdf["Subzone ID"])
        pivot_ids = set(pivot["Subzone ID"])
        assert geo_ids == pivot_ids

    def test_minimal_archive_with_coords(self, minimal_dwca):
        gdf = dwca_reader.extract_geodataframe(minimal_dwca)
        assert gdf is not None
        assert len(gdf) == 3
        # Check actual coordinate values
        row_e1 = gdf[gdf["Subzone ID"] == "E1"].iloc[0]
        assert row_e1.geometry.y == 55.0
        assert row_e1.geometry.x == 21.0

    def test_no_coordinates_returns_none(self, tmp_path):
        """Archive with no coordinates should return None."""
        meta_xml = """\
<archive xmlns="http://rs.tdwg.org/dwc/text/">
  <core encoding="UTF-8" fieldsTerminatedBy="\\t" ignoreHeaderLines="1" rowType="http://rs.tdwg.org/dwc/terms/Event">
    <files><location>event.txt</location></files>
    <id index="0" />
    <field index="1" term="http://rs.tdwg.org/dwc/terms/eventID"/>
  </core>
  <extension encoding="UTF-8" fieldsTerminatedBy="\\t" ignoreHeaderLines="1" rowType="http://rs.tdwg.org/dwc/terms/Occurrence">
    <files><location>occurrence.txt</location></files>
    <coreid index="0" />
    <field index="1" term="http://rs.tdwg.org/dwc/terms/eventID"/>
    <field index="2" term="http://rs.tdwg.org/dwc/terms/scientificName"/>
    <field index="3" term="http://rs.tdwg.org/dwc/terms/individualCount"/>
  </extension>
</archive>"""
        event_txt = "id\teventID\nE1\tE1\n"
        occ_txt = "id\teventID\tscientificName\tindividualCount\nE1\tE1\tSpecies A\t1\n"

        zip_path = str(tmp_path / "no_coords.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("meta.xml", meta_xml)
            zf.writestr("event.txt", event_txt)
            zf.writestr("occurrence.txt", occ_txt)

        gdf = dwca_reader.extract_geodataframe(zip_path)
        assert gdf is None

    def test_child_inherits_parent_coords(self, tmp_path):
        """Child events should inherit coordinates from parent events."""
        meta_xml = """\
<archive xmlns="http://rs.tdwg.org/dwc/text/">
  <core encoding="UTF-8" fieldsTerminatedBy="\\t" ignoreHeaderLines="1" rowType="http://rs.tdwg.org/dwc/terms/Event">
    <files><location>event.txt</location></files>
    <id index="0" />
    <field index="1" term="http://rs.tdwg.org/dwc/terms/eventID"/>
    <field index="2" term="http://rs.tdwg.org/dwc/terms/parentEventID"/>
    <field index="3" term="http://rs.tdwg.org/dwc/terms/decimalLatitude"/>
    <field index="4" term="http://rs.tdwg.org/dwc/terms/decimalLongitude"/>
  </core>
  <extension encoding="UTF-8" fieldsTerminatedBy="\\t" ignoreHeaderLines="1" rowType="http://rs.tdwg.org/dwc/terms/Occurrence">
    <files><location>occurrence.txt</location></files>
    <coreid index="0" />
    <field index="1" term="http://rs.tdwg.org/dwc/terms/eventID"/>
    <field index="2" term="http://rs.tdwg.org/dwc/terms/scientificName"/>
    <field index="3" term="http://rs.tdwg.org/dwc/terms/individualCount"/>
  </extension>
</archive>"""
        # Parent P1 has coords; children C1A and C1B inherit from it
        event_txt = "id\teventID\tparentEventID\tdecimalLatitude\tdecimalLongitude\n"
        event_txt += "P1\tP1\t\t55.5\t21.5\n"
        event_txt += "C1A\tC1A\tP1\t\t\n"
        event_txt += "C1B\tC1B\tP1\t\t\n"

        occ_txt = "id\teventID\tscientificName\tindividualCount\n"
        occ_txt += "C1A\tC1A\tSpecies X\t3\n"
        occ_txt += "C1B\tC1B\tSpecies Y\t2\n"

        zip_path = str(tmp_path / "inherit.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("meta.xml", meta_xml)
            zf.writestr("event.txt", event_txt)
            zf.writestr("occurrence.txt", occ_txt)

        gdf = dwca_reader.extract_geodataframe(zip_path)
        assert gdf is not None
        assert len(gdf) == 2  # Only children (C1A, C1B) are in occurrences
        # Both should have parent's coordinates
        for _, row in gdf.iterrows():
            assert row.geometry.y == 55.5
            assert row.geometry.x == 21.5


class TestEdgeCases:
    def test_no_extension_raises(self, tmp_path):
        """Archive with no occurrence extension should raise."""
        meta_xml = """\
<archive xmlns="http://rs.tdwg.org/dwc/text/">
  <core encoding="UTF-8" fieldsTerminatedBy="\\t" ignoreHeaderLines="1" rowType="http://rs.tdwg.org/dwc/terms/Event">
    <files><location>event.txt</location></files>
    <id index="0" />
  </core>
</archive>"""
        event_txt = "id\nE1\nE2\n"
        zip_path = str(tmp_path / "no_ext.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("meta.xml", meta_xml)
            zf.writestr("event.txt", event_txt)

        with pytest.raises(ValueError, match="no Occurrence extension"):
            dwca_reader.read_dwca(zip_path)

    def test_empty_species_names_filtered(self, tmp_path):
        """Occurrences with empty species names should be excluded."""
        meta_xml = """\
<archive xmlns="http://rs.tdwg.org/dwc/text/">
  <core encoding="UTF-8" fieldsTerminatedBy="\\t" ignoreHeaderLines="1" rowType="http://rs.tdwg.org/dwc/terms/Event">
    <files><location>event.txt</location></files>
    <id index="0" />
    <field index="1" term="http://rs.tdwg.org/dwc/terms/eventID"/>
  </core>
  <extension encoding="UTF-8" fieldsTerminatedBy="\\t" ignoreHeaderLines="1" rowType="http://rs.tdwg.org/dwc/terms/Occurrence">
    <files><location>occurrence.txt</location></files>
    <coreid index="0" />
    <field index="1" term="http://rs.tdwg.org/dwc/terms/eventID"/>
    <field index="2" term="http://rs.tdwg.org/dwc/terms/scientificName"/>
    <field index="3" term="http://rs.tdwg.org/dwc/terms/individualCount"/>
  </extension>
</archive>"""
        event_txt = "id\teventID\nE1\tE1\n"
        occ_txt = "id\teventID\tscientificName\tindividualCount\n"
        occ_txt += "E1\tE1\tSpecies X\t2\n"
        occ_txt += "E1\tE1\t\t1\n"  # empty species name
        occ_txt += "E1\tE1\t  \t1\n"  # whitespace-only species name

        zip_path = str(tmp_path / "empty_sp.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("meta.xml", meta_xml)
            zf.writestr("event.txt", event_txt)
            zf.writestr("occurrence.txt", occ_txt)

        df = dwca_reader.read_dwca(zip_path)
        species_cols = [c for c in df.columns if c != "Subzone ID"]
        # Only "Species X" should be present
        assert species_cols == ["Species X"]

    def test_missing_count_defaults_to_one(self, tmp_path):
        """When individualCount is missing, default to 1."""
        meta_xml = """\
<archive xmlns="http://rs.tdwg.org/dwc/text/">
  <core encoding="UTF-8" fieldsTerminatedBy="\\t" ignoreHeaderLines="1" rowType="http://rs.tdwg.org/dwc/terms/Event">
    <files><location>event.txt</location></files>
    <id index="0" />
    <field index="1" term="http://rs.tdwg.org/dwc/terms/eventID"/>
  </core>
  <extension encoding="UTF-8" fieldsTerminatedBy="\\t" ignoreHeaderLines="1" rowType="http://rs.tdwg.org/dwc/terms/Occurrence">
    <files><location>occurrence.txt</location></files>
    <coreid index="0" />
    <field index="1" term="http://rs.tdwg.org/dwc/terms/eventID"/>
    <field index="2" term="http://rs.tdwg.org/dwc/terms/scientificName"/>
    <field index="3" term="http://rs.tdwg.org/dwc/terms/individualCount"/>
  </extension>
</archive>"""
        event_txt = "id\teventID\nE1\tE1\n"
        occ_txt = "id\teventID\tscientificName\tindividualCount\n"
        occ_txt += "E1\tE1\tSpecies A\t\n"  # empty count
        occ_txt += "E1\tE1\tSpecies A\tNA\n"  # non-numeric count

        zip_path = str(tmp_path / "no_count.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("meta.xml", meta_xml)
            zf.writestr("event.txt", event_txt)
            zf.writestr("occurrence.txt", occ_txt)

        df = dwca_reader.read_dwca(zip_path, value_column="abundance")
        # Two occurrences of Species A with count=1 each -> sum=2
        assert df[df["Subzone ID"] == "E1"]["Species A"].iloc[0] == 2

    def test_path_traversal_in_filename_rejected(self, tmp_path):
        """meta.xml referencing '../' filenames should be rejected."""
        meta_xml = """\
<archive xmlns="http://rs.tdwg.org/dwc/text/">
  <core encoding="UTF-8" fieldsTerminatedBy="\\t" ignoreHeaderLines="1" rowType="http://rs.tdwg.org/dwc/terms/Event">
    <files><location>../../../etc/passwd</location></files>
    <id index="0" />
  </core>
</archive>"""
        zip_path = str(tmp_path / "traversal.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("meta.xml", meta_xml)

        with pytest.raises(ValueError, match="Suspicious filename"):
            dwca_reader.read_dwca(zip_path)

    def test_entity_declaration_rejected(self, tmp_path):
        """meta.xml with XML entity declarations should be rejected."""
        meta_xml = """\
<?xml version="1.0"?>
<!DOCTYPE foo [<!ENTITY xxe "evil">]>
<archive xmlns="http://rs.tdwg.org/dwc/text/">
  <core encoding="UTF-8" fieldsTerminatedBy="\\t" ignoreHeaderLines="1" rowType="http://rs.tdwg.org/dwc/terms/Event">
    <files><location>event.txt</location></files>
    <id index="0" />
  </core>
</archive>"""
        zip_path = str(tmp_path / "xxe.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("meta.xml", meta_xml)
            zf.writestr("event.txt", "id\nE1\n")

        with pytest.raises(ValueError, match="entity declarations"):
            dwca_reader.read_dwca(zip_path)

    def test_multiple_extensions_finds_occurrence(self, tmp_path):
        """Archive with multiple extensions should pick the Occurrence one."""
        meta_xml = """\
<archive xmlns="http://rs.tdwg.org/dwc/text/">
  <core encoding="UTF-8" fieldsTerminatedBy="\\t" ignoreHeaderLines="1" rowType="http://rs.tdwg.org/dwc/terms/Event">
    <files><location>event.txt</location></files>
    <id index="0" />
    <field index="1" term="http://rs.tdwg.org/dwc/terms/eventID"/>
  </core>
  <extension encoding="UTF-8" fieldsTerminatedBy="\\t" ignoreHeaderLines="1" rowType="http://rs.tdwg.org/dwc/terms/MeasurementOrFact">
    <files><location>measurement.txt</location></files>
    <coreid index="0" />
    <field index="1" term="http://rs.tdwg.org/dwc/terms/measurementType"/>
  </extension>
  <extension encoding="UTF-8" fieldsTerminatedBy="\\t" ignoreHeaderLines="1" rowType="http://rs.tdwg.org/dwc/terms/Occurrence">
    <files><location>occurrence.txt</location></files>
    <coreid index="0" />
    <field index="1" term="http://rs.tdwg.org/dwc/terms/eventID"/>
    <field index="2" term="http://rs.tdwg.org/dwc/terms/scientificName"/>
    <field index="3" term="http://rs.tdwg.org/dwc/terms/individualCount"/>
  </extension>
</archive>"""
        event_txt = "id\teventID\nE1\tE1\n"
        occ_txt = "id\teventID\tscientificName\tindividualCount\nE1\tE1\tSpecies X\t5\n"
        meas_txt = "id\tmeasurementType\nE1\ttemperature\n"

        zip_path = str(tmp_path / "multi_ext.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("meta.xml", meta_xml)
            zf.writestr("event.txt", event_txt)
            zf.writestr("occurrence.txt", occ_txt)
            zf.writestr("measurement.txt", meas_txt)

        df = dwca_reader.read_dwca(zip_path, value_column="abundance")
        assert "Species X" in df.columns
        assert df[df["Subzone ID"] == "E1"]["Species X"].iloc[0] == 5
