import { IconCheck, IconCheckDouble } from "../icons";
import type { Message } from "../types";

function fmtTime(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

const MEDIA_LABEL: Record<string, string> = {
  photo: "Rasm",
  video: "Video",
  round: "Dumaloq video",
  voice: "Audio xabar",
  audio: "Musiqa",
  sticker: "Stiker",
  gif: "GIF",
  file: "Fayl",
  poll: "So'rov",
};

export function MessageBubble({ msg }: { msg: Message }) {
  const hasMedia = msg.media_type !== "none";
  return (
    <div className={`bubble-row ${msg.out ? "out" : "in"}`}>
      <div className={`bubble ${msg.out ? "out" : "in"} ${hasMedia ? "has-media" : ""}`}>
        {hasMedia && (
          <div className="media-box">
            {msg.media_type === "photo" && msg.media_url && (
              <img src={msg.media_url} alt="Rasm" className="media-img" />
            )}
            {msg.media_type !== "photo" && (
              <div className="media-placeholder">
                <span className="media-label">{MEDIA_LABEL[msg.media_type] ?? "Media"}</span>
                {msg.media_type === "round" && <span className="media-sub">dumaloq video</span>}
              </div>
            )}
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