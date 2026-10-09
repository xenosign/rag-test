"""섹션 → 검색용 청크 분할 (pipeline.chunk)."""
from pipeline.chunk import MAX_CHARS, MIN_CHARS, pack, split_subsections, split_table, split_units


def table(n_rows: int, cell: str = "내용") -> str:
    rows = ["| 구분 | 내용 |", "|---|---|"] + [f"| 항목{i} | {cell * 10} |" for i in range(n_rows)]
    return "\n".join(rows)


def test_split_subsections_drops_section_title_and_splits_on_subheadings():
    text = "3. 부가서비스\n공통 안내\n1) 기본 혜택\n적립 0.5%\n2) 추가 혜택\n라운지 연 2회\n* 카드 이용 전에 참고해 주세요\n유의사항"
    assert split_subsections(text) == [
        (None, "공통 안내"),
        ("1) 기본 혜택", "적립 0.5%"),
        ("2) 추가 혜택", "라운지 연 2회"),
        ("* 카드 이용 전에 참고해 주세요", "유의사항"),
    ]


def test_split_subsections_skips_empty_bodies():
    assert split_subsections("1) 기본 혜택\n\n2) 추가 혜택\n본문") == [("2) 추가 혜택", "본문")]


def test_split_units_separates_tables_bullets_and_paragraphs():
    body = "문단 하나\n이어지는 줄\n\n| a | b |\n|---|---|\n| 1 | 2 |\n· 첫 글머리\n  계속\n· 둘째 글머리"
    assert split_units(body) == [
        "문단 하나\n이어지는 줄",
        "| a | b |\n|---|---|\n| 1 | 2 |",
        "· 첫 글머리\n  계속",
        "· 둘째 글머리",
    ]


def test_split_table_repeats_header_and_respects_limit():
    t = table(40)
    pieces = split_table(t)
    assert len(pieces) > 1
    header = t.split("\n")[:2]
    body_rows = []
    for p in pieces:
        lines = p.split("\n")
        assert lines[:2] == header
        assert len(p) <= MAX_CHARS
        body_rows += lines[2:]
    assert body_rows == t.split("\n")[2:]  # 행 순서 유지, 누락·중복 없음


def test_pack_keeps_short_body_whole():
    assert pack("짧은 본문") == ["짧은 본문"]


def test_pack_splits_long_body_without_losing_lines():
    paragraphs = [f"문단 {i} " + "가" * 150 for i in range(12)]
    body = "\n\n".join(paragraphs)
    chunks = pack(body)
    assert len(chunks) > 1
    assert all(len(c) <= MAX_CHARS + MIN_CHARS for c in chunks)
    assert "\n\n".join(chunks) == body


def test_pack_merges_short_tail_into_previous_chunk():
    body = "\n\n".join(["가" * 340, "나" * 340, "다" * 50])
    chunks = pack(body)
    assert chunks[-1].endswith("다" * 50)
    assert all(len(c) >= MIN_CHARS for c in chunks)
