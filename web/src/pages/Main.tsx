import { ChatList } from "../components/ChatList";
import { ChatView } from "../components/ChatView";
import { useStore } from "../store";

export function Main() {
  const { activeDialog } = useStore();
  return (
    <div className="app-shell">
      <ChatList />
      {activeDialog ? <ChatView /> : <div className="chat-empty" />}
    </div>
  );
}