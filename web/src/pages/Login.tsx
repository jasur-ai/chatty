import { useEffect, useState } from "react";
import { api } from "../api";
import { IconBack, IconLock, IconPhone, IconShield, IconSpinner } from "../icons";
import { useStore } from "../store";
import type { LoginResult } from "../types";

type Step = "terms" | "phone" | "code" | "password";

/** Telegram O'zbekiston raqamlari: +998 va 9 xona. */
export function normalizePhone(raw: string) {
  return raw.replace(/[^\d+]/g, "");
}

export function phoneProblem(v: string): string {
  const d = v.replace(/\D/g, "");
  if (!d) return "";
  if (!d.startsWith("998")) return "Raqam 998 bilan boshlanishi kerak";
  if (d.length < 12) return `Yana ${12 - d.length} ta raqam kerak`;
  if (d.length > 12) return "Raqam juda uzun";
  return "";
}

const TERMS = [
  { title: "Akkaunt ulash", text: "Chatty sizning Telegram akkauntingizni MTProto orqali xavfsiz ulaydi. Ulash uchun telefon raqamingiz, tasdiqlash kodi va 2FA paroli talab qilinadi." },
  { title: "Maxfiylik", text: "Sizning shaxsiy ma'lumotlaringiz va chatlaringiz faqat shu tizim ichida saqlanadi. Sessiyalar shifrlangan holda himoyalanadi." },
  { title: "Foydalanish shartlari", text: "Tizimdan foydalanish orqali siz barcha shartlarga rozilik bildirasiz. Chatlar, akkauntlar va barcha faoliyat qonunchilikka muvofiq olib boriladi." },
  { title: "Nazorat", text: "Barcha amaliyotlar qattiq admin nazorati va kuzatuvi ostida olib boriladi." },
];

