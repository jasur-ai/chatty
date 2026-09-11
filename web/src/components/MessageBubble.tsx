import { useState } from "react";
import { api } from "../api";
import { resolveUrl } from "../env";
import { IconCheck, IconCheckDouble, IconDownload, IconEdit, IconReply, IconStar, IconTrash, IconX } from "../icons";
import { useStore } from "../store";
import type { Message } from "../types";

function fmtTime(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function MediaContent({ msg }: { msg: Message }) {
  const url = resolveUrl(msg.media_url);
  if (!url) {
    return <div className="media-placeholder"><span>Media</span></div>;
  }
  switch (msg.media_type) {
    case "photo":
      return <img src={url} alt="Rasm" className="media-img" loading="lazy" />;
    case "video":
      return (
        <video src={url} controls className="media-img" preload="metadata" />
      );
    case "round":
      return (
        <video
          src={url}
          controls
          playsInline
          className="media-round"
          preload="metadata"
        />
      );
    case "voice":
    case "audio":
      return <audio src={url} controls className="media-audio" preload="metadata" />;
    case "gif":
      return <img src={url} alt="GIF" className="media-img" loading="lazy" />;
    case "file":
    default:
      return (
        <a className="file-chip" href={url} download target="_blank" rel="noreferrer">
          <IconDownload size={20} />
          <span>Fayl</span>
        </a>
      );
  }
}

const REACTIONS = ["👍", "❤️", "🔥", "😮", "😢", "🎉"];

export function MessageBubble({ msg }: { msg: Message }) {
  const { current, token, activeDialog, appUser, setReplyTo } = useStore();
  const [menuOpen, setMenuOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState("");
  const [reacting, setReacting] = useState(false);
  const hasMedia = msg.media_type !== "none";
  const isVip = !!appUser?.is_vip || !!appUser?.is_owner || !!appUser?.is_admin;

  async function act(fn: () => Promise<unknown>) {
    setMenuOpen(false);
    try {
      await fn();
    } catch (e) {
      console.error(e);
    }
  }

  async function saveEdit() {
    if (!current || !token || !activeDialog) return;
    await api.vipEdit(current.id, activeDialog.id, msg.tg_id, editText, token);
    setEditing(false);
  }

  return (
    <div className={`bubble-row ${msg.out ? "out" : "in"}`}>
      <div className={`bubble ${msg.out ? "out" : "in"} ${hasMedia ? "has-media" : ""}`}>
        {msg.reply_to && <div className="reply-ref">javob qilingan xabar</div>}
        {hasMedia && (
          <div className="media-box">
            <MediaContent msg={msg} />
          </div>
        )}
        {editing ? (
          <div className="edit-box">
            <input className="input" value={editText} onChange={(e) => setEditText(e.target.value)} autoFocus />
            <button className="btn primary" onClick={() => void saveEdit()}>Saqlash</button>
            <button className="btn ghost" onClick={() => setEditing(false)}>Bekor</button>
          </div>
        ) : (
          msg.text && <div className="bubble-text">{msg.text}</div>
        )}
        <div className="bubble-meta">
          <span>{fmtTime(msg.date)}</span>
          {msg.out &&
            (msg.read ? <IconCheckDouble size={15} className="tick read" /> : <IconCheck size={15} className="tick" />)}
        </div>
      </div>

      <div className="msg-actions">
        <button className="mini-btn" title="Javob berish" onClick={() => setReplyTo(msg)}>
          <IconReply size={15} />
        </button>
        {isVip && !editing && (
          <>
            <button className="mini-btn" title="Harakatlar" onClick={() => setMenuOpen((v) => !v)}>
              <IconStar size={14} />
            </button>
            {menuOpen && (
              <div className="msg-menu">
                {msg.out && (
                  <button onClick={() => { setEditing(true); setEditText(msg.text); setMenuOpen(false); }}>
                    <IconEdit size={15} /> Tahrirlash
                  </button>
                )}
                {msg.out && (
                  <button onClick={() => act(() => api.vipDelete(current!.id, activeDialog!.id, msg.tg_id, token!))}>
                    <IconTrash size={15} /> O'chirish
                  </button>
                )}
                <button onClick={() => { setReacting((v) => !v); setMenuOpen(false); }}>
                  <IconStar size={15} /> Reaksiya
                </button>
                <button
                  onClick={() =>
                    act(() => api.vipStar(current!.id, { dialog_id: activeDialog!.id, tg_id: msg.tg_id, text: msg.text, dialog_title: activeDialog!.title }, token!))
                  }
                >
                  <IconStar size={15} /> Yulduzcha
                </button>
              </div>
            )}
            {reacting && (
              <div className="reaction-bar">
                {REACTIONS.map((r) => (
                  <button key={r} onClick={() => { void act(() => api.vipReact(current!.id, activeDialog!.id, msg.tg_id, r, token!)); setReacting(false); }}>
                    {r}
                  </button>
                ))}
                <button onClick={() => setReacting(false)}><IconX size={14} /></button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
