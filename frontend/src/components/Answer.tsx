"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// 답변 속 근거 표시 [1], [2] 를 클릭 가능한 링크로 바꾼다 (이미 링크인 [텍스트](url) 는 건드리지 않음)
const CITATION = /\[(\d{1,2})\](?!\()/g;

export function Answer({
  content,
  onCite,
}: {
  content: string;
  onCite: (index: number) => void;
}) {
  const markdown = content.replace(CITATION, "[$1](#cite-$1)");
  return (
    <div className="answer text-[15px] leading-7">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a({ href, children }) {
            if (href?.startsWith("#cite-")) {
              const index = Number(href.slice(6));
              return (
                <button
                  type="button"
                  onClick={() => onCite(index)}
                  className="mx-0.5 inline-flex h-[18px] min-w-[18px] -translate-y-px items-center justify-center rounded bg-accent-soft px-1 align-middle text-[11px] font-semibold text-accent hover:bg-accent hover:text-white"
                  aria-label={`근거 문서 ${index} 보기`}
                >
                  {children}
                </button>
              );
            }
            return (
              <a href={href} target="_blank" rel="noreferrer" className="text-accent underline">
                {children}
              </a>
            );
          },
        }}
      >
        {markdown}
      </ReactMarkdown>
    </div>
  );
}
