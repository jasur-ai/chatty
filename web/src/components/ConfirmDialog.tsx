import { useEffect } from "react";

type Props = {
  open: boolean;
  title: string;
  text: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

/**
 * Ilova ichidagi tasdiq oynasi.
 *
 * window.confirm()/alert() Telegram Mini App WebView'ida ishonchsiz: ba'zan
 * bloklanadi va hech narsa qaytarmaydi (masalan xabar o'chirish jim o'tib
 * ketadi). Shuning uchun barcha tasdiqlar shu komponent orqali bajariladi.
 */
export function ConfirmDialog({
  open,
  title,
  text,
  confirmLabel = "Tasdiqlash",
  cancelLabel = "Bekor qilish",
  danger = false,
  onConfirm,
  onCancel,
}: Props) {
  // Android back tugmasi / Escape — bekor qilish
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onCancel();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div className="overlay" onClick={onCancel} role="presentation">
      <div
        className="confirm-dialog"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className="confirm-title">{title}</div>
        <div className="confirm-text">{text}</div>
        <div className="confirm-actions">
          <button className="btn ghost" onClick={onCancel}>
            {cancelLabel}
          </button>
          <button className={danger ? "btn danger" : "btn primary"} onClick={onConfirm}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
