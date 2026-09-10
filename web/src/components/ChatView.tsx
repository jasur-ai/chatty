import { useEffect, useRef } from "react";
import { IconBack } from "../icons";
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
  const label = d.toDateString() === new Date().toDateString() ? "Bugun" : d.toLocaleDateString("uz-UZ", { day: "numeric", month: "long" });
  return <div className="day-divider">{label}</div>;
}

export function ChatView() {
  const { current, activeDialog, messages, loadingMessages, backToList, loadMore } = useStore();
  const scrollRef = useRef<HTMLDivElement>(null);
  const prevFirstRef = useRef<number | null>(null);
  const stickBottom = useRef(true);

  // Yangi xabar kelganda pastga scroll
  useEffect(() => {
    const el = scrollRef.current;
    if (el && stickBottom.current) el.scrollTop = el.scrollHeight;
  }, [messages.length]);

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
        <Avatar name={title} size={40} />
        <div className="chat-header-info">
          <div className="chat-header-title">{title}</div>
          <div className="chat-header-status muted">
            {activeDialog.type === "user" ? "oxirgi marta yaqinda" : `${activeDialog.type === "chat" ? "guruh" : "kanal"}`}
          </div>
        </div>
      </header>

      <div
        className="messages"
        ref={scrollRef}
        onScroll={(e) => {
          const el = e.currentTarget;
          stickBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
          if (el.scrollTop < 60) void loadMore();
        }}
      >
        {loadingMessages && (
          <div className="messages-loading">Yuklanmoqda...</div>
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

      <Composer />
    </section>
  );
}