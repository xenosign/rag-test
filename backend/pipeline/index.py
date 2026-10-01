"""data/chunks.jsonl 을 bge-m3 로 임베딩해 Chroma(data/chroma) 에 저장한다.

- 임베딩 입력: embed_text ("[카드명] 섹션 > 소제목" + 본문)
- document: 본문(text) — LLM 에 넘길 내용
- 카드 필터용 메타데이터: rag/store.py 참고
"""
import json

from rag.paths import CHROMA_DIR, CHUNKS_PATH
from rag.store import COLLECTION, MODEL_NAME, card_key, chroma_client, load_model


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

    client = chroma_client()
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
