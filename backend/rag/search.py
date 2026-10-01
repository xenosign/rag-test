"""질문에서 카드명을 감지해 필터를 걸고 Chroma 에서 관련 청크를 검색한다.

사용:
    python -m rag.search "제네시스 카드 라운지 몇 번 쓸 수 있어?"
    python -m rag.search -k 3 --no-filter "해외 결제 수수료율"
"""
import argparse
import re

from rag.store import card_key, embed_queries, get_collection

GREEN = "the Green Edition4"
PINK = "the Pink Edition3"
HAENGBOK = "국민행복 현대카드"
KYOWON = "교원웰스 현대카드"
NEXEN = "넥센타이어 현대카드"
GENESIS = "제네시스 현대카드"
HONORS = "제네시스 현대카드 the Honors"
ALPHA_D = "알파벳카드D BOLD"
ALPHA_S = "알파벳카드S BOLD"
ALPHA_T = "알파벳카드T BOLD"

ALL_CARDS = [GREEN, PINK, HAENGBOK, KYOWON, NEXEN, GENESIS, HONORS, ALPHA_D, ALPHA_S, ALPHA_T]

# 공백 제거·소문자로 정규화한 질문에서 찾을 별칭
ALIASES = {
    GREEN: ["green", "그린"],
    PINK: ["pink", "핑크"],
    HAENGBOK: ["국민행복"],
    KYOWON: ["교원", "웰스"],
    NEXEN: ["넥센"],
    HONORS: ["honors", "아너스"],
    ALPHA_D: ["알파벳카드d", "알파벳d", "dbold", "디볼드"],
    ALPHA_S: ["알파벳카드s", "알파벳s", "sbold", "에스볼드"],
    ALPHA_T: ["알파벳카드t", "알파벳t", "tbold", "티볼드"],
}


def detect_cards(query: str) -> list[str]:
    """질문에 언급된 카드 목록. 상위 이름만 언급되면 해당 계열 전체."""
    q = re.sub(r"\s", "", query).lower()
    found = [card for card, aliases in ALIASES.items() if any(a in q for a in aliases)]
    # "제네시스" 만 있고 Honors 언급이 없으면 두 카드 모두(어느 쪽인지 모호)
    if "제네시스" in q and HONORS not in found:
        found += [GENESIS, HONORS]
    # "알파벳" 만 있고 D/S/T 지정이 없으면 세 카드 모두
    if "알파벳" in q and not {ALPHA_D, ALPHA_S, ALPHA_T} & set(found):
        found += [ALPHA_D, ALPHA_S, ALPHA_T]
    return list(dict.fromkeys(found))


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
