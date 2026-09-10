import { useRef, useState } from "react";
import { api } from "../api";
import { IconPlus, IconSend, IconSpinner } from "../icons";
import { useStore } from "../store";

export function Composer() {
  const { current, token, activeDialog, sendText } = useStore();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  async function doSend() {
    const t = text.trim();
    if ((!t && !uploading) || busy) return;
    setBusy(true);
    setError("");
    setText("");
    try {
      await sendText(t);
    } finally {
      setBusy(false);
    }
  }

  async function onFileSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file || !current || !token || !activeDialog || uploading) return;
    setUploading(true);
    setError("");
    try {
      const up = await api.uploadMedia(current.id, file, token);
      // Media + caption bilan yuboramiz
      await api.send(current.id, activeDialog.id, text.trim(), token, {
        mediaKey: up.media_key,
        mediaType: up.media_type,
      });
      setText("");
    } catch (err) {
      setError((err as Error).message || "Yuborilmadi");
    } finally {
      setUploading(false);
    }
  }

  return (
    <footer className="composer">
      <input
        ref={fileRef}
        type="file"
        accept="image/*,video/*,audio/*,.pdf,.doc,.docx,.xls,.xlsx,.zip,.rar,.txt"
        style={{ display: "none" }}
        onChange={onFileSelected}
      />
      <button
        className="icon-btn attach"
        title="Fayl qo'shish"
        disabled={uploading}
        onClick={() => fileRef.current?.click()}
      >
        {uploading ? <IconSpinner size={22} /> : <IconPlus size={24} />}
      </button>
      <textarea
        className="composer-input"
        placeholder={uploading ? "Yuklanmoqda..." : "Xabar yozish..."}
        rows={1}
        value={text}
        disabled={uploading}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            void doSend();
          }
        }}
      />
      <button
        className="btn send"
        disabled={(!text.trim() && !uploading) || busy}
        onClick={() => void doSend()}
        title="Yuborish"
      >
        <IconSend size={22} />
      </button>
      {error && <div className="composer-error">{error}</div>}
    </footer>
  );
}