import { useEffect, useState } from "react";
import { api } from "./api";
import { IconSpinner } from "./icons";
import { Login } from "./pages/Login";
import { Main } from "./pages/Main";
import { useStore } from "./store";

export function App() {
  const { accounts, current, token, appUser, refreshAccounts } = useStore();
  const [booted, setBooted] = useState(false);

  useEffect(() => {
    void refreshAccounts().finally(() => setBooted(true));
  }, [refreshAccounts]);

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

  if (!booted) {
    return (
      <div className="splash">
        <img src="/chatty.svg" alt="Chatty" width={64} height={64} />
        <IconSpinner size={22} />
      </div>
    );
  }

  const ready = accounts.some((a) => a.auth_step === "ready");
  if (!ready || !current || !token) {
    return <Login />;
  }
  return <Main />;
}