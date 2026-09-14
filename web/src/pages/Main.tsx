import { AdminPanel } from "../components/AdminPanel";
import { ChatList } from "../components/ChatList";
import { ChatView } from "../components/ChatView";
import { DelegateView } from "../components/DelegateView";
import { LotusWidget } from "../components/LotusWidget";
import { Settings } from "../components/Settings";
import { useStore } from "../store";

export function Main() {
  const { activeDialog, settingsOpen, lotusOpen, view } = useStore();

  if (view === "admin") {
    return (
      <div className="app-shell">
        <AdminPanel />
      </div>
    );
  }

  if (view === "delegate") {
    return (
      <div className="app-shell">
        <DelegateView />
      </div>
    );
  }

  return (
    <div className="app-shell">
      <ChatList />
      {activeDialog ? <ChatView /> : <div className="chat-empty" />}
      {settingsOpen && <Settings />}
      {lotusOpen && <LotusWidget />}
    </div>
  );
}
