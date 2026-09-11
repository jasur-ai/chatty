import { useEffect, useState } from "react";
import { api } from "./api";
import { IconSpinner } from "./icons";
import { Login } from "./pages/Login";
import { Main } from "./pages/Main";
import { useStore } from "./store";

export function App() {
  const { accounts, current, token, appUser, refreshAccounts, silentLogin } = useStore();
  const [booted, setBooted] = useState(false);
  const [authChecked, setAuthChecked] = useState(false);

  useEffect(() => {
    void refreshAccounts().finally(() => setBooted(true));
  }, [refreshAccounts]);

  // Telegram ichida bo'lsa va hali token yo'q bo'lsa — avtomatik (silent) kirish.
  // Sessiya Postgres'da saqlangani uchun telefon/kod/2FA qayta so'ralmaydi.
  useEffect(() => {
    if (!booted || authChecked) return;
    const ready = accounts.some((a) => a.auth_step === "ready");
    if (ready && !token) {
      void silentLogin().finally(() => setAuthChecked(true));
    } else {
      setAuthChecked(true);
    }
  }, [booted, authChecked, accounts, token, silentLogin]);

  // Pink/default rejimni qo'llash
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", appUser?.theme === "pink" ? "pink" : "default");
  }, [appUser?.theme]);

  // VIP shaxsiy mavzu rangini qo'llash
  useEffect(() => {
    if (!current || !token) return;
    if (appUser?.is_vip || appUser?.is_owner || appUser?.is_admin) {
      void api.vipThemeGet(current.id, token).then((t) => {
        document.documentElement.style.setProperty("--accent", t.accent);
        document.documentElement.style.setProperty("--accent-hover", t.accent);
      });
    }
  }, [current?.id, token, appUser?.is_vip, appUser?.is_owner, appUser?.is_admin]);

  // Yuklanmoqda yoki avtomatik kirish tekshirilmoqda — splash ko'rsatamiz
  if (!booted || !authChecked) {
    return (
      <div className="splash">
        <img src="/chatty.svg" alt="Chatty" width={64} height={64} />
        <IconSpinner size={24} />
        <div className="splash-label">Ulanyapti…</div>
      </div>
    );
  }

  const ready = accounts.some((a) => a.auth_step === "ready");
  if (!ready || !current || !token) {
    return <Login />;
  }
  return <Main />;
}