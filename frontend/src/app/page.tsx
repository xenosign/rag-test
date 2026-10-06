"use client";

import { useEffect, useRef, useState } from "react";
import { Answer } from "@/components/Answer";
import { CardFilter, type Filter, filterToRequest } from "@/components/CardFilter";
import { Sources } from "@/components/Sources";
import { fetchCards, streamChat, type Hit } from "@/lib/api";

type Message =
  | { id: number; role: "user"; content: string }
  | {
      id: number;
      role: "assistant";
      content: string;
      hits: Hit[];
      searchedCards: string[] | null;
      status: "searching" | "streaming" | "done" | "error" | "stopped";
      error?: string;
    };

const EXAMPLES = [
  "제네시스 카드 공항 라운지 몇 번 쓸 수 있어?",
  "해외 결제 수수료율이 카드마다 어떻게 달라?",
  "알파벳카드S BOLD 연회비랑 주요 혜택 알려줘",
  "카드 해지하면 남은 연회비 돌려받을 수 있어?",
];

export default function Home() {
  const [cards, setCards] = useState<string[]>([]);
  const [filter, setFilter] = useState<Filter>({ mode: "auto" });
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [openSources, setOpenSources] = useState<Record<number, number | null>>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const nextId = useRef(0);
  const stickToBottom = useRef(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    // 백엔드는 시작 시 임베딩 모델을 로드하느라 수십 초 걸릴 수 있으므로 연결될 때까지 재시도
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const load = (attempt: number) =>
      fetchCards()
        .then((list) => {
          if (cancelled) return;
          setCards(list);
          setServerError(null);
        })
        .catch(() => {
          if (cancelled) return;
          if (attempt >= 2) {
            setServerError("API 서버에 연결하는 중입니다… 계속되면 백엔드(uvicorn)가 실행 중인지 확인하세요.");
          }
          timer = setTimeout(() => load(attempt + 1), 2000);
        });
    load(0);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, []);

  useEffect(() => {
    // 위로 올려 읽는 중이면 답변 스트리밍에 끌려 내려가지 않도록, 바닥 근처에 있을 때만 따라간다
    if (stickToBottom.current) bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages]);

  const updateAssistant = (id: number, patch: (m: Extract<Message, { role: "assistant" }>) => Partial<Message>) =>
    setMessages((prev) =>
      prev.map((m) => (m.id === id && m.role === "assistant" ? ({ ...m, ...patch(m) } as Message) : m)),
    );

  async function send(question: string) {
    question = question.trim();
    if (!question || busy) return;
    stickToBottom.current = true; // 새 질문을 보내면 다시 바닥을 따라간다
    const userId = nextId.current++;
    const assistantId = nextId.current++;
    setMessages((prev) => [
      ...prev,
      { id: userId, role: "user", content: question },
      { id: assistantId, role: "assistant", content: "", hits: [], searchedCards: null, status: "searching" },
    ]);
    setInput("");

    const controller = new AbortController();
    abortRef.current = controller;
    setBusy(true);
    try {
      await streamChat(
        question,
        filterToRequest(filter),
        (event) => {
          if (event.type === "sources") {
            updateAssistant(assistantId, () => ({ hits: event.hits, searchedCards: event.cards, status: "streaming" }));
          } else if (event.type === "delta") {
            updateAssistant(assistantId, (m) => ({ content: m.content + event.text }));
          } else if (event.type === "error") {
            updateAssistant(assistantId, () => ({ status: "error", error: event.message }));
          } else if (event.type === "done") {
            updateAssistant(assistantId, (m) => ({ status: m.status === "error" ? "error" : "done" }));
          }
        },
        controller.signal,
      );
      // done 이벤트 없이 스트림이 끝났다면 서버 쪽에서 연결이 끊긴 것
      updateAssistant(assistantId, (m) =>
        m.status === "searching" || m.status === "streaming"
          ? { status: "error", error: "서버와의 연결이 끊겼습니다. 다시 시도해 주세요." }
          : {},
      );
    } catch (e) {
      if (controller.signal.aborted) {
        updateAssistant(assistantId, () => ({ status: "stopped" }));
      } else {
        updateAssistant(assistantId, () => ({
          status: "error",
          error: e instanceof Error ? e.message : "알 수 없는 오류",
        }));
      }
    } finally {
      abortRef.current = null;
      setBusy(false);
      textareaRef.current?.focus();
    }
  }

  return (
    <div className="mx-auto flex h-dvh w-full max-w-3xl flex-col">
      <header className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
        <div className="min-w-0">
          <h1 className="text-[17px] font-semibold">카드 상품설명서 Q&amp;A</h1>
          <p className="truncate text-[12px] text-muted">현대카드 10종 상품설명서를 근거로 답합니다</p>
        </div>
        <CardFilter cards={cards} value={filter} onChange={setFilter} />
      </header>

      <main
        className="flex-1 overflow-y-auto px-4 py-6"
        onScroll={(e) => {
          const el = e.currentTarget;
          stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
        }}
      >
        {serverError && (
          <div className="mb-4 rounded-lg border border-danger/40 bg-danger/10 px-4 py-3 text-[14px] text-danger">
            {serverError}
          </div>
        )}

        {messages.length === 0 ? (
          <div className="mt-[12vh] text-center">
            <p className="mb-6 text-[15px] text-muted">궁금한 카드 혜택이나 수수료를 물어보세요</p>
            <div className="mx-auto grid max-w-xl gap-2 sm:grid-cols-2">
              {EXAMPLES.map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => send(q)}
                  className="rounded-xl border border-line bg-surface px-4 py-3 text-left text-[14px] hover:border-accent"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            {messages.map((m) =>
              m.role === "user" ? (
                <div key={m.id} className="flex justify-end">
                  <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-accent px-4 py-2.5 text-[15px] text-white">
                    {m.content}
                  </div>
                </div>
              ) : (
                <div key={m.id} className="rounded-2xl border border-line bg-background px-4 py-3">
                  {m.status !== "searching" && (
                    <div className="mb-2 text-[12px] text-muted">
                      검색 범위:{" "}
                      {m.searchedCards === null || m.searchedCards.length === 0
                        ? "전체 카드"
                        : m.searchedCards.join(", ")}
                    </div>
                  )}
                  {m.status === "searching" && <Pending label="관련 문서를 찾는 중" />}
                  {m.status === "streaming" && !m.content && <Pending label="답변을 작성하는 중" />}
                  {m.content && (
                    <Answer
                      content={m.content}
                      onCite={(index) => setOpenSources((s) => ({ ...s, [m.id]: index }))}
                    />
                  )}
                  {m.status === "stopped" && <p className="mt-2 text-[13px] text-muted">답변을 중단했습니다.</p>}
                  {m.status === "error" && (
                    <p className="mt-2 text-[14px] text-danger">{m.error ?? "오류가 발생했습니다."}</p>
                  )}
                  {m.hits.length > 0 && (
                    <Sources
                      hits={m.hits}
                      open={m.id in openSources}
                      highlight={openSources[m.id] ?? null}
                      onToggle={() =>
                        setOpenSources((s) => {
                          const next = { ...s };
                          if (m.id in next) delete next[m.id];
                          else next[m.id] = null;
                          return next;
                        })
                      }
                    />
                  )}
                </div>
              ),
            )}
          </div>
        )}
        <div ref={bottomRef} />
      </main>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="border-t border-line px-4 pb-4 pt-3"
      >
        <div className="flex items-end gap-2 rounded-2xl border border-line bg-surface p-2 focus-within:border-accent">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              // 한글 IME 조합 중 Enter 는 글자 확정이므로 전송하지 않음
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                send(input);
              }
            }}
            rows={1}
            placeholder="질문을 입력하세요"
            title="Enter 전송 · Shift+Enter 줄바꿈"
            className="field-sizing-content max-h-40 min-h-10 flex-1 resize-none bg-transparent px-2 py-2 text-[15px] outline-none placeholder:text-muted"
            autoFocus
          />
          {busy ? (
            <button
              type="button"
              onClick={() => abortRef.current?.abort()}
              className="h-10 shrink-0 rounded-xl border border-line px-4 text-[14px] hover:border-danger hover:text-danger"
            >
              중단
            </button>
          ) : (
            <button
              type="submit"
              disabled={!input.trim()}
              className="h-10 shrink-0 rounded-xl bg-accent px-4 text-[14px] font-medium text-white disabled:opacity-40"
            >
              보내기
            </button>
          )}
        </div>
      </form>
    </div>
  );
}

function Pending({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2 text-[14px] text-muted" role="status">
      <span className="flex gap-1">
        <span className="size-1.5 animate-bounce rounded-full bg-current [animation-delay:-0.3s]" />
        <span className="size-1.5 animate-bounce rounded-full bg-current [animation-delay:-0.15s]" />
        <span className="size-1.5 animate-bounce rounded-full bg-current" />
      </span>
      {label}
    </div>
  );
}
