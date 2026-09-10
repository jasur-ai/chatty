import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { IconSend, IconStar, IconX } from "../icons";
import { useStore } from "../store";

export function LotusWidget() {
  const { token, lotusOpen, closeLotus } = useStore();
  const [chat, setChat] = useState<{ role: "user" | "ai"; text: string }[]>([]);
  const [input, setInput] = useState("");
  const [greeted, setGreeted] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!lotusOpen || !token || greeted) return;
    setGreeted(true);
    void api.lotusChat("salom", token).then((r) => {
      setChat((c) => [...c, { role: "ai", text: r.reply }]);
    });
  }, [lotusOpen, token, greeted]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat]);

  if (!lotusOpen) return null;

  async function send() {
    const t = input.trim();
    if (!t || !token) return;
    setInput("");
    setChat((c) => [...c, { role: "user", text: t }]);
    const res = await api.lotusChat(t, token);
    setChat((c) => [...c, { role: "ai", text: res.reply }]);
  }

  return (
    <div className="lotus-widget">
      <header className="lotus-widget-header">
        <div className="lotus-avatar small"><IconStar size={18} /></div>
        <div className="lotus-widget-title">Lotus 0.0.1</div>
        <button className="icon-btn" onClick={closeLotus} title="Yopish"><IconX size={20} /></button>
      </header>
      <div className="lotus-widget-body">
        {chat.map((c, i) => (
          <div key={i} className={`lotus-bubble ${c.role}`}>{c.text}</div>
        ))}
        <div ref={bottomRef} />
      </div>
      <div className="composer-mini">
        <input className="input" placeholder="Buyruq yozing..." value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && void send()} />
        <button className="btn send" onClick={() => void send()}><IconSend size={18} /></button>
      </div>
    </div>
  );
}
