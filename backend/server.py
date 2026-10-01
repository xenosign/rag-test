"""RAG 질의응답 API 서버 (FastAPI).

실행 (backend/ 에서):
    .venv/bin/uvicorn server:app --port 8000 --reload

엔드포인트
- GET  /api/cards  : 검색 필터로 고를 수 있는 카드 목록
- POST /api/chat   : 질문 → SSE 스트림
    event: sources  data: {"cards": [...], "hits": [...]}   검색 결과 (먼저 1회)
    event: delta    data: {"text": "..."}                   답변 조각 (여러 번)
    event: error    data: {"message": "..."}                실패 시
    event: done     data: {}
"""
import json
import os
from collections.abc import Iterator
from contextlib import asynccontextmanager

import anthropic
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from rag.answer import TOP_K, RefusalError, stream_answer
from rag.search import ALL_CARDS, detect_cards, search
from rag.store import get_collection, get_model

ALLOWED_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 첫 질문이 느려지지 않도록 임베딩 모델(~2GB)과 벡터 DB 를 미리 로드
    get_model()
    get_collection()
    app.state.client = anthropic.Anthropic()
    yield


app = FastAPI(title="Card RAG API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    # None: 질문에서 카드명 자동 감지 / []: 필터 없이 전체 검색 / [...]: 지정 카드 + 공통
    cards: list[str] | None = None
    k: int = Field(default=TOP_K, ge=1, le=20)


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def chat_events(req: ChatRequest, client: anthropic.Anthropic) -> Iterator[str]:
    try:
        cards = detect_cards(req.question) if req.cards is None else req.cards
        hits = search(req.question, k=req.k, cards=cards)
        yield sse("sources", {
            "cards": cards,
            "hits": [
                {key: h[key] for key in ("id", "score", "text", "cards", "is_common", "section_title", "subsection")}
                for h in hits
            ],
        })
        for text in stream_answer(req.question, hits, client, cards):
            yield sse("delta", {"text": text})
    except RefusalError as e:
        yield sse("error", {"message": str(e)})
    except anthropic.AuthenticationError:
        yield sse("error", {"message": "API 키 인증에 실패했습니다. 서버의 .env 를 확인하세요."})
    except anthropic.RateLimitError:
        yield sse("error", {"message": "요청이 많아 잠시 제한되었습니다. 잠시 후 다시 시도하세요."})
    except anthropic.APIConnectionError:
        yield sse("error", {"message": "Claude API 에 연결하지 못했습니다."})
    except anthropic.APIStatusError as e:
        yield sse("error", {"message": f"Claude API 오류 ({e.status_code})"})
    yield sse("done", {})


@app.get("/api/cards")
def list_cards() -> dict:
    return {"cards": ALL_CARDS}


@app.post("/api/chat")
def chat(req: ChatRequest) -> StreamingResponse:
    unknown = set(req.cards or []) - set(ALL_CARDS)
    if unknown:
        return StreamingResponse(iter([sse("error", {"message": f"알 수 없는 카드: {sorted(unknown)}"}), sse("done", {})]),
                                 media_type="text/event-stream")
    return StreamingResponse(
        chat_events(req, app.state.client),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
