"""eval/retrieval.jsonl 로 검색 품질을 측정한다 (카드 자동 필터 on/off 비교).

지표: hit@1, hit@3, hit@5 (상위 k 안에 정답 청크가 하나라도 있는 비율), MRR
"""
import json

from rag.paths import EVAL_DIR
from rag.cards import detect_cards
from rag.search import search

EVAL_PATH = EVAL_DIR / "retrieval.jsonl"
K = 5


def evaluate(cases: list[dict], auto_filter: bool, verbose: bool) -> dict:
    hits = {1: 0, 3: 0, 5: 0}
    rr_sum = 0.0
    for case in cases:
        ids = [h["id"] for h in search(case["question"], k=K, auto_filter=auto_filter)]
        rank = next((i for i, id_ in enumerate(ids, 1) if id_ in case["expected"]), None)
        for k in hits:
            hits[k] += rank is not None and rank <= k
        rr_sum += 1 / rank if rank else 0
        if verbose:
            mark = "✅" if rank == 1 else f"#{rank}" if rank else "❌"
            cards = detect_cards(case["question"]) if auto_filter else "-"
            print(f"  {mark:<3} {case['question'][:34]:<36} 필터={cards}")
            if rank != 1:
                print(f"       정답 {case['expected']} / 결과 {ids}")
    n = len(cases)
    return {f"hit@{k}": v / n for k, v in hits.items()} | {"MRR": rr_sum / n}


def main():
    cases = [json.loads(l) for l in EVAL_PATH.open(encoding="utf-8")]
    print(f"질문 {len(cases)}개\n")
    results = {}
    for auto_filter in (False, True):
        label = "카드 필터 ON" if auto_filter else "카드 필터 OFF"
        print(f"=== {label}")
        results[label] = evaluate(cases, auto_filter, verbose=True)
        print()
    print(f"{'':<14}" + "".join(f"{m:>8}" for m in next(iter(results.values()))))
    for label, r in results.items():
        print(f"{label:<14}" + "".join(f"{v:>8.2f}" for v in r.values()))


if __name__ == "__main__":
    main()
