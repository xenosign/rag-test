"""데이터 경로. 실행 위치(cwd)와 무관하게 backend/ 기준으로 잡는다."""
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"

PDF_DIR = DATA_DIR / "card-data"
EXTRACTED_DIR = DATA_DIR / "extracted"
DOCUMENTS_PATH = DATA_DIR / "documents.jsonl"
CHUNKS_PATH = DATA_DIR / "chunks.jsonl"
CHROMA_DIR = DATA_DIR / "chroma"

EVAL_DIR = BACKEND_DIR / "eval"
ENV_PATH = BACKEND_DIR / ".env"
