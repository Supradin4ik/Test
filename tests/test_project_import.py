from pathlib import Path

from openpyxl import Workbook

from app.main import parse_order_sheet


def make_excel_file(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "ORDER"
    ws.append(["position", "dxf", "name", "qty", "thickness", "material"])
    ws.append(["1", "part-001", "Part 001", 3, "2", "Steel"])
    ws.append(["2", "", "Skipped", 10, "3", "Al"])
    ws.append(["3", "part-003", "Part 003", 1.5, "4", "Stainless"])
    wb.save(path)


def test_parse_order_sheet_returns_expected_rows(tmp_path: Path):
    excel_path = tmp_path / "order.xlsx"
    make_excel_file(excel_path)

    parts = parse_order_sheet(excel_path)

    assert len(parts) == 2
    assert parts == [
        {
            "dxf_name": "part-001",
            "name": "Part 001",
            "qty_per_kit": 3.0,
            "thickness": "2",
            "material": "Steel",
        },
        {
            "dxf_name": "part-003",
            "name": "Part 003",
            "qty_per_kit": 1.5,
            "thickness": "4",
            "material": "Stainless",
        },
    ]


def test_project_template_contains_upload_form():
    template = Path("app/templates/project_import.html").read_text(encoding="utf-8")

    assert '<form action="/project/import_excel" method="post" enctype="multipart/form-data">' in template
    assert "Upload" in template
