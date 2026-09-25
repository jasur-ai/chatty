import { AdminPanel } from "../components/AdminPanel";
import { ChatList } from "../components/ChatList";
import { ChatView } from "../components/ChatView";
import { DelegateView } from "../components/DelegateView";
import { EventsView } from "../components/EventsView";
import { LotusWidget } from "../components/LotusWidget";
import { Settings } from "../components/Settings";
import { IconBot, IconSettings, IconStar, IconUsers } from "../icons";
import { useStore } from "../store";

/** Chat tanlanmaganda ko'rsatiladigan tushuntirish. */
function ChatPlaceholder() {
  const { setView, openSettings } = useStore();
  return (
    <div className="chat-empty chat-placeholder">
      <IconBot size={48} />
      <div className="ph-title">Chatni tanlang</div>
      <div className="ph-sub">
        Begona odamlar sizning botingizga yozadi, siz esa javobni shu yerdan — bot nomidan
        yuborasiz. Telegram akkauntingiz hech kimga ko'rinmaydi.
      </div>
      <div className="ph-hints">
        <button type="button" className="ph-hint" onClick={() => setView("delegate")}>
          <IconUsers size={16} />
          Botga yozganlar
        </button>
        <button type="button" className="ph-hint" onClick={openSettings}>
          <IconSettings size={16} />
          Bot sozlamalari
        </button>
      </div>
    </div>
  );
}

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

  if (view === "events") {
    return (
      <div className="app-shell">
        <EventsView />
      </div>
    );
  }

  return (
    <div className="app-shell">
      <ChatList />
      {activeDialog ? <ChatView /> : <ChatPlaceholder />}
      <button className="lotus-fab" onClick={openLotus} title="Lotus 0.0.1">
        <IconStar size={24} />
      </button>
      {settingsOpen && <Settings />}
      {lotusOpen && <LotusWidget />}
    </div>
  );
}
