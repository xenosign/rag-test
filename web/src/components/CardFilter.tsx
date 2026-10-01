"use client";

import { useEffect, useRef, useState } from "react";

export type Filter = { mode: "auto" } | { mode: "all" } | { mode: "cards"; cards: string[] };

/** 서버 요청용: null = 자동 감지, [] = 전체, [...] = 지정 카드 */
export function filterToRequest(filter: Filter): string[] | null {
  if (filter.mode === "auto") return null;
  if (filter.mode === "all") return [];
  return filter.cards;
}

export function filterLabel(filter: Filter): string {
  if (filter.mode === "auto") return "자동 감지";
  if (filter.mode === "all") return "전체 카드";
  return filter.cards.length === 1 ? filter.cards[0] : `카드 ${filter.cards.length}종`;
}

export function CardFilter({
  cards,
  value,
  onChange,
}: {
  cards: string[];
  value: Filter;
  onChange: (filter: Filter) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const selected = value.mode === "cards" ? value.cards : [];
  const toggleCard = (card: string) => {
    const next = selected.includes(card) ? selected.filter((c) => c !== card) : [...selected, card];
    onChange(next.length ? { mode: "cards", cards: next } : { mode: "auto" });
  };

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex max-w-[55vw] shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border border-line bg-surface px-3 py-1.5 text-[13px] hover:border-accent"
        aria-haspopup="dialog"
        aria-label={`검색 범위: ${filterLabel(value)}`}
        aria-expanded={open}
      >
        <span className="hidden text-muted sm:inline">검색 범위</span>
        <span className="truncate font-medium">{filterLabel(value)}</span>
        <span className="text-muted">▾</span>
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="검색 범위 선택"
          className="absolute right-0 z-20 mt-2 w-72 max-w-[calc(100vw-2rem)] rounded-xl border border-line bg-background p-2 shadow-lg"
        >
          {(
            [
              ["auto", "자동 감지", "질문에 나온 카드명으로 범위를 정합니다"],
              ["all", "전체 카드", "카드 구분 없이 모든 문서에서 찾습니다"],
            ] as const
          ).map(([mode, label, desc]) => (
            <button
              key={mode}
              type="button"
              onClick={() => {
                onChange({ mode });
                setOpen(false);
              }}
              className={`block w-full rounded-lg px-3 py-2 text-left hover:bg-surface ${
                value.mode === mode ? "bg-accent-soft" : ""
              }`}
            >
              <div className="text-[14px] font-medium">{label}</div>
              <div className="text-[12px] text-muted">{desc}</div>
            </button>
          ))}
          <div className="mx-3 mb-1 mt-2 border-t border-line pt-2 text-[12px] text-muted">
            특정 카드만 (공통 안내 포함)
          </div>
          <div className="max-h-64 overflow-auto">
            {cards.map((card) => (
              <label
                key={card}
                className="flex cursor-pointer items-center gap-2 rounded-lg px-3 py-1.5 text-[14px] hover:bg-surface"
              >
                <input
                  type="checkbox"
                  checked={selected.includes(card)}
                  onChange={() => toggleCard(card)}
                  className="accent-[var(--accent)]"
                />
                {card}
              </label>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
