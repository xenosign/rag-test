"""질문 속 카드명 감지 (rag.cards.detect_cards)."""
import pytest

from rag.cards import (
    ALIASES,
    ALL_CARDS,
    ALPHA_D,
    ALPHA_S,
    ALPHA_T,
    GENESIS,
    GREEN,
    HONORS,
    KYOWON,
    NEXEN,
    PINK,
    detect_cards,
)


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        # 카드명이 없으면 전체 검색
        ("해외 결제 수수료율이 카드마다 어떻게 달라?", []),
        # 공백·대소문자 무시
        ("the Green Edition4 해외서비스 수수료율 알려줘", [GREEN]),
        ("그린 에디션 바우처 받으려면 얼마나 써야 해?", [GREEN]),
        ("핑크 에디션 메탈 플레이트 발급 수수료는?", [PINK]),
        ("교원웰스 카드 렌탈료 할인 한도", [KYOWON]),
        ("넥센 타이어 카드 연회비", [NEXEN]),
        ("그린이랑 핑크 비교", [GREEN, PINK]),
        # 골프 "그린피" 는 Green Edition 이 아님
        ("그린피 할인 되는 카드?", []),
        ("그린 피 할인", []),
        ("Green Fee 할인", []),
        ("the Green Edition4 그린피 할인", [GREEN]),
        # 제네시스만 언급: 일반/Honors 중 어느 쪽인지 모호하므로 둘 다
        ("제네시스 카드 공항 라운지 몇 번 쓸 수 있어?", [GENESIS, HONORS]),
        # Honors 카드명의 일부인 "제네시스" 는 일반 제네시스가 아님
        ("제네시스 아너스 연회비", [HONORS]),
        ("제네시스 현대카드 the Honors 공항 라운지", [HONORS]),
        ("아너스 연회비", [HONORS]),
        # 둘 다 언급
        ("제네시스 현대카드랑 아너스 비교", [HONORS, GENESIS]),
        ("Honors랑 제네시스 비교", [HONORS, GENESIS]),
        ("제네시스 아너스랑 일반 제네시스 차이", [HONORS, GENESIS]),
        # 알파벳: D/S/T 지정이 없으면 세 카드 모두
        ("알파벳카드 연회비", [ALPHA_D, ALPHA_S, ALPHA_T]),
        ("알파벳카드S BOLD 연회비랑 주요 혜택 알려줘", [ALPHA_S]),
        ("알파벳 D 랑 알파벳 T 비교", [ALPHA_D, ALPHA_T]),
        ("D BOLD 적립률", [ALPHA_D]),
    ],
)
def test_detect_cards(question, expected):
    assert detect_cards(question) == expected


def test_no_duplicates():
    assert detect_cards("그린 그린 green Green Edition") == [GREEN]


def test_aliases_are_normalized():
    # detect_cards 는 공백 제거·소문자 질문과 비교하므로 별칭도 그 형태여야 매칭된다
    for card, aliases in ALIASES.items():
        assert card in ALL_CARDS
        for alias in aliases:
            assert alias == alias.lower() and " " not in alias, (card, alias)


def test_every_card_detectable_by_full_name():
    for card in ALL_CARDS:
        assert card in detect_cards(f"{card} 연회비 알려줘"), card
