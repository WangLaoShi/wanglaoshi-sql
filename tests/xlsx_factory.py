"""构造测试用的最小 xlsx。"""

from __future__ import annotations

import zipfile
from pathlib import Path


def write_xlsx(path: Path, sheets: list[tuple[str, str]]) -> None:
    overrides = []
    sheet_xml: list[tuple[str, str]] = []
    rels = []
    workbook_sheets = []
    for index, (name, xml) in enumerate(sheets, start=1):
        target = f"xl/worksheets/sheet{index}.xml"
        overrides.append(
            "<Override "
            f'PartName="/{target}" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        )
        sheet_xml.append((target, xml))
        rels.append(
            "<Relationship "
            f'Id="rId{index}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{index}.xml"/>'
        )
        workbook_sheets.append(
            f'<sheet name="{_escape(name)}" sheetId="{index}" r:id="rId{index}"/>'
        )

    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        + "".join(overrides)
        + "</Types>"
    )
    package_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        "<sheets>"
        + "".join(workbook_sheets)
        + "</sheets></workbook>"
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(rels)
        + "</Relationships>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", package_rels)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        for target, xml in sheet_xml:
            archive.writestr(target, xml)


def worksheet(rows: list[list[str | None]], merges: list[str] | None = None) -> str:
    rendered = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, value in enumerate(row, start=1):
            ref = f"{_column(column_index)}{row_index}"
            text = "" if value is None else _escape(str(value))
            cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{text}</t></is></c>')
        rendered.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    merge_xml = ""
    if merges:
        items = "".join(f'<mergeCell ref="{ref}"/>' for ref in merges)
        merge_xml = f'<mergeCells count="{len(merges)}">{items}</mergeCells>'
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(rendered)}</sheetData>{merge_xml}</worksheet>"
    )


def _column(index: int) -> str:
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
