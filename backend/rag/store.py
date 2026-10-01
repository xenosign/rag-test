"""임베딩 모델과 Chroma 컬렉션 (색인 구축·검색 공용).

카드 필터: Chroma 메타데이터는 리스트를 쓸 수 없으므로 카드마다 boolean 키를 둔다
  예) where={"card:제네시스 현대카드": True}
"""
import threading
from functools import lru_cache

import chromadb
import torch
from sentence_transformers import SentenceTransformer

from rag.paths import CHROMA_DIR

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


def chroma_client() -> chromadb.ClientAPI:
    return chromadb.PersistentClient(path=str(CHROMA_DIR))


# 여러 스레드에서 동시에 encode 하면 MPS(Apple GPU)에서 Segmentation fault 로 프로세스가 죽는다.
# FastAPI 는 요청을 스레드풀에서 처리하므로, 모델 로드와 질의 임베딩을 한 번에 하나씩만 실행한다.
# 질의 하나 임베딩은 수십 ms 라 직렬화 비용은 무시할 만하다.
_model_lock = threading.Lock()


@lru_cache
def _get_model() -> SentenceTransformer:
    return load_model()


def get_model() -> SentenceTransformer:
    with _model_lock:
        return _get_model()


def embed_queries(texts: list[str]) -> list[list[float]]:
    model = get_model()
    with _model_lock:
        return model.encode(texts, normalize_embeddings=True).tolist()


@lru_cache
def get_collection() -> chromadb.Collection:
    return chroma_client().get_collection(COLLECTION)
