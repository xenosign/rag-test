"""data/documents.jsonl 의 섹션을 검색용 청크로 나눠 data/chunks.jsonl 로 저장한다.

1. 섹션을 소제목("1) 기본 혜택", "* 카드 이용 전에 참고해 주세요" 등) 단위로 분할
2. MAX_CHARS 를 넘는 소섹션은 표 / '·' 글머리 묶음 / 문단 단위로 쪼갠 뒤 MAX_CHARS 까지 이어 붙임
   (MAX_CHARS 를 넘는 표는 헤더를 반복하며 행 단위로 분할)
3. 본문이 같은 청크는 카드가 달라도 하나로 합치고 cards 를 합친다
   (예: 모든 카드에 반복되는 "부가서비스 이용 시 참고해 주세요")
4. 임베딩용 텍스트(embed_text)에는 "[카드명] 섹션 > 소제목" 을 앞에 붙인다
"""
import json
import re
from pathlib import Path

IN_PATH = Path("data/documents.jsonl")
OUT_PATH = Path("data/chunks.jsonl")

MAX_CHARS = 700
MIN_CHARS = 150  # 이보다 짧은 마지막 조각은 앞 청크에 붙임 (MAX_CHARS 를 조금 넘을 수 있음)

SUBHEADING = re.compile(r"^(\d{1,2}\) .+|\* .*참고해 주세요)$", re.M)
BULLET = re.compile(r"^ {0,2}· ?\S")  # 들여쓰기 거의 없는 '·' 는 새 묶음 시작


def split_subsections(text: str) -> list[tuple[str | None, str]]:
    """(소제목, 본문) 목록. 첫 줄(섹션 제목)과 첫 소제목 앞 내용은 소제목 None."""
    lines = text.split("\n")
    if re.match(r"^\d{1,2}\. ", lines[0]):
        text = "\n".join(lines[1:])  # 섹션 제목은 breadcrumb 으로 대신함
    parts, last_title, last_end = [], None, 0
    for m in SUBHEADING.finditer(text):
        parts.append((last_title, text[last_end:m.start()]))
        last_title, last_end = m.group(1).strip(), m.end()
    parts.append((last_title, text[last_end:]))
    return [(t, body.strip()) for t, body in parts if body.strip()]


def split_units(body: str) -> list[str]:
    """표, '·' 글머리 묶음, 빈 줄로 구분된 문단 단위로 나눈다."""
    units, current, in_table = [], [], False

    def flush():
        if current and "\n".join(current).strip():
            units.append("\n".join(current).strip())
        current.clear()

    for line in body.split("\n"):
        is_table = line.startswith("|")
        if is_table != in_table or not line.strip() or (not is_table and BULLET.match(line)):
            flush()
        in_table = is_table
        if line.strip():
            current.append(line)
    flush()
    return units


def split_table(table: str) -> list[str]:
    rows = table.split("\n")
    header, rows = rows[:2], rows[2:]
    header_len = len("\n".join(header))
    pieces, current, size = [], [], header_len
    for row in rows:
        if current and size + len(row) + 1 > MAX_CHARS:
            pieces.append("\n".join(header + current))
            current, size = [], header_len
        current.append(row)
        size += len(row) + 1
    if current:
        pieces.append("\n".join(header + current))
    return pieces


def split_long_text(unit: str) -> list[str]:
    pieces, current = [], ""
    for line in unit.split("\n"):
        if current and len(current) + len(line) + 1 > MAX_CHARS:
            pieces.append(current)
            current = ""
        current = f"{current}\n{line}" if current else line
    return pieces + [current] if current else pieces


def pack(body: str) -> list[str]:
    if len(body) <= MAX_CHARS:
        return [body]
    units = []
    for u in split_units(body):
        if len(u) <= MAX_CHARS:
            units.append(u)
        elif u.startswith("|"):
            units.extend(split_table(u))
        else:
            units.extend(split_long_text(u))
    chunks, current = [], ""
    for u in units:
        if current and len(current) + len(u) + 2 > MAX_CHARS:
            chunks.append(current)
            current = ""
        current = f"{current}\n\n{u}" if current else u
    if current:
        if chunks and len(current) < MIN_CHARS:
            chunks[-1] = f"{chunks[-1]}\n\n{current}"
        else:
            chunks.append(current)
    return chunks


def cards_label(cards: list[str], is_common: bool) -> str:
    return "모든 카드 공통" if is_common else ", ".join(cards)


def main():
    docs = [json.loads(l) for l in IN_PATH.open(encoding="utf-8")]
    all_cards = sorted({c for d in docs for c in d["cards"]})

    merged: dict[tuple, dict] = {}  # (섹션번호, 섹션제목, 소제목, 본문) → 청크
    for doc in docs:
        for sub_i, (subtitle, body) in enumerate(split_subsections(doc["text"])):
            for part_i, text in enumerate(pack(body)):
                key = (doc["section_no"], doc["section_title"], subtitle, text)
                if key not in merged:
                    merged[key] = {
                        "id": f"{doc['id']}-{sub_i}-{part_i}",
                        "doc_ids": [],
                        "section_no": doc["section_no"],
                        "section_title": doc["section_title"],
                        "subsection": subtitle,
                        "cards": [],
                        "pages_by_card": {},
                        "text": text,
                    }
                chunk = merged[key]
                chunk["doc_ids"].append(doc["id"])
                for card in doc["cards"]:
                    if card not in chunk["cards"]:
                        chunk["cards"].append(card)
                        chunk["pages_by_card"][card] = doc["pages_by_card"][card]

    chunks = list(merged.values())
    for c in chunks:
        c["is_common"] = len(c["cards"]) == len(all_cards)
        heading = f"{c['section_no']}. {c['section_title']}" if c["section_no"] else c["section_title"]
        if c["subsection"]:
            heading += f" > {c['subsection']}"
        c["embed_text"] = f"[{cards_label(c['cards'], c['is_common'])}] {heading}\n{c['text']}"

    with OUT_PATH.open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    lengths = sorted(len(c["text"]) for c in chunks)
    n_common = sum(c["is_common"] for c in chunks)
    print(f"문서 {len(docs)}개 → 청크 {len(chunks)}개 → {OUT_PATH} "
          f"(전체 공통 {n_common}, 일부/단일 카드 {len(chunks) - n_common})")
    print(f"본문 길이: 최소 {lengths[0]}, 중앙 {lengths[len(lengths) // 2]}, 최대 {lengths[-1]}")


if __name__ == "__main__":
    main()
