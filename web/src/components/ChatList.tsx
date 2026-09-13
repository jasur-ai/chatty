import { useState } from "react";
import { resolveUrl } from "../env";
import { IconBot, IconLogout, IconMenu, IconPlus, IconSearch, IconSettings, IconShield } from "../icons";
import { useStore } from "../store";
import { Avatar } from "./Avatar";

function formatTime(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) + (sameDay ? "" : "");
}

export function ChatList() {
  const { accounts, current, dialogs, loadingChats, chatsError, selectAccount, openDialog, openSettings, logout, appUser, setView } = useStore();
  const [search, setSearch] = useState("");
  const [switcherOpen, setSwitcherOpen] = useState(false);

  const isAdminLike = appUser?.is_admin || appUser?.is_owner;

  const filtered = search
    ? dialogs.filter((d) => d.title.toLowerCase().includes(search.toLowerCase()))
    : dialogs;

  return (
    <aside className="sidebar">
      <header className="sidebar-header">
        <div className="account-switch">
          <button className="icon-btn" onClick={() => setSwitcherOpen((v) => !v)} title="Akkauntlar">
            <IconMenu size={22} />
          </button>
          <span className="sidebar-title">{current?.bot_name || current?.first_name || "Chatty"}</span>
          <button className="icon-btn" title="Yangi chat">
            <IconPlus size={22} />
          </button>
        </div>
        {switcherOpen && (
          <div className="switcher">
            {accounts.map((a) => (
              <button
                key={a.id}
                className={`switcher-item ${a.id === current?.id ? "active" : ""}`}
                onClick={() => {
                  void selectAccount(a.id);
                  setSwitcherOpen(false);
                }}
              >
                <Avatar name={a.bot_name || a.first_name || a.phone} size={34} />
                <span>{a.bot_name || a.first_name || a.phone}</span>
              </button>
            ))}
          </div>
        )}
        <div className="search-box">
          <IconSearch size={18} className="search-icon" />
          <input
            className="search-input"
            placeholder="Qidirish"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </header>

      <div className="chat-list">
        {loadingChats && (
          <div className="skeleton-list">
            {Array.from({ length: 8 }).map((_, i) => (
              <div className="skeleton" key={i}>
                <div className="skeleton-avatar" />
                <div className="skeleton-body">
                  <div className="skeleton-line" />
                  <div className="skeleton-line-sm" />
                </div>
              </div>
            ))}
          </div>
        )}
        {!loadingChats && chatsError && (
          <div className="list-status error">
            {chatsError}
            <button className="btn ghost" onClick={() => current && void selectAccount(current.id)}>
              Qayta urinish
            </button>
          </div>
        )}
        {!loadingChats && !chatsError && filtered.length === 0 && (
          <div className="list-status muted">Chatlar hozircha yo'q</div>
        )}
        {filtered.map((d) => (
          <button key={d.id} className="chat-item" onClick={() => void openDialog(d)}>
            <Avatar name={d.title} photo={resolveUrl(d.photo)} size={54} />
            <div className="chat-item-body">
              <div className="chat-item-top">
                <span className="chat-item-title">{d.title}</span>
                {d.last_msg_date && <span className="chat-item-time">{formatTime(d.last_msg_date)}</span>}
              </div>
              <div className="chat-item-bottom">
                <span className="chat-item-last">
                  {d.last_out ? "Siz: " : ""}
                  {d.last_msg_text || ""}
                </span>
                {d.unread_count > 0 && <span className="unread-badge">{d.unread_count}</span>}
              </div>
            </div>
          </button>
        ))}
      </div>

      <footer className="sidebar-footer">
        {isAdminLike && (
          <button className="icon-btn" title="Bot suhbatlari (vakil)" onClick={() => setView("delegate")}>
            <IconBot size={20} />
          </button>
        )}
        {isAdminLike && (
          <button className="icon-btn" title="Admin panel" onClick={() => setView("admin")}>
            <IconShield size={20} />
          </button>
        )}
        <button className="icon-btn" title="Sozlamalar" onClick={openSettings}>
          <IconSettings size={20} />
        </button>
        <button className="icon-btn" title="Chiqish" onClick={() => void logout()}>
          <IconLogout size={20} />
        </button>
      </footer>
    </aside>
  );
}