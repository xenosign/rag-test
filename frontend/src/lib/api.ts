export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Hit = {
  id: string;
  score: number;
  text: string;
  cards: string;
  is_common: boolean;
  section_title: string;
  subsection: string;
};

export type ChatEvent =
  | { type: "sources"; cards: string[]; hits: Hit[] }
  | { type: "delta"; text: string }
  | { type: "error"; message: string }
  | { type: "done" };

export async function fetchCards(): Promise<string[]> {
  const res = await fetch(`${API_URL}/api/cards`);
  if (!res.ok) throw new Error(`카드 목록을 불러오지 못했습니다 (${res.status})`);
  return (await res.json()).cards;
}

/**
 * 질문을 보내고 서버의 SSE 이벤트를 하나씩 넘겨준다.
 * cards: null = 질문에서 자동 감지, [] = 전체 검색, [...] = 지정 카드
 */
export async function streamChat(
  question: string,
  cards: string[] | null,
  onEvent: (event: ChatEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const res = await fetch(`${API_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, cards }),
    signal,
  });
  if (!res.ok || !res.body) throw new Error(await errorMessage(res));

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    // SSE 이벤트는 빈 줄로 구분된다
    let boundary;
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const raw = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const event = parseEvent(raw);
      if (event) onEvent(event);
    }
  }
}

/** FastAPI 422 응답의 detail[].msg 를 꺼내고, 없으면 상태 코드만 */
async function errorMessage(res: Response): Promise<string> {
  try {
    const { detail } = await res.json();
    if (Array.isArray(detail) && detail.length) {
      return detail.map((d: { msg?: string }) => d.msg?.replace(/^Value error, /, "")).join(" / ");
    }
  } catch {}
  return `서버 오류 (${res.status})`;
}

function parseEvent(raw: string): ChatEvent | null {
  let type = "";
  let data = "";
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) type = line.slice(6).trim();
    else if (line.startsWith("data:")) data += line.slice(5).trim();
  }
  if (!type) return null;
  return { type, ...(data ? JSON.parse(data) : {}) } as ChatEvent;
}
