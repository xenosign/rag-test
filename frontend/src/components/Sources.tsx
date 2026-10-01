"use client";

import { useEffect, useRef } from "react";
import type { Hit } from "@/lib/api";

export function Sources({
  hits,
  open,
  onToggle,
  highlight,
}: {
  hits: Hit[];
  open: boolean;
  onToggle: () => void;
  highlight: number | null;
}) {
  const itemRefs = useRef<(HTMLLIElement | null)[]>([]);

  useEffect(() => {
    if (open && highlight) {
      itemRefs.current[highlight - 1]?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [open, highlight]);

  return (
    <div className="mt-3 border-t border-line pt-2">
      <button
        type="button"
        onClick={onToggle}
        className="flex items-center gap-1 text-[13px] text-muted hover:text-foreground"
        aria-expanded={open}
      >
        <span className={`inline-block transition-transform ${open ? "rotate-90" : ""}`}>▸</span>
        근거 문서 {hits.length}개
      </button>
      {open && (
        <ol className="mt-2 space-y-2">
          {hits.map((hit, i) => {
            const heading = [hit.section_title, hit.subsection].filter(Boolean).join(" › ");
            return (
              <li
                key={hit.id}
                ref={(el) => {
                  itemRefs.current[i] = el;
                }}
                className={`rounded-lg border p-3 text-[13px] transition-colors ${
                  highlight === i + 1 ? "border-accent bg-accent-soft" : "border-line bg-surface"
                }`}
              >
                <div className="mb-1 flex flex-wrap items-center gap-x-2 gap-y-1">
                  <span className="font-semibold text-accent">[{i + 1}]</span>
                  <span className="rounded bg-chip px-1.5 py-0.5 text-[12px]">
                    {hit.is_common ? "모든 카드 공통" : hit.cards}
                  </span>
                  <span className="text-muted">{heading}</span>
                  <span className="ml-auto font-mono text-[11px] text-muted">
                    {hit.score.toFixed(2)}
                  </span>
                </div>
                <details>
                  <summary className="cursor-pointer text-muted hover:text-foreground">원문 보기</summary>
                  <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap break-words font-sans text-[12px] leading-5">
                    {hit.text}
                  </pre>
                </details>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
