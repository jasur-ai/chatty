import { AdminPanel } from "../components/AdminPanel";
import { ChatList } from "../components/ChatList";
import { ChatView } from "../components/ChatView";
import { DelegateView } from "../components/DelegateView";
import { LotusWidget } from "../components/LotusWidget";
import { Settings } from "../components/Settings";
import { IconStar } from "../icons";
import { useStore } from "../store";

export function Main() {
  const { activeDialog, settingsOpen, lotusOpen, openLotus, view } = useStore();

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
      <button className="lotus-fab" onClick={openLotus} title="Lotus 0.0.1">
        <IconStar size={24} />
      </button>
      {settingsOpen && <Settings />}
      {lotusOpen && <LotusWidget />}
    </div>
  );
}
