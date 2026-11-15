"""检查 xlsx 是不是第一行为列名的矩形表。只用标准库。"""

from __future__ import annotations

import zipfile
from xml.etree import ElementTree

from tableprobe.errors import TableProbeError


def prepare_sheet(path: str, sheet: str | None) -> str:
    """确认工作表能读，并返回实际使用的工作表名。"""

    try:
        with zipfile.ZipFile(path) as archive:
            sheet_name, sheet_xml = _read_sheet(archive, sheet)
            shared = _shared_strings(archive)
    except TableProbeError:
        raise
    except zipfile.BadZipFile as exc:
        raise TableProbeError("这个文件不是有效的 xlsx。") from exc
    except KeyError as exc:
        raise TableProbeError("这个文件不是有效的 xlsx。") from exc
    except ElementTree.ParseError as exc:
        raise TableProbeError("这个文件不是有效的 xlsx。") from exc

    root = ElementTree.fromstring(sheet_xml)
    for element in root.iter():
        if _local(element.tag) == "mergeCell":
            raise TableProbeError("这个工作表有合并单元格，第一版只读取矩形表。")
    _reject_blank_header(root, shared)
    return sheet_name


def _read_sheet(archive: zipfile.ZipFile, sheet: str | None) -> tuple[str, bytes]:
    workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    sheets: list[tuple[str, str]] = []
    for element in workbook.iter():
        if _local(element.tag) != "sheet":
            continue
        name = element.attrib.get("name") or ""
        rel_id = _attr(element, "id")
        if rel_id:
            sheets.append((name, rel_id))
    if not sheets:
        raise TableProbeError("这个 xlsx 里没有工作表。")

    if sheet is None:
        sheet_name, rel_id = sheets[0]
    else:
        matches = [item for item in sheets if item[0] == sheet]
        if not matches:
            raise TableProbeError(f"这个工作表不存在：{sheet}")
        sheet_name, rel_id = matches[0]

    rels = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    target = None
    for element in rels.iter():
        if _local(element.tag) == "Relationship" and element.attrib.get("Id") == rel_id:
            target = element.attrib.get("Target")
    if not target:
        raise TableProbeError("这个文件不是有效的 xlsx。")
    target = target.replace("\\", "/").lstrip("/")
    if target.startswith("./"):
        target = target[2:]
    if not target.startswith("xl/"):
        target = "xl/" + target
    return sheet_name, archive.read(target)


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    values: list[str] = []
    for item in list(root):
        if _local(item.tag) != "si":
            continue
        texts = [
            node.text or ""
            for node in item.iter()
            if _local(node.tag) == "t"
        ]
        values.append("".join(texts))
    return values


def _reject_blank_header(root: ElementTree.Element, shared: list[str]) -> None:
    first_row = next((element for element in root.iter() if _local(element.tag) == "row"), None)
    if first_row is None:
        raise TableProbeError("这个工作表的第一行有空列名，不是矩形表。")

    cells: list[tuple[int, str]] = []
    for element in list(first_row):
        if _local(element.tag) != "c":
            continue
        cells.append((_column_index(element.attrib.get("r", "")), _cell_text(element, shared)))
    if not cells:
        raise TableProbeError("这个工作表的第一行有空列名，不是矩形表。")

    cells.sort(key=lambda item: item[0])
    indexes = [index for index, _ in cells]
    if indexes != list(range(1, len(indexes) + 1)):
        raise TableProbeError("这个工作表的第一行有空列名，不是矩形表。")
    if any(not text.strip() for _, text in cells):
        raise TableProbeError("这个工作表的第一行有空列名，不是矩形表。")


def _cell_text(cell: ElementTree.Element, shared: list[str]) -> str:
    kind = cell.attrib.get("t")
    value = next((node.text or "" for node in cell.iter() if _local(node.tag) == "v"), "")
    if kind == "s":
        try:
            return shared[int(value)]
        except (ValueError, IndexError):
            return ""
    if kind == "inlineStr":
        return "".join(node.text or "" for node in cell.iter() if _local(node.tag) == "t")
    return value


def _column_index(ref: str) -> int:
    letters = "".join(character for character in ref if character.isalpha())
    if not letters:
        return 0
    index = 0
    for character in letters:
        index = index * 26 + (ord(character.upper()) - 64)
    return index


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _attr(element: ElementTree.Element, name: str) -> str | None:
    for key, value in element.attrib.items():
        if _local(key) == name:
            return value
    return None
