"""커밋된 data/documents.jsonl, data/chunks.jsonl 이 파이프라인 코드와 맞는지 확인한다.

prepare/chunk 를 고치고 산출물을 다시 만들지 않으면 실패한다
→ python -m pipeline.prepare && python -m pipeline.chunk 후 다시 실행 (그다음 pipeline.index 로 재색인).
"""
import json

import pytest

from pipeline import chunk, prepare
from rag.cards import ALL_CARDS
from rag.paths import CHUNKS_PATH, DOCUMENTS_PATH


@pytest.fixture(scope="module")
def regenerated(tmp_path_factory):
    out = tmp_path_factory.mktemp("data")
    mp = pytest.MonkeyPatch()
    mp.setattr(prepare, "OUT_PATH", out / "documents.jsonl")
    mp.setattr(chunk, "IN_PATH", out / "documents.jsonl")
    mp.setattr(chunk, "OUT_PATH", out / "chunks.jsonl")
    prepare.main()
    chunk.main()
    mp.undo()
    return out


def test_documents_up_to_date(regenerated):
    assert (regenerated / "documents.jsonl").read_text(encoding="utf-8") == DOCUMENTS_PATH.read_text(encoding="utf-8")


def test_chunks_up_to_date(regenerated):
    assert (regenerated / "chunks.jsonl").read_text(encoding="utf-8") == CHUNKS_PATH.read_text(encoding="utf-8")


def test_chunks_are_consistent():
    chunks = [json.loads(line) for line in CHUNKS_PATH.open(encoding="utf-8")]
    assert len({c["id"] for c in chunks}) == len(chunks)
    for c in chunks:
        # 검색 필터(rag.cards)의 카드명과 데이터의 카드명이 어긋나면 필터 검색 결과가 비게 된다
        assert set(c["cards"]) <= set(ALL_CARDS), c["id"]
        assert c["is_common"] == (set(c["cards"]) == set(ALL_CARDS)), c["id"]
        assert c["text"].strip() and c["embed_text"].endswith(c["text"])
