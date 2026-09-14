import { useState } from "react";
import { api } from "../api";
import { resolveUrl } from "../env";
import { IconCheck, IconCheckDouble, IconDownload, IconEdit, IconReply, IconSpinner, IconStar, IconTrash, IconX } from "../icons";
import { useStore } from "../store";
import type { Message } from "../types";

function fmtTime(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function MediaContent({ msg }: { msg: Message }) {
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const url = resolveUrl(msg.media_url);
  if (!url) {
    return <div className="media-placeholder"><span>Media</span></div>;
  }
  // Media elementni doim ko'rsatamiz (display:none video yuklashni to'xtatadi),
  // ustiga spinner qo'yib, yuklangach yashiramiz.
  switch (msg.media_type) {
    case "photo":
      return (
        <div className="media-wrap">
          {state === "loading" && <div className="media-loading"><IconSpinner size={16} /></div>}
          <img src={url} alt="Rasm" className="media-img" loading="lazy" onLoad={() => setState("ready")} onError={() => setState("error")} />
          {state === "error" && <div className="media-error">Rasm yuklanmadi</div>}
        </div>
      );
    case "video":
      return (
        <div className="media-wrap">
          {state === "loading" && <div className="media-loading"><IconSpinner size={16} /></div>}
          <video src={url} controls className="media-img" preload="auto" onLoadedData={() => setState("ready")} onError={() => setState("error")} />
          {state === "error" && <div className="media-error">Video yuklanmadi</div>}
        </div>
      );
    case "round":
      return (
        <div className="media-wrap">
          {state === "loading" && <div className="media-loading"><IconSpinner size={16} /></div>}
          <video src={url} controls playsInline className="media-round" preload="auto" onLoadedData={() => setState("ready")} onError={() => setState("error")} />
          {state === "error" && <div className="media-error">Video yuklanmadi</div>}
        </div>
      );
    case "voice":
    case "audio":
      return (
        <div className="media-wrap">
          {state === "loading" && <div className="media-loading"><IconSpinner size={16} /></div>}
          <audio src={url} controls className="media-audio" preload="auto" onLoadedData={() => setState("ready")} onError={() => setState("error")} />
          {state === "error" && <div className="media-error">Audio yuklanmadi</div>}
        </div>
      );
    case "gif":
      return (
        <div className="media-wrap">
          {state === "loading" && <div className="media-loading"><IconSpinner size={16} /></div>}
          <img src={url} alt="GIF" className="media-img" loading="lazy" onLoad={() => setState("ready")} onError={() => setState("error")} />
          {state === "error" && <div className="media-error">GIF yuklanmadi</div>}
        </div>
      );
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
  const { current, token, activeDialog, setReplyTo } = useStore();
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState("");
  const [reacting, setReacting] = useState(false);
  const hasMedia = msg.media_type !== "none";

  async function act(fn: () => Promise<unknown>) {
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
          <IconReply size={16} />
        </button>
        {!editing && (
          <>
            {msg.out && (
              <button className="mini-btn" title="Tahrirlash" onClick={() => { setEditing(true); setEditText(msg.text); }}>
                <IconEdit size={16} />
              </button>
            )}
            {msg.out && (
              <button
                className="mini-btn"
                title="O'chirish"
                onClick={() => {
                  if (window.confirm("Xabarni o'chirish?")) {
                    void act(() => api.vipDelete(current!.id, activeDialog!.id, msg.tg_id, token!));
                  }
                }}
              >
                <IconTrash size={16} />
              </button>
            )}
            <button className="mini-btn" title="Reaksiya" onClick={() => setReacting((v) => !v)}>
              <IconStar size={15} />
            </button>
            <button
              className="mini-btn"
              title="Yulduzcha (belgilash)"
              onClick={() =>
                void act(() => api.vipStar(current!.id, { dialog_id: activeDialog!.id, tg_id: msg.tg_id, text: msg.text, dialog_title: activeDialog!.title }, token!))
              }
            >
              <IconStar size={15} />
            </button>
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
