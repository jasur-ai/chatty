import { useState } from "react";
import { api } from "../api";
import { IconBack, IconLock, IconPhone, IconShield, IconSpinner } from "../icons";
import { useStore } from "../store";
import type { LoginResult } from "../types";

type Step = "terms" | "phone" | "code" | "password";

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

  async function doStart() {
    setBusy(true);
    setError("");
    try {
      await api.startLogin(phone.trim());
      setStep("code");
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
              onChange={(e) => setPhone(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && doStart()}
            />
            {error && <div className="error">{error}</div>}
            <button className="btn primary" disabled={busy || phone.trim().length < 5} onClick={doStart}>
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
            <input
              className="input"
              type="text"
              inputMode="numeric"
              placeholder="Kod"
              value={code}
              autoFocus
              onChange={(e) => setCode(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && doVerify()}
            />
            {error && <div className="error">{error}</div>}
            <button className="btn primary" disabled={busy || code.trim().length < 4} onClick={doVerify}>
              {busy ? <IconSpinner size={18} /> : "Tasdiqlash"}
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