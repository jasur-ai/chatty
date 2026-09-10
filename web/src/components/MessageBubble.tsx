import { IconCheck, IconCheckDouble, IconDownload } from "../icons";
import type { Message } from "../types";

function fmtTime(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function MediaContent({ msg }: { msg: Message }) {
  const url = msg.media_url;
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

export function MessageBubble({ msg }: { msg: Message }) {
  const hasMedia = msg.media_type !== "none";
  return (
    <div className={`bubble-row ${msg.out ? "out" : "in"}`}>
      <div className={`bubble ${msg.out ? "out" : "in"} ${hasMedia ? "has-media" : ""}`}>
        {hasMedia && (
          <div className="media-box">
            <MediaContent msg={msg} />
          </div>
        )}
        {msg.text && <div className="bubble-text">{msg.text}</div>}
        <div className="bubble-meta">
          <span>{fmtTime(msg.date)}</span>
          {msg.out &&
            (msg.read ? <IconCheckDouble size={15} className="tick read" /> : <IconCheck size={15} className="tick" />)}
        </div>
      </div>
    </div>
  );
}