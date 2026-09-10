import { ChatList } from "../components/ChatList";
import { ChatView } from "../components/ChatView";
import { LotusWidget } from "../components/LotusWidget";
import { Settings } from "../components/Settings";
import { IconStar } from "../icons";
import { useStore } from "../store";

export function Main() {
  const { activeDialog, settingsOpen, lotusOpen, openLotus } = useStore();
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