export function Login() {
  const { addAccount } = useStore();
  const [step, setStep] = useState<Step>("terms");
  const [agreed, setAgreed] = useState(false);
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [via, setVia] = useState<string | null>(null);
  // Telegram kod so'rovlarini cheklaydi: 30 soniyada bir marta, soatiga 5 marta.
  // Shuning uchun qayta yuborish tugmasida qancha kutish kerakligini ko'rsatamiz.
  const [wait, setWait] = useState(0);

  useEffect(() => {
    if (wait <= 0) return;
    const t = setTimeout(() => setWait((w) => w - 1), 1000);
    return () => clearTimeout(t);
  }, [wait]);

  async function doStart() {
    setBusy(true);
    setError("");
    try {
      const r = await api.startLogin(phone.trim());
      setVia(r.via ?? null);
      setWait(30);
      setStep("code");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function resend() {
    setBusy(true);
    setError("");
    try {
      const r = await api.startLogin(phone.trim());
      setVia(r.via ?? null);
      setWait(30);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function doVerify() {
    setBusy(true);
    setError("");
    try {
      const res = await api.verifyCode(phone.trim(), code.trim());
      if ("step" in res && res.step === "password") {
        setStep("password");
      } else {
        finish(res as LoginResult);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function doPassword() {
    setBusy(true);
    setError("");
    try {
      finish(await api.submitPassword(phone.trim(), password));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function finish(res: LoginResult) {
    addAccount(res.account, res.token, res.app_user);
  }

  return (
    <div className="login-wrap">
      <div className="login-card">
        <div className="login-logo">
          <img src="/chatty.svg" alt="Chatty" width={72} height={72} />
        </div>
        <h1 className="login-title">Chatty</h1>

        {step === "terms" && (
          <>
            <p className="login-sub">Telegram akkauntlarini boshqarish platformasi</p>
            <div className="terms-box">
              {TERMS.map((t) => (
                <div className="term-item" key={t.title}>
                  <div className="term-title">{t.title}</div>
                  <div className="term-text">{t.text}</div>
                </div>
              ))}
            </div>
            <label className="terms-agree">
              <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />
              <span>Foydalanish shartlariga roziman</span>
            </label>
            <button className="btn primary" disabled={!agreed} onClick={() => setStep("phone")}>
              Davom etish
            </button>
          </>
        )}

        {step === "phone" && (
          <>
            <div className="step-icon">
              <IconPhone size={26} />
            </div>
            <p className="login-sub">Telefon raqamingizni kiriting</p>
            <input
              className="input"
              type="tel"
              placeholder="+998901234567"
              value={phone}
              autoFocus
              onChange={(e) => setPhone(normalizePhone(e.target.value))}
              onKeyDown={(e) => e.key === "Enter" && !phoneProblem(phone) && doStart()}
            />
            {phoneProblem(phone) && <div className="field-hint">{phoneProblem(phone)}</div>}
            {error && <div className="error">{error}</div>}
            <button
              className="btn primary"
              disabled={busy || !!phoneProblem(phone) || phone.replace(/\D/g, "").length !== 12}
              onClick={doStart}
            >
              {busy ? <IconSpinner size={18} /> : "Kod yuborish"}
            </button>
            <button className="btn ghost" onClick={() => setStep("terms")}>
              <IconBack size={16} /> Orqaga
            </button>
          </>
        )}

        {step === "code" && (
          <>
            <div className="step-icon">
              <IconLock size={26} />
            </div>
            <p className="login-sub">
              Telegram'ga yuborilgan tasdiqlash kodini kiriting
              <br />
              <span className="muted">{phone}</span>
            </p>
            <div className="hint">
              {via === "sms" ? (
                <>Telegram kodni <b>SMS</b> orqali yubordi. Xabar kelishini kuting.</>
              ) : via === "call" ? (
                <>Telegram kodni <b>qo'ng'iroq</b> orqali yubordi — kiruvchi raqamning oxirgi raqamlarini kiriting.</>
              ) : via === "flash" ? (
                <>Kodni olish uchun qurilmangizdagi tasdiqlashni bosing.</>
              ) : (
                <>
                  Telegram kodni <b>ilovaga</b> yubordi (SMS emas). Chatlar ro'yxatida
                  ko'k samolyot belgili <b>"Telegram"</b> servis chatini oching —
                  5 xonali kod shu yerda.
                </>
              )}
              <br />
              Agar 5 daqiqada kelmasa — urinishni to'xtating, 30-60 daqiqa kuting,
              keyin bir marta qayta yuboring (tez-tez so'rash Telegram'da blok qo'yadi).
            </div>
            <input
              className="input"
              type="text"
              inputMode="numeric"
              placeholder="5 xonali kod"
              maxLength={8}
              value={code}
              autoFocus
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              onKeyDown={(e) => e.key === "Enter" && code.trim().length >= 5 && doVerify()}
            />
            {code.trim().length > 0 && code.trim().length < 5 && (
              <div className="field-hint">Kod {code.trim().length}/5 xona</div>
            )}
            {error && <div className="error">{error}</div>}
            <button className="btn primary" disabled={busy || code.trim().length < 5} onClick={doVerify}>
              {busy ? <IconSpinner size={18} /> : "Tasdiqlash"}
            </button>
            <button
              className="btn ghost"
              disabled={busy || wait > 0}
              onClick={resend}
              title="Kodni qayta yuborish"
            >
              {busy ? <IconSpinner size={16} /> : wait > 0 ? `Qayta yuborish (${wait}s)` : "Kodni qayta yuborish"}
            </button>
            <button className="btn ghost" onClick={() => setStep("phone")}>
              <IconBack size={16} /> Orqaga
            </button>
          </>
        )}

        {step === "password" && (
          <>
            <div className="step-icon">
              <IconShield size={26} />
            </div>
            <p className="login-sub">
              Akkauntda ikki bosqichli tekshiruv (2FA) yoqilgan.
              <br />
              <span className="muted">Parolni kiriting</span>
            </p>
            <input
              className="input"
              type="password"
              placeholder="2FA paroli"
              value={password}
              autoFocus
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && doPassword()}
            />
            {error && <div className="error">{error}</div>}
            <button className="btn primary" disabled={busy || !password} onClick={doPassword}>
              {busy ? <IconSpinner size={18} /> : "Kirish"}
            </button>
            <button className="btn ghost" onClick={() => setStep("code")}>
              <IconBack size={16} /> Orqaga
            </button>
          </>
        )}
      </div>
    </div>
  );
}