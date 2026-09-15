import { useMemo, useState } from "react";
import { resolveUrl } from "../env";
import { IconBot, IconGroup, IconLogout, IconMenu, IconSearch, IconSettings, IconShield, IconUser } from "../icons";
import { useStore } from "../store";
import type { Dialog, DialogKind } from "../types";
import { Avatar } from "./Avatar";

function formatTime(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) + (sameDay ? "" : "");
}

type SectionId = "all" | DialogKind;

const SECTIONS: { id: SectionId; label: string }[] = [
  { id: "all", label: "Barchasi" },
  { id: "user", label: "Chatlar" },
  { id: "group", label: "Guruhlar" },
  { id: "channel", label: "Kanallar" },
  { id: "bot", label: "Botlar" },
];

function SectionIcon({ id, size = 14 }: { id: SectionId; size?: number }) {
  if (id === "bot") return <IconBot size={size} />;
  if (id === "group") return <IconGroup size={size} />;
  if (id === "channel") return <IconGroup size={size} />;
  if (id === "user") return <IconUser size={size} />;
  return null;
}

export function ChatList() {
  const { accounts, current, dialogs, loadingChats, chatsError, selectAccount, openDialog, openSettings, logout, appUser, setView } =
    useStore();
  const [search, setSearch] = useState("");
  const [switcherOpen, setSwitcherOpen] = useState(false);
  const [section, setSection] = useState<SectionId>("all");

  const isAdminLike = appUser?.is_admin || appUser?.is_owner;

  const counts = useMemo(() => {
    const c: Record<SectionId, number> = { all: dialogs.length, user: 0, group: 0, channel: 0, bot: 0 };
    for (const d of dialogs) {
      const k = (d.kind || "user") as DialogKind;
      if (c[k] === undefined) c[k] = 0;
      c[k] += 1;
    }
    return c;
  }, [dialogs]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return dialogs.filter((d) => {
      if (section !== "all" && (d.kind || "user") !== section) return false;
      if (!q) return true;
      return (
        d.title.toLowerCase().includes(q) ||
        (d.username ? d.username.toLowerCase().includes(q) : false) ||
        (d.last_msg_text ? d.last_msg_text.toLowerCase().includes(q) : false)
      );
    });
  }, [dialogs, search, section]);

  return (
    <aside className="sidebar">
      <header className="sidebar-header">
        <div className="account-switch">
          <button className="icon-btn" onClick={() => setSwitcherOpen((v) => !v)} title="Akkauntlar">
            <IconMenu size={22} />
          </button>
          <span className="sidebar-title">{current?.bot_name || current?.first_name || "Chatty"}</span>
          <span className="tg-close-spacer" />
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
        {/* Bo'limlar: chatlar / guruhlar / kanallar / botlar */}
        <div className="chat-sections" role="tablist">
          {SECTIONS.map((s) => (
            <button
              key={s.id}
              role="tab"
              aria-selected={section === s.id}
              className={`chat-section ${section === s.id ? "active" : ""}`}
              onClick={() => setSection(s.id)}
            >
              <SectionIcon id={s.id} size={13} />
              <span>{s.label}</span>
              <span className="section-count">{counts[s.id] ?? 0}</span>
            </button>
          ))}
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
          <div className="list-status muted">
            {search ? "Hech narsa topilmadi" : "Bu bo'limda chatlar yo'q"}
          </div>
        )}
        {filtered.map((d) => (
          <ChatRow key={d.id} d={d} onOpen={() => void openDialog(d)} />
        ))}
      </div>

      <footer className="sidebar-footer">
        {isAdminLike && (
          <button className="footer-btn" title="Bot suhbatlari (vakil)" onClick={() => setView("delegate")}>
            <IconBot size={22} />
            <span>Bot</span>
          </button>
        )}
        {isAdminLike && (
          <button className="footer-btn" title="Admin panel" onClick={() => setView("admin")}>
            <IconShield size={22} />
            <span>Admin</span>
          </button>
        )}
        <button className="footer-btn" title="Sozlamalar" onClick={openSettings}>
          <IconSettings size={22} />
          <span>Sozlamalar</span>
        </button>
        <button className="footer-btn" title="Chiqish" onClick={() => void logout()}>
          <IconLogout size={22} />
          <span>Chiqish</span>
        </button>
      </footer>
    </aside>
  );
}

function ChatRow({ d, onOpen }: { d: Dialog; onOpen: () => void }) {
  return (
    <button className="chat-item" onClick={onOpen}>
      <Avatar name={d.title} photo={resolveUrl(d.photo)} size={54} />
      <div className="chat-item-body">
        <div className="chat-item-top">
          <span className="chat-item-title">
            {d.kind === "bot" && <span className="kind-tag">bot</span>}
            {d.kind === "channel" && <span className="kind-tag">kanal</span>}
            {d.kind === "group" && <span className="kind-tag">guruh</span>}
            {d.title}
          </span>
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
  );
}
