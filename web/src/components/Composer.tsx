import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { IconMic, IconPlus, IconSend, IconSpinner, IconStory, IconX } from "../icons";
import { useStore } from "../store";

/** Brauzer qo'llab-quvvatlaydigan yozib olish formatini tanlaydi
 *  (iOS Safari webm o'rniga mp4 ishlatadi — aks holda MediaRecorder xato beradi). */
function pickMime(kind: "voice" | "round"): string {
  const candidates =
    kind === "voice"
      ? ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"]
      : ["video/webm;codecs=vp9,opus", "video/webm;codecs=vp8,opus", "video/webm", "video/mp4"];
  if (typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported) {
    for (const c of candidates) {
      if (MediaRecorder.isTypeSupported(c)) return c;
    }
  }
  return kind === "voice" ? "audio/webm" : "video/webm";
}

function extForMime(mime: string): string {
  if (mime.includes("mp4")) return "mp4";
  if (mime.includes("ogg")) return "ogg";
  return "webm";
}

export function Composer() {
  const { current, token, activeDialog, sendText, dialogs, replyTo, setReplyTo } = useStore();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [recording, setRecording] = useState<"voice" | "round" | null>(null);
  const [recSeconds, setRecSeconds] = useState(0);
  const [forwardMode, setForwardMode] = useState(false);
  const [forwardTargets, setForwardTargets] = useState<number[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const recStartRef = useRef(0);
  const cameraRef = useRef<HTMLVideoElement>(null);

  // Yozish vaqti hisoblagichi
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

  // Dumaloq video yozayotganda jonli kamera preview
  useEffect(() => {
    const v = cameraRef.current;
    if (recording === "round" && v && streamRef.current) {
      v.srcObject = streamRef.current;
      void v.play().catch(() => {});
    }
    return () => {
      if (v) v.srcObject = null;
    };
  }, [recording]);

  function fmtRec(s: number): string {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${sec.toString().padStart(2, "0")}`;
  }

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

  async function startRecording(kind: "voice" | "round") {
    if (!current || !token || !activeDialog || recording) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        // Ovozli xabar: faqat audio. Dumaloq video: audio + video (kamera).
        audio: true,
        video: kind === "round",
      });
      streamRef.current = stream;
      const mime = pickMime(kind);
      const rec = new MediaRecorder(stream, { mimeType: mime });
      chunksRef.current = [];
      rec.ondataavailable = (e) => chunksRef.current.push(e.data);
      rec.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: mime });
        const ext = extForMime(mime);
        const file = new File([blob], `${kind}-${Date.now()}.${ext}`, { type: mime });
        setUploading(true);
        try {
          const up = await api.uploadMedia(current!.id, file, token!);
          await api.send(current!.id, activeDialog!.id, "", token!, {
            mediaKey: up.media_key,
            mediaType: kind, // "voice" yoki "round"
          });
        } catch (err) {
          setError((err as Error).message);
        } finally {
          setUploading(false);
        }
      };
      rec.start();
      mediaRecorderRef.current = rec;
      setRecording(kind);
      // Telegram dumaloq video uchun 60 soniya limit — avtomatik to'xtatamiz
      if (kind === "round") {
        window.setTimeout(() => {
          if (mediaRecorderRef.current === rec && rec.state !== "inactive") stopRecording();
        }, 60000);
      }
    } catch (err) {
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

  async function doForward() {
    if (!current || !token || !activeDialog) return;
    // Eng oxirgi xabarni forward qilish (optimistik: last msg tg_id)
    setBusy(true);
    setError("");
    try {
      const lastId = await findLastOutgoingId();
      if (!lastId) {
        setError("Forward qilish uchun avval xabar yuboring");
        return;
      }
      await api.forward(current.id, {
        dialog_id: activeDialog.id,
        msg_tg_id: lastId,
        target_dialog_ids: forwardTargets,
      }, token);
      setForwardMode(false);
      setForwardTargets([]);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function findLastOutgoingId(): Promise<number | null> {
    if (!current || !token || !activeDialog) return null;
    const res = await api.messages(current.id, activeDialog.id, token);
    const last = [...res.messages].reverse().find((m) => m.out);
    return last?.tg_id ?? null;
  }

  return (
    <footer className="composer">
      {replyTo && (
        <div className="reply-context">
          <div className="reply-context-text">
            <b>Javob:</b> {replyTo.text || "media"}
          </div>
          <button className="icon-btn" onClick={() => setReplyTo(null)} title="Bekor">
            <IconX size={16} />
          </button>
        </div>
      )}
      {recording && (
        <div className="rec-panel">
          {recording === "round" ? (
            <video ref={cameraRef} className="rec-camera" autoPlay playsInline muted />
          ) : (
            <div className="rec-wave">
              {Array.from({ length: 28 }).map((_, i) => (
                <span
                  key={i}
                  className="wave-bar"
                  style={{ animationDelay: `${(i % 7) * 0.09}s`, height: `${30 + ((i * 13) % 55)}%` }}
                />
              ))}
            </div>
          )}
          <div className="rec-info">
            <span className="rec-label">
              <span className="rec-dot" />
              <span>{recording === "voice" ? "Ovozli xabar" : "Dumaloq video"} yozilmoqda</span>
            </span>
            <span className="rec-timer muted">{fmtRec(recSeconds)}</span>
            <button className="btn danger" onClick={stopRecording}>To'xtatish va yuborish</button>
          </div>
        </div>
      )}
      <div className="composer-row">
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
        disabled={uploading || !!recording}
        onClick={() => fileRef.current?.click()}
      >
        {uploading ? <IconSpinner size={22} /> : <IconPlus size={24} />}
      </button>

      <button
        className={`icon-btn attach ${recording === "voice" ? "rec" : ""}`}
        title={recording === "voice" ? "To'xtatish" : "Ovozli xabar"}
        disabled={uploading || recording === "round"}
        onClick={() => (recording === "voice" ? stopRecording() : void startRecording("voice"))}
      >
        <IconMic size={22} />
      </button>

      <button
        className={`icon-btn attach ${recording === "round" ? "rec" : ""}`}
        title={recording === "round" ? "To'xtatish" : "Dumaloq video"}
        disabled={uploading || recording === "voice"}
        onClick={() => (recording === "round" ? stopRecording() : void startRecording("round"))}
      >
        <IconStory size={22} />
      </button>

      <textarea
        className="composer-input"
        placeholder={uploading ? "Yuklanmoqda..." : recording ? "Yozilmoqda... to'xtatish uchun bosing" : "Xabar yozish..."}
        rows={1}
        value={text}
        disabled={uploading || !!recording}
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

      <button
        className={`icon-btn attach ${forwardMode ? "active" : ""}`}
        title="Forward"
        onClick={() => setForwardMode((v) => !v)}
      >
        <span style={{ transform: "scaleX(-1)", display: "inline-flex" }}><IconSend size={18} /></span>
      </button>
      </div>

      {forwardMode && (
        <div className="forward-pop">
          <div className="pane-sub">Forward qilish (eng oxirgi chiqim xabar)</div>
          <div className="target-list" style={{ maxHeight: 180, overflowY: "auto" }}>
            {dialogs.filter((d) => d.id !== activeDialog?.id).map((d) => (
              <label className="check-row" key={d.id}>
                <input
                  type="checkbox"
                  checked={forwardTargets.includes(d.id)}
                  onChange={(e) =>
                    setForwardTargets((prev) =>
                      e.target.checked ? [...prev, d.id] : prev.filter((x) => x !== d.id),
                    )
                  }
                />
                <span>{d.title}</span>
              </label>
            ))}
          </div>
          <button className="btn primary" disabled={!forwardTargets.length || busy} onClick={() => void doForward()}>
            Forward
          </button>
        </div>
      )}
      {error && <div className="composer-error">{error}</div>}
    </footer>
  );
}
