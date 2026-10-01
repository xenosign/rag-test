"""data/chunks.jsonl 을 bge-m3 로 임베딩해 Chroma(data/chroma) 에 저장한다.

- 임베딩 입력: embed_text ("[카드명] 섹션 > 소제목" + 본문)
- document: 본문(text) — LLM 에 넘길 내용
- 카드 필터: Chroma 메타데이터는 리스트를 쓸 수 없으므로 카드마다 boolean 키를 둔다
  예) where={"card:제네시스 현대카드": True}
"""
import json
from pathlib import Path

import chromadb
import torch
from sentence_transformers import SentenceTransformer

CHUNKS_PATH = Path("data/chunks.jsonl")
CHROMA_DIR = Path("data/chroma")
COLLECTION = "card_docs"
MODEL_NAME = "BAAI/bge-m3"

CARD_KEY_PREFIX = "card:"


def card_key(card: str) -> str:
    return CARD_KEY_PREFIX + card


def load_model() -> SentenceTransformer:
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    model = SentenceTransformer(MODEL_NAME, device=device)
    model.max_seq_length = 1024  # 청크가 최대 ~800자라 충분
    return model


def to_metadata(chunk: dict) -> dict:
    meta = {
        "section_no": chunk["section_no"] or 0,
        "section_title": chunk["section_title"],
        "subsection": chunk["subsection"] or "",
        "is_common": chunk["is_common"],
        "cards": ", ".join(chunk["cards"]),
        "pages_by_card": json.dumps(chunk["pages_by_card"], ensure_ascii=False),
        "embed_text": chunk["embed_text"],
    }
    for card in chunk["cards"]:
        meta[card_key(card)] = True
    return meta


def main():
    chunks = [json.loads(l) for l in CHUNKS_PATH.open(encoding="utf-8")]

    model = load_model()
    embeddings = model.encode(
        [c["embed_text"] for c in chunks],
        batch_size=16,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    if COLLECTION in [c.name for c in client.list_collections()]:
        client.delete_collection(COLLECTION)  # 매번 전체 재색인
    collection = client.create_collection(
        COLLECTION,
        configuration={"hnsw": {"space": "cosine"}},
        metadata={"embedding_model": MODEL_NAME},
    )
    collection.add(
        ids=[c["id"] for c in chunks],
        embeddings=embeddings.tolist(),
        documents=[c["text"] for c in chunks],
        metadatas=[to_metadata(c) for c in chunks],
    )
    print(f"{collection.count()}개 청크 저장 → {CHROMA_DIR} (collection={COLLECTION}, dim={embeddings.shape[1]})")


if __name__ == "__main__":
    main()
