# 카드 상품설명서 RAG

현대카드 상품설명서 PDF 10종을 근거로 질문에 답하는 RAG 데모입니다.

```
backend/                 Python — 데이터 파이프라인 + FastAPI 서버
├── pyproject.toml
├── server.py            API 서버 (GET /api/cards, POST /api/chat → SSE)
├── rag/                 서버·CLI 공용: 경로, 임베딩/벡터 DB, 검색, 답변 생성
├── pipeline/            데이터 구축: extract → prepare → chunk → index
├── eval/                검색 품질 평가 (retrieval.jsonl)
└── data/                card-data(PDF), extracted, documents/chunks.jsonl, chroma(무시됨)
frontend/                Next.js 16 채팅 페이지
```

## 설치

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -e .
echo "ANTHROPIC_API_KEY=..." > .env   # Claude API 키

cd ../frontend
npm install
```

## 데이터 구축 (처음 한 번, PDF 가 바뀌면 다시)

`backend/` 에서 실행합니다. 첫 `index` 실행 시 임베딩 모델(BAAI/bge-m3, 약 2.2GB)을 내려받습니다.

```bash
.venv/bin/python -m pipeline.extract   # PDF → data/extracted/
.venv/bin/python -m pipeline.prepare   # → data/documents.jsonl (섹션 분할·중복 제거)
.venv/bin/python -m pipeline.chunk     # → data/chunks.jsonl
.venv/bin/python -m pipeline.index     # → data/chroma/ (벡터 DB)
```

## 실행

```bash
# 터미널 1 — API (backend/ 에서)
.venv/bin/uvicorn server:app --port 8000

# 터미널 2 — 웹 (frontend/ 에서)
npm run dev
```

http://localhost:3000 에서 사용합니다. 배포 시 백엔드에 `CORS_ORIGINS`, 프론트엔드에 `NEXT_PUBLIC_API_URL` 을 설정하세요.

## CLI · 평가 (`backend/` 에서)

```bash
.venv/bin/python -m rag.search "넥센타이어 해외 수수료"      # 검색 결과만
.venv/bin/python -m rag.answer "제네시스 라운지 몇 번?"     # 답변 생성
.venv/bin/python -m eval.eval_retrieval                    # 검색 품질 (hit@k, MRR)
```
