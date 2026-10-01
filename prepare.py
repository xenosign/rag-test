"""extracted/*.json 을 정제하고 섹션 단위로 나눠 메타데이터와 함께 data/documents.jsonl 로 저장한다.

- 카드명: 2페이지 '상품명' 표에서 추출
- 카드별 전체 페이지를 이어 붙인 뒤 번호 섹션("1. ~ 상품 개요" … "18. ~")으로 분할
  (페이지 경계가 카드마다 달라 페이지 단위 비교는 부정확함)
- 같은 섹션 중 본문이 완전히 같은 것끼리 묶어 한 번만 저장하고, 적용 카드 목록(cards)을 단다.
  비슷해 보여도 수수료율 등이 카드마다 다를 수 있으므로(예: 해외서비스 수수료 0.18% vs 0.2%)
  한 글자라도 다르면 별도 레코드로 남긴다. 모든 카드에 적용되면 is_common=True.
"""
import json
import re
from collections import defaultdict
from pathlib import Path

IN_DIR = Path("extracted")
OUT_PATH = Path("data/documents.jsonl")

INTRO_TITLE = "신용카드 설명서 안내(가입 전 확인 사항)"

NUMBERED_LINE = re.compile(r"^(\d{1,2})\. (.+)$", re.M)
PAGE_MARK = "\x00PAGE{}\x00\n"
PAGE_MARK_RE = re.compile(r"\x00PAGE(\d+)\x00\n")


def normalize(text: str) -> str:
    text = text.replace("　", " ")
    text = re.sub(r"[ \t]+\n", "\n", text)  # 줄 끝 공백
    text = re.sub(r"(?<=\S)[ \t]{2,}", " ", text)  # 단어 사이 연속 공백 (들여쓰기는 유지)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def card_name(doc: dict) -> str:
    for page in doc["pages"]:
        for table in page["tables"]:
            for row in table:
                if row and row[0] == "상품명":
                    return next(c for c in row[1:] if c).strip()
    raise ValueError(f"상품명을 찾지 못함: {doc['file']}")


def find_headings(text: str) -> list[re.Match]:
    """최상위 섹션 제목만 고른다.

    번호는 1부터 순차 증가하되, 카드 고유 섹션(1~2 또는 1~3) 뒤 공통 섹션이 "3." 부터
    다시 시작하므로 같은 번호도 허용한다. 본문 안의 번호 목록("1. 이행 책임 : …",
    "1. 카지노" …)은 번호가 맞지 않거나, 시작된 하위 목록의 연속 번호라서 제외된다.
    """
    headings, last, sub_last = [], 0, None
    for m in NUMBERED_LINE.finditer(text):
        n, title = int(m.group(1)), m.group(2).strip()
        if sub_last is not None and n == sub_last + 1:
            sub_last = n  # 진행 중인 하위 목록
            continue
        if n in (last, last + 1) and len(title) <= 50 and " : " not in title:
            headings.append(m)
            last, sub_last = n, None
        elif n == 1:
            sub_last = 1  # 새 하위 목록 시작
    return headings


def pages_of(full: str, start: int, end: int) -> list[int]:
    """[start, end) 구간에 실제 내용이 걸쳐 있는 페이지 번호."""
    marks = [(m.start(), m.end(), int(m.group(1))) for m in PAGE_MARK_RE.finditer(full)]
    pages = set()
    for i, (m_start, m_end, page) in enumerate(marks):
        page_end = marks[i + 1][0] if i + 1 < len(marks) else len(full)
        lo, hi = max(m_end, start), min(page_end, end)
        if lo < hi and full[lo:hi].strip():
            pages.add(page)
    return sorted(pages)


def split_sections(doc: dict) -> list[dict]:
    full = "".join(PAGE_MARK.format(p["page"]) + normalize(p["text"]) + "\n" for p in doc["pages"])
    bounds = [(0, None, INTRO_TITLE)] + [
        (m.start(), int(m.group(1)), m.group(2).strip()) for m in find_headings(full)
    ]
    sections = []
    for i, (start, num, title) in enumerate(bounds):
        end = bounds[i + 1][0] if i + 1 < len(bounds) else len(full)
        sections.append({
            "section_no": num,
            "section_title": title.replace(doc["card"], "").strip(),
            "pages": pages_of(full, start, end),
            "text": normalize(PAGE_MARK_RE.sub("", full[start:end])),
        })
    return sections


def main():
    docs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(IN_DIR.glob("*.json"))]
    all_cards = []
    # (섹션번호, 섹션제목, 본문) → 해당 본문을 가진 카드들
    variants: dict[tuple, dict] = {}
    for doc in docs:
        card = doc["card"] = card_name(doc)
        all_cards.append(card)
        for s in split_sections(doc):
            key = (s["section_no"], s["section_title"], s["text"])
            v = variants.setdefault(key, {**s, "cards": [], "source_files": [], "pages_by_card": {}})
            v["cards"].append(card)
            v["source_files"].append(doc["file"])
            v["pages_by_card"][card] = s["pages"]

    # id: 전체 공통이면 sNN, 단일 카드 전용이면 sNN-c<카드번호>, 여러 카드가 공유하는 변형이면 sNN-v<순번>
    records = []
    n_shared = defaultdict(int)
    for (num, title, _), v in sorted(variants.items(), key=lambda kv: (kv[0][0] or 0, kv[0][1])):
        sec = f"s{num or 0:02d}"
        is_common = len(v["cards"]) == len(all_cards)
        if is_common:
            rid = sec
        elif len(v["cards"]) == 1:
            rid = f"{sec}-c{all_cards.index(v['cards'][0]):02d}"
        else:
            n_shared[sec] += 1
            rid = f"{sec}-v{n_shared[sec]}"
        records.append({
            "id": rid,
            "section_no": num,
            "section_title": title,
            "is_common": is_common,
            "cards": v["cards"],
            "source_files": v["source_files"],
            "pages_by_card": v["pages_by_card"],
            "text": v["text"],
        })
    assert len({r["id"] for r in records}) == len(records), "id 중복"

    OUT_PATH.parent.mkdir(exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    n_common = sum(r["is_common"] for r in records)
    total_sections = sum(len(r["cards"]) for r in records)
    print(f"카드 {len(all_cards)}종: {', '.join(all_cards)}")
    print(f"섹션 {total_sections}개 → 고유 본문 {len(records)}개 → {OUT_PATH} "
          f"(전체 공통 {n_common}, 일부/단일 카드 {len(records) - n_common})")
    print(f"총 {sum(len(r['text']) for r in records):,}자")


if __name__ == "__main__":
    main()
