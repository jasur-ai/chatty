import { useEffect, useRef, useState } from "react";
import { resolveUrl } from "../env";
import { IconBack, IconBot, IconSend, IconSpinner } from "../icons";
import { useStore } from "../store";
import { Avatar } from "./Avatar";

function fmtTime(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function DelegateView() {
  const {
    delegateDialogs,
    delegateLoading,
    activeDelegateDialog,
    openDelegateDialog,
    setView,
  } = useStore();

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <header className="sidebar-header">
          <div className="account-switch">
            <button className="icon-btn" title="Chatlarga qaytish" onClick={() => setView("chats")}>
              <IconBack size={22} />
            </button>
            <span className="sidebar-title">Bot suhbatlari</span>
          </div>
          <div className="delegate-hint">Begonalar @chattiey_bot'ga yozadi</div>
        </header>

        <div className="chat-list">
          {delegateLoading && (
            <div className="skeleton-list">
              {Array.from({ length: 6 }).map((_, i) => (
                <div className="skeleton" key={i}>
                  <div className="skeleton-avatar" />
                  <div className="skeleton-body">
                    <div className="skeleton-line" />
                    <div className="skeleton-line-sm" />
                  </div>
                </div>
              ))}
            </div>
          )}
          {!delegateLoading && delegateDialogs.length === 0 && (
            <div className="list-status muted">Hozircha hech kim yozmagan</div>
          )}
          {delegateDialogs.map((d) => (
            <button
              key={d.id}
              className={`chat-item ${activeDelegateDialog?.id === d.id ? "active" : ""}`}
              onClick={() => void openDelegateDialog(d)}
            >
              <Avatar name={d.first_name || d.username || "?"} size={54} />
              <div className="chat-item-body">
                <div className="chat-item-top">
                  <span className="chat-item-title">{d.first_name || d.username || "Foydalanuvchi"}</span>
                  {d.last_msg_date && <span className="chat-item-time">{fmtTime(d.last_msg_date)}</span>}
                </div>
                <div className="chat-item-bottom">
                  <span className="chat-item-last">
                    {d.last_out ? "Siz: " : ""}
                    {d.last_msg_text || ""}
                  </span>
                  {d.unread_count > 0 && <span className="unread-badge">{d.unread_count}</span>}
                </div>
              </div>
            </button>
          ))}
        </div>
      </aside>

      {activeDelegateDialog ? (
        <DelegateChat />
      ) : (
        <div className="chat-empty delegate-empty">
          <IconBot size={48} />
          <div>Suhbat tanlang</div>
          <div className="muted">Begona odamlar botga yozganda shu yerda ko'rinadi</div>
        </div>
      )}
    </div>
  );
}

function DelegateChat() {
  const { activeDelegateDialog, delegateMessages, delegateMessagesLoading, delegateBack, delegateSend } = useStore();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [delegateMessages.length, activeDelegateDialog?.id]);

  async function send() {
    const t = text.trim();
    if (!t || busy) return;
    setBusy(true);
    setError("");
    setText("");
    try {
      await delegateSend(t);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!activeDelegateDialog) return null;
  const name = activeDelegateDialog.first_name || activeDelegateDialog.username || "Foydalanuvchi";

  return (
    <section className="chat-view">
      <header className="chat-header">
        <button className="icon-btn mobile-back" onClick={delegateBack}>
          <IconBack size={22} />
        </button>
        <Avatar name={name} size={40} />
        <div className="chat-header-info">
          <div className="chat-header-title">{name}</div>
          <div className="chat-header-status muted">
            {activeDelegateDialog.username ? `@${activeDelegateDialog.username}` : "bot orqali suhbat"}
          </div>
        </div>
        <span className="badge badge-admin">Bot vakili</span>
      </header>

      <div className="messages" ref={scrollRef}>
        {delegateMessagesLoading && (
          <div className="messages-loading">
            <IconSpinner size={18} />
            <span>Yuklanmoqda…</span>
          </div>
        )}
        {delegateMessages.map((m) => (
          <div key={m.id} className={`bubble-row ${m.direction === "out" ? "out" : "in"}`}>
            <div className={`bubble ${m.direction === "out" ? "out" : "in"}`}>
              {m.media_url && m.media_type === "photo" && (
                <img className="bubble-media" src={resolveUrl(m.media_url)} alt="rasm" />
              )}
              {m.media_url && m.media_type === "voice" && (
                <audio className="bubble-media" src={resolveUrl(m.media_url)} controls />
              )}
              {m.media_url && (m.media_type === "video" || m.media_type === "round" || m.media_type === "gif") && (
                <video className="bubble-media" src={resolveUrl(m.media_url)} controls />
              )}
              {m.media_url && !["photo", "voice", "video", "round", "gif"].includes(m.media_type) && (
                <a className="bubble-file" href={resolveUrl(m.media_url)} target="_blank" rel="noreferrer">
                  Faylni ochish
                </a>
              )}
              {m.text && <div className="bubble-text">{m.text}</div>}
              <div className="bubble-meta">
                {m.date ? new Date(m.date).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : ""}
              </div>
            </div>
          </div>
        ))}
      </div>

      <footer className="composer">
        {error && <div className="composer-error">{error}</div>}
        <div className="composer-row">
          <textarea
            className="composer-input"
            placeholder="Javob yozish... (bot nomidan ketadi)"
            rows={1}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void send();
              }
            }}
          />
          <button className="btn send" disabled={!text.trim() || busy} onClick={() => void send()} title="Yuborish">
            <IconSend size={22} />
          </button>
        </div>
      </footer>
    </section>
  );
}
