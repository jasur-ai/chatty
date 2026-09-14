import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { resolveUrl } from "../env";
import { IconBack, IconBot, IconMic, IconPlus, IconSend, IconSpinner, IconStory } from "../icons";
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
  const { current, token, activeDelegateDialog, delegateMessages, delegateMessagesLoading, delegateBack, delegateSend } = useStore();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [recording, setRecording] = useState<"voice" | "round" | null>(null);
  const [recSeconds, setRecSeconds] = useState(0);
  const fileRef = useRef<HTMLInputElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const recStartRef = useRef(0);

  useEffect(() => {
    if (!recording) {
      setRecSeconds(0);
      return;
    }
    recStartRef.current = Date.now();
    setRecSeconds(0);
    const t = setInterval(() => {
      setRecSeconds(Math.floor((Date.now() - recStartRef.current) / 1000));
    }, 500);
    return () => clearInterval(t);
  }, [recording]);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [delegateMessages.length, activeDelegateDialog?.id]);

  async function send() {
    const t = text.trim();
    if ((!t && !busy) || busy) return;
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

  async function onFileSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file || !current || !token || busy) return;
    setBusy(true);
    setError("");
    try {
      const up = await api.uploadMedia(current.id, file, token);
      await delegateSend(text.trim(), up.media_key, up.media_type);
      setText("");
    } catch (err) {
      setError((err as Error).message || "Yuborilmadi");
    } finally {
      setBusy(false);
    }
  }

  async function startRecording(kind: "voice" | "round") {
    if (!current || !token || recording) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: kind === "voice",
        video: kind === "round",
      });
      streamRef.current = stream;
      const mime = kind === "voice" ? "audio/webm" : "video/webm";
      const rec = new MediaRecorder(stream, { mimeType: mime });
      chunksRef.current = [];
      rec.ondataavailable = (e) => chunksRef.current.push(e.data);
      rec.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: mime });
        const file = new File([blob], `${kind}-${Date.now()}.webm`, { type: mime });
        setBusy(true);
        try {
          const up = await api.uploadMedia(current!.id, file, token!);
          // kind — "voice" (ovozli xabar) yoki "round" (dumaloq video)
          await delegateSend("", up.media_key, kind);
        } catch (err) {
          setError((err as Error).message);
        } finally {
          setBusy(false);
        }
      };
      rec.start();
      mediaRecorderRef.current = rec;
      setRecording(kind);
    } catch {
      setError("Mikrofon/kamera ruxsati yo'q");
    }
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    mediaRecorderRef.current = null;
    setRecording(null);
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
            {m.direction === "in" && (
              <Avatar name={name} size={34} />
            )}
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
        {recording && (
          <div className="rec-banner">
            <span className="rec-dot" />
            <span>
              {recording === "voice" ? "Ovozli xabar" : "Dumaloq video"} yozilmoqda — {Math.floor(recSeconds / 60)}:{String(recSeconds % 60).padStart(2, "0")}
            </span>
            <button className="btn danger" onClick={stopRecording}>To'xtatish va yuborish</button>
          </div>
        )}
        {error && <div className="composer-error">{error}</div>}
        <div className="composer-row">
          <input
            ref={fileRef}
            type="file"
            accept="image/*,audio/*,video/*"
            style={{ display: "none" }}
            onChange={onFileSelected}
          />
          <button
            className="icon-btn attach"
            title="Rasm/audio/video qo'shish"
            disabled={busy || !!recording}
            onClick={() => fileRef.current?.click()}
          >
            {busy ? <IconSpinner size={22} /> : <IconPlus size={24} />}
          </button>
          <button
            className={`icon-btn attach ${recording === "voice" ? "rec" : ""}`}
            title={recording === "voice" ? "To'xtatish" : "Ovozli xabar"}
            disabled={busy || recording === "round"}
            onClick={() => (recording === "voice" ? stopRecording() : void startRecording("voice"))}
          >
            <IconMic size={22} />
          </button>
          <button
            className={`icon-btn attach ${recording === "round" ? "rec" : ""}`}
            title={recording === "round" ? "To'xtatish" : "Dumaloq video"}
            disabled={busy || recording === "voice"}
            onClick={() => (recording === "round" ? stopRecording() : void startRecording("round"))}
          >
            <IconStory size={22} />
          </button>
          <textarea
            className="composer-input"
            placeholder="Javob yozish... (bot nomidan ketadi)"
            rows={1}
            value={text}
            disabled={busy || !!recording}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void send();
              }
            }}
          />
          <button className="btn send" disabled={(!text.trim() && !busy) || busy || !!recording} onClick={() => void send()} title="Yuborish">
            <IconSend size={22} />
          </button>
        </div>
      </footer>
    </section>
  );
}
