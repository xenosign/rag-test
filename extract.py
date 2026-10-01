"""card-data/*.pdf 에서 페이지별 텍스트를 추출해 extracted/ 에 저장한다.

일반 텍스트는 그대로, 표는 Markdown 으로 변환해 페이지 내 위→아래 순서로 합친다.
(표를 plain text 로 뽑으면 다단 셀이 뒤섞이기 때문)
"""
import json
import re
from pathlib import Path

import pymupdf

DATA_DIR = Path("card-data")
OUT_DIR = Path("extracted")

# \x07 은 단어 중간("커\x07 피전문점")이나 글머리표 뒤에 끼어 있으므로 뒤 공백까지 제거
BELL = re.compile(r"\x07 ?")
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def clean(text: str) -> str:
    return CONTROL_CHARS.sub("", BELL.sub("", text))


def extract_table(table) -> list[list[str | None]]:
    """표를 행 리스트로 추출하되, 세로 병합 셀은 위 셀 값으로 채운다.

    병합 셀은 가로·세로 모두 None 으로 나오므로, 위쪽 셀의 bbox 가
    현재 행까지 내려와 있는 경우만 세로 병합으로 보고 채운다.
    """
    rows = table.extract()
    for r in range(1, len(rows)):
        row_top = table.rows[r].bbox[1]
        for c, value in enumerate(rows[r]):
            if value is not None:
                continue
            for above in range(r - 1, -1, -1):
                cell = table.rows[above].cells[c]
                if cell is not None:
                    if cell[3] > row_top + 1:
                        rows[r][c] = rows[above][c]
                    break
    return rows


def table_to_markdown(rows: list[list[str | None]]) -> str:
    # 병합 셀은 None 으로 나오므로 빈 칸 처리, 셀 내부 줄바꿈은 <br> 로 유지
    def cell(c):
        return clean(c or "").strip().replace("\n", "<br>").replace("|", "\\|")

    rows = [[cell(c) for c in r] for r in rows]
    header, body = rows[0], rows[1:]
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(r) + " |" for r in body]
    return "\n".join(lines)


def overlaps(rect: pymupdf.Rect, boxes: list[pymupdf.Rect]) -> bool:
    return any(rect.intersects(b) and (rect & b).get_area() > 0.5 * rect.get_area() for b in boxes)


def extract_page(page: pymupdf.Page) -> tuple[str, list]:
    tables = page.find_tables().tables
    table_boxes = [pymupdf.Rect(t.bbox) for t in tables]

    # (y0, x0, 내용) 항목을 모아 위→아래 정렬
    items = []
    for x0, y0, x1, y1, text, _, block_type in page.get_text("blocks", sort=True):
        if block_type != 0 or overlaps(pymupdf.Rect(x0, y0, x1, y1), table_boxes):
            continue
        items.append((y0, x0, clean(text).strip()))

    extracted_tables = []
    for t, box in zip(tables, table_boxes):
        rows = extract_table(t)
        extracted_tables.append([[clean(c) if c else c for c in r] for r in rows])
        items.append((box.y0, box.x0, table_to_markdown(rows)))

    items.sort(key=lambda it: (round(it[0]), it[1]))
    text = "\n\n".join(content for _, _, content in items if content)
    return text, extracted_tables


def extract(pdf_path: Path) -> dict:
    doc = pymupdf.open(pdf_path)
    pages = []
    for i, page in enumerate(doc, start=1):
        text, tables = extract_page(page)
        pages.append({"page": i, "text": text, "tables": tables})
    return {"file": pdf_path.name, "num_pages": len(pages), "pages": pages}


def main():
    OUT_DIR.mkdir(exist_ok=True)
    for pdf_path in sorted(DATA_DIR.glob("*.pdf")):
        result = extract(pdf_path)
        stem = pdf_path.stem
        (OUT_DIR / f"{stem}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (OUT_DIR / f"{stem}.md").write_text(
            "\n\n".join(f"<!-- page {p['page']} -->\n\n{p['text']}" for p in result["pages"]),
            encoding="utf-8",
        )
        chars = sum(len(p["text"]) for p in result["pages"])
        n_tables = sum(len(p["tables"]) for p in result["pages"])
        print(f"{result['num_pages']:>3}p  {chars:>6} chars  {n_tables:>2} tables  {pdf_path.name}")


if __name__ == "__main__":
    main()
