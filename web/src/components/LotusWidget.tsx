import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { IconSend, IconStar, IconX } from "../icons";
import { useStore } from "../store";

type Turn = { role: "user" | "ai" | "error"; text: string };

/** AI javobini kutayotganda ko'rsatiladigan animatsiyali nuqtalar. */
function TypingDots() {
  return (
    <div className="lotus-bubble ai lotus-typing" aria-label="Lotus javob yozmoqda">
      <span className="tdot" />
      <span className="tdot" />
      <span className="tdot" />
    </div>
  );
}

export function LotusWidget() {
  const { token, lotusOpen, closeLotus } = useStore();
  const [chat, setChat] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const [greeted, setGreeted] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Birinchi ochilishda salomlashish — muvaffaqiyatsiz bo'lsa ham jim qolmaydi.
  useEffect(() => {
    if (!lotusOpen || !token || greeted) return;
    setGreeted(true);
    setThinking(true);
    api
      .lotusChat("salom", token)
      .then((r) => setChat((c) => [...c, { role: "ai", text: r.reply }]))
      .catch(() =>
        setChat((c) => [
          ...c,
          {
            role: "ai",
            text: "Salom! Men Lotus — yordamchingiz. Hozir javob berolmayapman, birozdan keyin qayta urinib ko'ring.",
          },
        ]),
      )
      .finally(() => setThinking(false));
  }, [lotusOpen, token, greeted]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat, thinking]);

  if (!lotusOpen) return null;

  async function send() {
    const t = input.trim();
    if (!t || !token || thinking) return;
    setInput("");
    setThinking(true);
    setChat((c) => [...c, { role: "user", text: t }]);
    try {
      const res = await api.lotusChat(t, token);
      setChat((c) => [...c, { role: "ai", text: res.reply }]);
    } catch (e) {
      setChat((c) => [
        ...c,
        { role: "error", text: `Javob olib bo'lmadi: ${(e as Error).message}` },
      ]);
    } finally {
      setThinking(false);
    }
  }

  return (
    <div className="lotus-widget">
      <header className="lotus-widget-header">
        <div className="lotus-avatar small">
          <IconStar size={18} />
        </div>
        <div className="lotus-widget-title">Lotus 0.0.1</div>
        <button className="icon-btn" onClick={closeLotus} title="Yopish" aria-label="Yopish">
          <IconX size={20} />
        </button>
      </header>
      <div className="lotus-widget-body">
        {chat.map((c, i) => (
          <div key={i} className={`lotus-bubble ${c.role}`}>
            {c.text}
          </div>
        ))}
        {thinking && <TypingDots />}
        <div ref={bottomRef} />
      </div>
      <div className="composer-mini">
        <input
          className="input"
          placeholder={thinking ? "Lotus javob yozmoqda…" : "Buyruq yozing..."}
          value={input}
          disabled={thinking}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && void send()}
        />
        <button
          className="btn send"
          onClick={() => void send()}
          disabled={thinking || !input.trim()}
          aria-label="Yuborish"
        >
          <IconSend size={18} />
        </button>
      </div>
    </div>
  );
}
