import sqlite3
from pathlib import Path

from app.pdf_index import (
    base_key,
    compact_key,
    ensure_pdf_schema,
    find_pdf,
    normalize_key,
    reindex_source,
)


def test_normalization_rules():
    assert base_key(" EVRI.Out.02.01.002.DXF ") == "EVRI.Out.02.01.002"
    assert normalize_key("StBM.014.301   WD.dxf") == "stbm.014.301 wd"
    assert compact_key("StBM.014.301 WD.dxf") == "stbm014301wd"


def test_pdf_match_project_then_standard(tmp_path: Path):
    project = tmp_path / "project"
    standard = tmp_path / "standard"
    project.mkdir()
    standard.mkdir()

    (project / "StBM.014.301 WD.PDF").write_text("p")
    (standard / "EVRI.Out.02.01.002.pdf").write_text("s")

    conn = sqlite3.connect(":memory:")
    ensure_pdf_schema(conn)
    reindex_source(conn, "project", str(project))
    reindex_source(conn, "standard", str(standard))

    assert find_pdf(conn, "StBM.014.301 WD.dxf", "project").endswith("StBM.014.301 WD.PDF")
    assert find_pdf(conn, "EVRI.Out.02.01.002.DXF", "project") is None
    assert find_pdf(conn, "EVRI.Out.02.01.002.DXF", "standard").endswith("EVRI.Out.02.01.002.pdf")
