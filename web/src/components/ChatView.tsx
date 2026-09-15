import { useCallback, useEffect, useRef, useState } from "react";
import { resolveUrl } from "../env";
import { IconArrowDown, IconBack, IconSpinner } from "../icons";
import { useStore } from "../store";
import type { Message } from "../types";
import { Avatar } from "./Avatar";
import { Composer } from "./Composer";
import { MessageBubble } from "./MessageBubble";

function groupKey(m: Message): string {
  const d = m.date ? new Date(m.date) : new Date();
  return d.toDateString();
}

function DayDivider({ iso }: { iso: string }) {
  const d = new Date(iso);
  const label =
    d.toDateString() === new Date().toDateString()
      ? "Bugun"
      : d.toLocaleDateString("uz-UZ", { day: "numeric", month: "long" });
  return <div className="day-divider">{label}</div>;
}

export function ChatView() {
  const { current, activeDialog, messages, loadingMessages, backToList, loadMore } = useStore();
  const scrollRef = useRef<HTMLDivElement>(null);
  const prevFirstRef = useRef<number | null>(null);
  const stickBottom = useRef(true);
  const [atBottom, setAtBottom] = useState(true);
  const [newCount, setNewCount] = useState(0);
  const lastLenRef = useRef(0);

  const scrollToBottom = useCallback((smooth = true) => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: smooth ? "smooth" : "auto" });
    stickBottom.current = true;
    setAtBottom(true);
    setNewCount(0);
  }, []);

  const onScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const bottom = el.scrollHeight - el.scrollTop - el.clientHeight < 120;
    stickBottom.current = bottom;
    setAtBottom(bottom);
    if (bottom) setNewCount(0);
    if (el.scrollTop < 60) void loadMore();
  }, [loadMore]);

  // Yangi xabar kelganda pastga scroll (faqat pastda bo'lsak)
  useEffect(() => {
    const el = scrollRef.current;
    const added = messages.length - lastLenRef.current;
    lastLenRef.current = messages.length;
    if (el && stickBottom.current) {
      el.scrollTop = el.scrollHeight;
      setNewCount(0);
    } else if (added > 0) {
      // Pastda emasmiz → yangi xabarlar sonini ko'rsatamiz
      setNewCount((c) => c + added);
    }
  }, [messages.length]);

  // Chat ochilganda eng pastga tushish
  useEffect(() => {
    lastLenRef.current = messages.length;
    setNewCount(0);
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeDialog?.id]);

  // Eski xabarlar yuklanganda scroll pozitsiyasini saqlash
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    if (prevFirstRef.current !== null && messages[0] && messages[0].id !== prevFirstRef.current) {
      const prev = el.scrollHeight;
      requestAnimationFrame(() => {
        el.scrollTop = el.scrollHeight - prev;
      });
    }
    prevFirstRef.current = messages[0]?.id ?? null;
  }, [messages]);

  if (!activeDialog) return null;

  const title = activeDialog.title || current?.bot_name || "Chat";

  return (
    <section className="chat-view">
      <header className="chat-header">
        <button className="icon-btn mobile-back" onClick={backToList}>
          <IconBack size={22} />
        </button>
        <Avatar name={title} photo={resolveUrl(activeDialog.photo)} size={40} />
        <div className="chat-header-info">
          <div className="chat-header-title">{title}</div>
          <div className="chat-header-status muted">
            {activeDialog.kind === "bot"
              ? "bot"
              : activeDialog.kind === "group"
                ? "guruh"
                : activeDialog.kind === "channel"
                  ? "kanal"
                  : "oxirgi marta yaqinda"}
          </div>
        </div>
      </header>

      <div className="messages-wrap">
        <div className="messages" ref={scrollRef} onScroll={onScroll}>
          {loadingMessages && (
            <div className="messages-loading">
              <IconSpinner size={18} />
              <span>Yuklanmoqda…</span>
            </div>
          )}
          {messages.map((m, i) => {
            const prev = messages[i - 1];
            const showDay = !prev || groupKey(prev) !== groupKey(m);
            return (
              <div key={m.id}>
                {showDay && <DayDivider iso={m.date ?? new Date().toISOString()} />}
                <MessageBubble msg={m} />
              </div>
            );
          })}
        </div>

        {/* Pastga tushirish tugmasi (Telegram'dagidek) */}
        <button
          className={`jump-down ${atBottom ? "hidden" : ""}`}
          onClick={() => scrollToBottom()}
          title="Oxirgi xabarlarga o'tish"
          aria-label="Oxirgi xabarlarga o'tish"
        >
          <IconArrowDown size={20} />
          {newCount > 0 && <span className="jump-badge">{newCount > 99 ? "99+" : newCount}</span>}
        </button>
      </div>

      <Composer />
    </section>
  );
}
