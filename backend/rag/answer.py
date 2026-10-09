"""검색된 청크를 근거로 Claude 가 질문에 답한다.

사용:
    python -m rag.answer "제네시스 카드 라운지 몇 번 쓸 수 있어?"
    python -m rag.answer            # 대화형
API 키는 backend/.env 의 ANTHROPIC_API_KEY 에서 읽는다.
"""
import argparse
import sys
from collections.abc import AsyncIterator

import anthropic
from dotenv import load_dotenv

from rag.paths import ENV_PATH
from rag.cards import ALL_CARDS, detect_cards
from rag.search import search

load_dotenv(ENV_PATH)

MODEL = "claude-opus-5-5"
TOP_K = 5

# 전체 카드 목록을 알려 주지 않으면, 모든 카드를 다 나열하고도 빠진 카드가 있는지 알 수 없어
# "나열되지 않은 카드는 확인되지 않습니다" 같은 불필요한 단서를 덧붙인다
SYSTEM_PROMPT = f"""당신은 현대카드 상품설명서를 근거로 고객 질문에 답하는 상담 도우미입니다.

상품설명서가 있는 카드는 다음 {len(ALL_CARDS)}종이 전부입니다: {", ".join(ALL_CARDS)}

<documents> 안의 문서 발췌만 근거로 답하세요. 각 문서의 cards 속성은 그 내용이 적용되는 카드이며, "모든 카드 공통"은 위 {len(ALL_CARDS)}종 전체에 적용됩니다.

- 질문한 내용이 문서에 없으면 추측하지 말고 "제공된 설명서에서 확인되지 않습니다"라고 답하세요. 이 문장은 사용자가 물어본 것 중 실제로 근거가 없는 부분에만 쓰세요. 답변이 질문 대상 카드를 모두 다뤘다면 다른 카드에 대한 단서를 덧붙이지 마세요.
- 일부 카드만 근거가 없을 때는 "나머지 카드" 같은 표현 대신 해당 카드 이름을 직접 밝히세요.
- 수수료율, 연회비, 적립률, 한도처럼 카드마다 다를 수 있는 값은 반드시 해당 카드의 문서에서 가져오세요. 질문에 카드가 특정되지 않았는데 카드별로 값이 다르면 카드별로 나눠 답하세요.
- 답변의 각 사실 뒤에 근거 문서를 [번호] 형식으로 표시하세요.
- 한국어로 간결하게 답하고, 숫자·조건은 문서 표현 그대로 옮기세요."""


def format_documents(hits: list[dict]) -> str:
    docs = []
    for i, h in enumerate(hits, 1):
        cards = "모든 카드 공통" if h["is_common"] else h["cards"]
        section = " > ".join(filter(None, [h["section_title"], h["subsection"]]))
        docs.append(f'<document index="{i}" cards="{cards}" section="{section}">\n{h["text"]}\n</document>')
    return "<documents>\n" + "\n".join(docs) + "\n</documents>"


REFUSAL_MESSAGE = "요청이 거절되었습니다. 질문을 바꿔서 다시 시도해 주세요."


def user_message(question: str, hits: list[dict], cards: list[str] | None) -> str:
    # 검색 범위를 알려 주지 않으면 "다른 카드는 확인되지 않습니다" 같은 불필요한 단서를 붙인다
    scope = f"검색 대상 카드: {', '.join(cards)} (사용자가 지정했거나 질문에서 언급한 카드)" if cards else "검색 대상 카드: 전체"
    return f"{format_documents(hits)}\n\n{scope}\n질문: {question}"


def request_params(question: str, hits: list[dict], cards: list[str] | None = None) -> dict:
    return {
        "model": MODEL,
        "max_tokens": 16000,
        "betas": ["server-side-fallback-2026-07-01"],
        "fallbacks": "default",  # 안전 분류기가 오탐으로 거절하면 서버에서 대체 모델로 재시도
        "output_config": {"effort": "medium"},
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_message(question, hits, cards)}],
    }


def answer(
    question: str, client: anthropic.Anthropic, k: int = TOP_K, cards: list[str] | None = None
) -> tuple[str, list[dict]]:
    """cards 를 주지 않으면 질문에서 감지한다 (검색 필터와 프롬프트의 검색 범위에 같이 쓰임)."""
    if cards is None:
        cards = detect_cards(question)
    hits = search(question, k=k, cards=cards)
    response = client.beta.messages.create(**request_params(question, hits, cards))
    if response.stop_reason == "refusal":
        return REFUSAL_MESSAGE, hits
    text = "".join(b.text for b in response.content if b.type == "text")
    return text, hits


async def stream_answer(
    question: str, hits: list[dict], client: anthropic.AsyncAnthropic, cards: list[str] | None = None
) -> AsyncIterator[str]:
    """답변 텍스트를 생성되는 대로 내보낸다. 끝내 거절되면 RefusalError.

    서버 측 fallback 이 스트림 도중 일어나도 이미 받은 텍스트는 유효하고 같은 스트림에서 이어진다.
    async 라서 클라이언트가 연결을 끊으면 태스크가 취소되며 Claude API 스트림도 바로 닫힌다.
    """
    async with client.beta.messages.stream(**request_params(question, hits, cards)) as stream:
        async for text in stream.text_stream:
            yield text
        if (await stream.get_final_message()).stop_reason == "refusal":
            raise RefusalError(REFUSAL_MESSAGE)


class RefusalError(Exception):
    pass


def print_answer(question: str, client: anthropic.Anthropic):
    cards = detect_cards(question)
    print(f"\n(검색 필터: {', '.join(cards) if cards else '전체'})")
    text, hits = answer(question, client, cards=cards)
    print(f"\n{text}\n\n근거 문서:")
    for i, h in enumerate(hits, 1):
        cards = "모든 카드 공통" if h["is_common"] else h["cards"]
        section = " > ".join(filter(None, [h["section_title"], h["subsection"]]))
        print(f"  [{i}] {cards} · {section}  ({h['id']}, {h['score']:.2f})")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("question", nargs="?")
    args = parser.parse_args()

    client = anthropic.Anthropic()
    if args.question:
        print_answer(args.question, client)
        return
    print("질문을 입력하세요 (종료: Ctrl+D)")
    for line in sys.stdin:
        if line.strip():
            print_answer(line.strip(), client)
            print("\n> ", end="", flush=True)


if __name__ == "__main__":
    try:
        main()
    except anthropic.AuthenticationError:
        sys.exit("API 키 인증 실패: .env 의 ANTHROPIC_API_KEY 를 확인하세요.")
