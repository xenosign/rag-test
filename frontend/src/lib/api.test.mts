// node --test 로 실행 (npm test). Node 의 TypeScript 타입 제거 기능을 쓰므로 별도 의존성 없음
import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { type ChatEvent, streamChat } from "./api.ts";

const realFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = realFetch;
});

/** 응답 본문을 주어진 청크 단위로 흘려보내는 가짜 fetch */
function mockStream(chunks: string[]) {
  globalThis.fetch = async () =>
    new Response(
      new ReadableStream({
        start(controller) {
          for (const chunk of chunks) controller.enqueue(new TextEncoder().encode(chunk));
          controller.close();
        },
      }),
    );
}

async function collect(): Promise<ChatEvent[]> {
  const events: ChatEvent[] = [];
  await streamChat("질문", null, (e) => events.push(e), new AbortController().signal);
  return events;
}

test("LF 로 구분된 이벤트", async () => {
  mockStream(['event: sources\ndata: {"cards":[],"hits":[]}\n\nevent: delta\ndata: {"text":"안녕"}\n\nevent: done\ndata: {}\n\n']);
  assert.deepEqual(await collect(), [
    { type: "sources", cards: [], hits: [] },
    { type: "delta", text: "안녕" },
    { type: "done" },
  ]);
});

test("이벤트가 여러 청크에 걸쳐 나뉘어 와도 이어 붙인다", async () => {
  mockStream(["event: del", 'ta\ndata: {"te', 'xt":"가"}\n', "\nevent: done\ndata: {}\n\n"]);
  assert.deepEqual(await collect(), [{ type: "delta", text: "가" }, { type: "done" }]);
});

test("CRLF 와 CR 줄바꿈, 청크 경계에서 잘린 CRLF", async () => {
  mockStream(['event: delta\r\ndata: {"text":"a"}\r', "\n\r\n", 'event: delta\rdata: {"text":"b"}\r\r', "event: done\r\ndata: {}\r\n\r\n"]);
  assert.deepEqual(await collect(), [
    { type: "delta", text: "a" },
    { type: "delta", text: "b" },
    { type: "done" },
  ]);
});

test("여러 data: 줄은 줄바꿈으로 잇고, 주석 줄은 무시한다", async () => {
  mockStream([': keep-alive\n\nevent: delta\ndata: {"text":\ndata: "c"}\n\nevent: done\ndata:{}\n\n']);
  assert.deepEqual(await collect(), [{ type: "delta", text: "c" }, { type: "done" }]);
});

test("콜론 뒤 공백 하나만 떼고 값 안의 공백은 유지한다", async () => {
  mockStream(['event: delta\ndata:  {"text":"  x  "}\n\n']);
  assert.deepEqual(await collect(), [{ type: "delta", text: "  x  " }]);
});

test("422 응답이면 FastAPI 검증 메시지로 예외를 던진다", async () => {
  globalThis.fetch = async () =>
    Response.json({ detail: [{ msg: "Value error, 알 수 없는 카드: ['x']" }] }, { status: 422 });
  await assert.rejects(collect(), { message: "알 수 없는 카드: ['x']" });
});

test("본문 없는 오류 응답이면 상태 코드로 예외를 던진다", async () => {
  globalThis.fetch = async () => new Response("Internal Server Error", { status: 500 });
  await assert.rejects(collect(), { message: "서버 오류 (500)" });
});
