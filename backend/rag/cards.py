"""카드 목록과 질문 속 카드명 감지 (검색 필터·프롬프트 공용).

무거운 의존성(torch, chromadb) 없이 import 할 수 있도록 rag.search 에서 분리했다.
"""
import re

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

# 별칭을 포함하지만 카드명이 아닌 단어. 별칭 검사 전에 질문에서 지운다
# 예) "그린피 할인" 이 the Green Edition4 로 필터되면 골프 혜택이 있는 다른 카드가 빠진다
NOT_CARD_WORDS = re.compile(r"그린피|greenfee")

# 공백 제거·소문자 질문에서 Honors 카드의 전체 이름 ("제네시스아너스", "제네시스현대카드thehonors" 등)
HONORS_NAME = re.compile(r"제네시스(현대)?(카드)?(the|더)?(honors|아너스)")


def detect_cards(query: str) -> list[str]:
    """질문에 언급된 카드 목록. 상위 이름만 언급되면 해당 계열 전체."""
    q = NOT_CARD_WORDS.sub("", re.sub(r"\s", "", query).lower())
    found = [card for card, aliases in ALIASES.items() if any(a in q for a in aliases)]
    # "제네시스 (현대카드) 아너스" 처럼 Honors 카드명의 일부인 "제네시스" 를 빼고도 "제네시스" 가 남으면
    # 일반 제네시스 카드도 언급된 것 (예: "제네시스 현대카드랑 아너스 비교")
    if "제네시스" in HONORS_NAME.sub("", q):
        found.append(GENESIS)
        # Honors 언급이 없으면 어느 쪽인지 모호하므로 두 카드 모두
        if HONORS not in found:
            found.append(HONORS)
    # "알파벳" 만 있고 D/S/T 지정이 없으면 세 카드 모두
    if "알파벳" in q and not {ALPHA_D, ALPHA_S, ALPHA_T} & set(found):
        found += [ALPHA_D, ALPHA_S, ALPHA_T]
    return list(dict.fromkeys(found))
