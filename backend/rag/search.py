"""질문에서 카드명을 감지해 필터를 걸고 Chroma 에서 관련 청크를 검색한다.

사용:
    python -m rag.search "제네시스 카드 라운지 몇 번 쓸 수 있어?"
    python -m rag.search -k 3 --no-filter "해외 결제 수수료율"
"""
import argparse

from rag.cards import detect_cards
from rag.store import card_key, embed_queries, get_collection


def search(query: str, k: int = 5, cards: list[str] | None = None, auto_filter: bool = True) -> list[dict]:
    """cards 를 주지 않으면 질문에서 감지한다. 필터 시 해당 카드 청크 + 전체 공통 청크만 검색."""
    if cards is None and auto_filter:
        cards = detect_cards(query)
    where = None
    if cards:
        where = {"$or": [{card_key(c): True} for c in cards] + [{"is_common": True}]}

    embedding = embed_queries([query])
    result = get_collection().query(query_embeddings=embedding, n_results=k, where=where)
    return [
        {
            "id": id_,
            "score": 1 - dist,
            "text": doc,
            "cards": meta["cards"],
            "is_common": meta["is_common"],
            "section_title": meta["section_title"],
            "subsection": meta["subsection"],
            "embed_text": meta["embed_text"],
        }
        for id_, dist, doc, meta in zip(
            result["ids"][0], result["distances"][0], result["documents"][0], result["metadatas"][0]
        )
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("-k", type=int, default=5)
    parser.add_argument("--no-filter", action="store_true", help="카드명 자동 필터 끄기")
    args = parser.parse_args()

    if not args.no_filter:
        print(f"감지된 카드: {detect_cards(args.query) or '없음(전체 검색)'}")
    for i, hit in enumerate(search(args.query, k=args.k, auto_filter=not args.no_filter), 1):
        cards = "모든 카드 공통" if hit["is_common"] else hit["cards"]
        heading = " > ".join(filter(None, [hit["section_title"], hit["subsection"]]))
        print(f"\n[{i}] {hit['score']:.3f} {hit['id']}  [{cards}] {heading}")
        print("    " + hit["text"][:200].replace("\n", "\n    "))


if __name__ == "__main__":
    main()
