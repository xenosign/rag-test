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
  let pendingCR = false;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    // SSE 줄바꿈은 \r\n, \r, \n 모두 허용되므로 \n 으로 통일한다.
    // 청크가 \r 로 끝나면 다음 청크의 \n 과 짝일 수 있으니 다음 청크까지 미룬다
    let chunk: string = (pendingCR ? "\r" : "") + value;
    pendingCR = chunk.endsWith("\r");
    if (pendingCR) chunk = chunk.slice(0, -1);
    buffer += chunk.replace(/\r\n?/g, "\n");
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

/** SSE 필드 값: 콜론 뒤 공백은 하나만 떼어 낸다 */
function fieldValue(line: string, name: string): string {
  const value = line.slice(name.length + 1);
  return value.startsWith(" ") ? value.slice(1) : value;
}

function parseEvent(raw: string): ChatEvent | null {
  let type = "";
  const data: string[] = [];
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) type = fieldValue(line, "event").trim();
    else if (line.startsWith("data:")) data.push(fieldValue(line, "data"));
    // ":" 로 시작하는 주석(프록시 keep-alive 등)과 그 밖의 필드는 무시
  }
  if (!type) return null;
  // 여러 data: 줄은 줄바꿈으로 이어 하나의 값이 된다
  const payload = data.join("\n");
  return { type, ...(payload ? JSON.parse(payload) : {}) } as ChatEvent;
}
