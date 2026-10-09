# 카드 상품설명서 RAG

현대카드 상품설명서 PDF 10종을 근거로 질문에 답하는 RAG 데모입니다.

```
backend/                 Python — 데이터 파이프라인 + FastAPI 서버
├── pyproject.toml
├── server.py            API 서버 (GET /api/cards, POST /api/chat → SSE)
├── rag/                 서버·CLI 공용: 경로, 임베딩/벡터 DB, 검색, 답변 생성
├── pipeline/            데이터 구축: extract → prepare → chunk → index
├── eval/                검색 품질 평가 (retrieval.jsonl)
├── tests/               pytest — 카드명 감지, 청크 분할, 데이터 산출물 최신 여부
└── data/                card-data(PDF), extracted, documents/chunks.jsonl, chroma(무시됨)
frontend/                Next.js 16 채팅 페이지
```

## 설치

Python 3.11 이상, Node.js 가 필요합니다.

### 백엔드 가상환경

```bash
cd backend
python3 -m venv .venv          # Windows: py -m venv .venv
```

이후 명령은 **가상환경을 활성화한 터미널**에서 실행합니다 (`python`, `pip`, `uvicorn` 이 `.venv` 의 것을 가리킴).

| OS | 활성화 |
|---|---|
| macOS / Linux | `source .venv/bin/activate` |
| Windows PowerShell | `.venv\Scripts\Activate.ps1` |
| Windows Git Bash | `source .venv/Scripts/activate` |

활성화 없이 쓰려면 `python` 대신 `.venv/bin/python` (Windows: `.venv\Scripts\python`) 처럼 경로를 붙입니다.

PowerShell 에서 스크립트 실행이 막혀 있으면 한 번 `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` 를 실행하세요.

### 패키지 설치

```bash
pip install -e .
```

**Windows/Linux + NVIDIA GPU**: PyPI 의 torch 는 Windows 에서 CPU 전용 빌드라 임베딩이 GPU 를 쓰지 못합니다.
`pip install -e .` 전에 [pytorch.org](https://pytorch.org/get-started/locally/) 에서 드라이버에 맞는 CUDA 빌드를 먼저 설치하세요 (예: `pip install torch --index-url https://download.pytorch.org/whl/cu128`).
`python -c "import torch; print(torch.cuda.is_available())"` 가 `True` 면 GPU 를 씁니다. Mac 은 자동으로 MPS 를 씁니다.

### API 키

`backend/.env` 파일을 만들고 Claude API 키를 한 줄 적습니다.

```
ANTHROPIC_API_KEY=...
```

Windows PowerShell 5.1 의 `echo ... > .env` 는 UTF-16 으로 저장돼 읽히지 않으므로 편집기로 만드세요.

### 프론트엔드

```bash
cd ../frontend
npm install
```

## 데이터 구축 (처음 한 번, PDF 가 바뀌면 다시)

`backend/` 에서 가상환경을 활성화하고 실행합니다. 첫 `index` 실행 시 임베딩 모델(BAAI/bge-m3, 약 2.2GB)을 내려받습니다.

```bash
python -m pipeline.extract   # PDF → data/extracted/
python -m pipeline.prepare   # → data/documents.jsonl (섹션 분할·중복 제거)
python -m pipeline.chunk     # → data/chunks.jsonl
python -m pipeline.index     # → data/chroma/ (벡터 DB)
```

## 실행

```bash
# 터미널 1 — API (backend/ 에서, 가상환경 활성화)
uvicorn server:app --port 8000

# 터미널 2 — 웹 (frontend/ 에서)
npm run dev
```

http://localhost:3000 에서 사용합니다. 배포 시 백엔드에 `CORS_ORIGINS`, 프론트엔드에 `NEXT_PUBLIC_API_URL` 을 설정하세요.

## CLI · 평가 (`backend/` 에서, 가상환경 활성화)

```bash
python -m rag.search "넥센타이어 해외 수수료"      # 검색 결과만
python -m rag.answer "제네시스 라운지 몇 번?"     # 답변 생성
python -m eval.eval_retrieval                    # 검색 품질 (hit@k, MRR)
```

## 테스트

```bash
# backend/ 에서 (가상환경 활성화)
pip install -e ".[dev]"
python -m pytest

# frontend/ 에서
npm test             # SSE 파서 (node --test)
npm run lint
npm run typecheck
```

`main` 푸시와 PR 마다 GitHub Actions(`.github/workflows/ci.yml`)가 위 검사를 실행합니다.
백엔드 테스트는 torch·chromadb 없이 돌아가며, `prepare`/`chunk` 코드를 고친 뒤 `data/*.jsonl` 을 다시 만들지 않으면 `test_pipeline_data` 가 실패합니다.
