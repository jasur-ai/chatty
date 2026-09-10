import { useState } from "react";
import { IconPlus, IconSend } from "../icons";
import { useStore } from "../store";

export function Composer() {
  const { sendText } = useStore();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);

  async function doSend() {
    const t = text.trim();
    if (!t || busy) return;
    setBusy(true);
    setText("");
    try {
      await sendText(t);
    } finally {
      setBusy(false);
    }
  }

  return (
    <footer className="composer">
      <button className="icon-btn attach" title="Ilova qilish">
        <IconPlus size={24} />
      </button>
      <textarea
        className="composer-input"
        placeholder="Xabar yozish..."
        rows={1}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            void doSend();
          }
        }}
      />
      <button className="btn send" disabled={!text.trim()} onClick={() => void doSend()} title="Yuborish">
        <IconSend size={22} />
      </button>
    </footer>
  );
}