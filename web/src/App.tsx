import { useEffect, useState } from "react";
import { IconSpinner } from "./icons";
import { Login } from "./pages/Login";
import { Main } from "./pages/Main";
import { useStore } from "./store";

export function App() {
  const { accounts, current, token, refreshAccounts } = useStore();
  const [booted, setBooted] = useState(false);

  useEffect(() => {
    void refreshAccounts().finally(() => setBooted(true));
  }, [refreshAccounts]);

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