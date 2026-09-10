import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import {
  IconBot,
  IconCrown,
  IconImage,
  IconMic,
  IconMusic,
  IconSend,
  IconSettings,
  IconStar,
  IconStory,
  IconTrash,
  IconUser,
  IconX,
} from "../icons";
import { useStore } from "../store";
import type { AdminAccount, BotSettings, MusicPost } from "../types";
import { Avatar } from "./Avatar";

type Tab = "bot" | "auto" | "lotus" | "music" | "admin";

export function Settings() {
  const { current, token, appUser, closeSettings } = useStore();
  const [tab, setTab] = useState<Tab>("bot");
  const isAdmin = !!appUser?.is_admin || !!appUser?.is_owner;

  if (!current || !token) return null;

  return (
    <div className="overlay">
      <div className="settings">
        <header className="settings-header">
          <div className="settings-title">
            <IconSettings size={20} />
            <span>Sozlamalar</span>
          </div>
          <button className="icon-btn" onClick={closeSettings} title="Yopish">
            <IconX size={22} />
          </button>
        </header>

        <nav className="settings-nav">
          <NavBtn id="bot" icon={<IconBot size={18} />} label="Bot" active={tab === "bot"} onClick={() => setTab("bot")} />
          <NavBtn id="auto" icon={<IconSend size={18} />} label="Avto-javob" active={tab === "auto"} onClick={() => setTab("auto")} />
          <NavBtn id="lotus" icon={<IconStar size={18} />} label="Lotus" active={tab === "lotus"} onClick={() => setTab("lotus")} />
          <NavBtn id="music" icon={<IconMusic size={18} />} label="Musiqa" active={tab === "music"} onClick={() => setTab("music")} />
          {isAdmin && (
            <NavBtn id="admin" icon={<IconCrown size={18} />} label="Admin" active={tab === "admin"} onClick={() => setTab("admin")} />
          )}
        </nav>

        <div className="settings-body">
          {tab === "bot" && <BotTab />}
          {tab === "auto" && <AutoTab />}
          {tab === "lotus" && <LotusTab />}
          {tab === "music" && <MusicTab />}
          {tab === "admin" && isAdmin && <AdminTab />}
        </div>
      </div>
    </div>
  );
}

function NavBtn({ icon, label, active, onClick }: { id?: string; icon: React.ReactNode; label: string; active: boolean; onClick: () => void }) {
  return (
    <button className={`nav-btn ${active ? "active" : ""}`} onClick={onClick}>
      {icon}
      <span>{label}</span>
    </button>
  );
}

// ---------------- Bot persona ----------------
function BotTab() {
  const { current, token, refreshAccounts } = useStore();
  const [name, setName] = useState("");
  const [updateTg, setUpdateTg] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const photoRef = useRef<HTMLInputElement>(null);
  const storyRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!current || !token) return;
    void api.botSettings(current.id, token).then((s) => {
      setName(s.account.bot_name || s.account.first_name || "");
    });
  }, [current, token]);

  if (!current || !token) return null;

  async function saveName() {
    setBusy(true);
    setMsg("");
    try {
      await api.updateBotSettings(current!.id, { bot_name: name, update_tg_profile: updateTg }, token!);
      setMsg("Saqlangan");
      await refreshAccounts();
    } catch (e) {
      setMsg((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function onPhoto(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!f) return;
    setBusy(true);
    setMsg("");
    try {
      await api.setBotPhoto(current!.id, f, token!);
      setMsg("Profil rasmi yangilandi");
    } catch (err) {
      setMsg((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function onStory(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!f) return;
    setBusy(true);
    setMsg("");
    try {
      await api.postStory(current!.id, f, "", token!);
      setMsg("Story joylandi");
    } catch (err) {
      setMsg((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="settings-pane">
      <div className="pane-head">
        <Avatar name={name} size={64} />
        <div>
          <div className="pane-title">{name || "Bot"}</div>
          <div className="muted">Default: akkaunt bilan bir xil. O'zgartirishingiz mumkin.</div>
        </div>
      </div>

      <label className="field">
        <span>Bot nomi</span>
        <input className="input" value={name} onChange={(e) => setName(e.target.value)} />
      </label>
      <label className="check-row">
        <input type="checkbox" checked={updateTg} onChange={(e) => setUpdateTg(e.target.checked)} />
        <span>Telegram profil nomini ham o'zgartirish</span>
      </label>
      <button className="btn primary" disabled={busy} onClick={saveName}>
        Saqlash
      </button>

      <div className="pane-row">
        <input ref={photoRef} type="file" accept="image/*" style={{ display: "none" }} onChange={onPhoto} />
        <button className="btn ghost" onClick={() => photoRef.current?.click()}>
          <IconImage size={18} /> Profil rasmi
        </button>
        <input ref={storyRef} type="file" accept="image/*,video/*" style={{ display: "none" }} onChange={onStory} />
        <button className="btn ghost" onClick={() => storyRef.current?.click()}>
          <IconStory size={18} /> Story joylash
        </button>
      </div>

      {msg && <div className="settings-msg">{msg}</div>}
    </div>
  );
}

// ---------------- Avto-javob ----------------
function AutoTab() {
  const { current, token } = useStore();
  const [settings, setSettings] = useState<BotSettings | null>(null);
  const [enabled, setEnabled] = useState(false);
  const [text, setText] = useState("");
  const [selectedText, setSelectedText] = useState("");
  const [targetId, setTargetId] = useState("");
  const [targetName, setTargetName] = useState("");
  const [msg, setMsg] = useState("");

  useEffect(() => {
    if (!current || !token) return;
    void api.botSettings(current.id, token).then((s) => {
      setSettings(s);
      setEnabled(s.auto_reply.enabled);
      setText(s.auto_reply.text || "");
      setSelectedText(s.auto_reply.selected_text || "");
    });
  }, [current, token]);

  if (!current || !token) return null;

  async function persist(patch: Parameters<typeof api.setAutoReply>[1]) {
    setMsg("");
    try {
      await api.setAutoReply(current!.id, patch, token!);
      setMsg("Saqlangan");
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  async function addTarget() {
    const id = Number(targetId.trim());
    if (!id) return;
    try {
      await api.addTarget(current!.id, id, targetName.trim() || null, token!);
      setTargetId("");
      setTargetName("");
      const s = await api.botSettings(current!.id, token!);
      setSettings(s);
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  async function removeTarget(id: number) {
    await api.removeTarget(current!.id, id, token!);
    const s = await api.botSettings(current!.id, token!);
    setSettings(s);
  }

  return (
    <div className="settings-pane">
      <label className="check-row">
        <input type="checkbox" checked={enabled} onChange={(e) => { setEnabled(e.target.checked); void persist({ enabled: e.target.checked }); }} />
        <span>Avto-javobni yoqish</span>
      </label>

      <label className="field">
        <span>Asosiy avto-javob matni</span>
        <textarea className="input" rows={3} value={text} onChange={(e) => setText(e.target.value)} onBlur={() => void persist({ text })} />
      </label>

      <div className="chips">
        {settings?.suggested_replies.map((r) => (
          <button key={r} className="chip" onClick={() => { setText(r); void persist({ text: r }); }}>
            {r}
          </button>
        ))}
      </div>

      <label className="field">
        <span>Belgilangan odamlar uchun matn (bo'sh bo'lsa asosiy matn)</span>
        <textarea className="input" rows={3} value={selectedText} onChange={(e) => setSelectedText(e.target.value)} onBlur={() => void persist({ selected_text: selectedText })} />
      </label>

      <div className="pane-sub">Belgilangan odamlar (avto-javob ularga yuboriladi)</div>
      <div className="target-add">
        <input className="input" placeholder="Telegram ID" value={targetId} onChange={(e) => setTargetId(e.target.value)} />
        <input className="input" placeholder="Ism (ixtiyoriy)" value={targetName} onChange={(e) => setTargetName(e.target.value)} />
        <button className="btn primary" onClick={addTarget}>Qo'shish</button>
      </div>
      <div className="target-list">
        {settings?.auto_reply.targets.map((t) => (
          <div className="target-item" key={t.tg_user_id}>
            <Avatar name={t.name || String(t.tg_user_id)} size={34} />
            <span>{t.name || t.tg_user_id}</span>
            <button className="icon-btn" onClick={() => void removeTarget(t.tg_user_id)} title="O'chirish">
              <IconTrash size={18} />
            </button>
          </div>
        ))}
        {(!settings?.auto_reply.targets.length) && <div className="muted">Belgilangan odamlar yo'q — hammaga asosiy matn yuboriladi.</div>}
      </div>
      {msg && <div className="settings-msg">{msg}</div>}
    </div>
  );
}

// ---------------- Lotus ----------------
function LotusTab() {
  const { token } = useStore();
  const [lang, setLang] = useState("uz");
  const [voice, setVoice] = useState(false);
  const [chat, setChat] = useState<{ role: "user" | "ai"; text: string }[]>([]);
  const [input, setInput] = useState("");
  const [reminders, setReminders] = useState<{ id: number; text: string; due_at: string }[]>([]);

  useEffect(() => {
    if (!token) return;
    void api.lotusSettings(token).then((s) => { setLang(s.language); setVoice(s.voice_enabled); });
    void api.lotusReminders(token).then((r) => setReminders(r.reminders));
  }, [token]);

  if (!token) return null;

  async function setLanguage(l: string) {
    setLang(l);
    await api.updateLotusSettings({ language: l }, token!);
  }

  async function toggleVoice(v: boolean) {
    setVoice(v);
    await api.updateLotusSettings({ voice_enabled: v }, token!);
  }

  async function send() {
    const t = input.trim();
    if (!t) return;
    setInput("");
    setChat((c) => [...c, { role: "user", text: t }]);
    const res = await api.lotusChat(t, token!);
    setChat((c) => [...c, { role: "ai", text: res.reply }]);
  }

  return (
    <div className="settings-pane">
      <div className="pane-head">
        <div className="lotus-avatar"><IconStar size={26} /></div>
        <div>
          <div className="pane-title">Lotus 0.0.1</div>
          <div className="muted">Shaxsiy AI yordamchingiz</div>
        </div>
      </div>

      <label className="field">
        <span>Til</span>
        <div className="seg">
          {["uz", "ru", "en"].map((l) => (
            <button key={l} className={`seg-btn ${lang === l ? "active" : ""}`} onClick={() => void setLanguage(l)}>
              {l.toUpperCase()}
            </button>
          ))}
        </div>
      </label>

      <label className="check-row">
        <input type="checkbox" checked={voice} onChange={(e) => void toggleVoice(e.target.checked)} />
        <span><IconMic size={16} /> Voice chat</span>
      </label>

      <div className="lotus-chat">
        {chat.length === 0 && <div className="muted">Lotus'dan biror narsa so'rang yoki "Yordam" deb yozing.</div>}
        {chat.map((c, i) => (
          <div key={i} className={`lotus-bubble ${c.role}`}>{c.text}</div>
        ))}
      </div>
      <div className="composer-mini">
        <input className="input" placeholder="Lotus'ga yozing..." value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && void send()} />
        <button className="btn send" onClick={() => void send()}><IconSend size={18} /></button>
      </div>

      <div className="pane-sub">Eslatmalar</div>
      {reminders.map((r) => (
        <div className="target-item" key={r.id}>
          <span>{r.text}</span>
          <span className="muted">{new Date(r.due_at).toLocaleString()}</span>
        </div>
      ))}
      {reminders.length === 0 && <div className="muted">Faol eslatmalar yo'q</div>}
    </div>
  );
}

// ---------------- Musiqa ----------------
function MusicTab() {
  const { current, token, appUser } = useStore();
  const [music, setMusic] = useState<MusicPost[]>([]);
  const [title, setTitle] = useState("");
  const [performer, setPerformer] = useState("");
  const [caption, setCaption] = useState("");
  const [msg, setMsg] = useState("");
  const isAdmin = !!appUser?.is_admin || !!appUser?.is_owner;

  useEffect(() => {
    if (!current || !token) return;
    void api.musicList(current.id, token).then((m) => setMusic(m.music));
  }, [current, token]);

  if (!current || !token) return null;

  async function create() {
    if (!title.trim()) return;
    setMsg("");
    try {
      await api.createMusic(current!.id, { title, performer: performer || undefined, caption }, token!);
      setTitle("");
      setPerformer("");
      setCaption("");
      setMusic((await api.musicList(current!.id, token!)).music);
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  async function react(p: MusicPost, r: string) {
    await api.reactMusic({ music_post_id: p.id, reaction: r, user_tg_id: current!.id }, token!);
    setMusic((await api.musicList(current!.id, token!)).music);
  }

  return (
    <div className="settings-pane">
      {isAdmin && (
        <>
          <div className="pane-sub">Musiqa taklifi qo'shish</div>
          <label className="field"><span>Nomi</span><input className="input" value={title} onChange={(e) => setTitle(e.target.value)} /></label>
          <label className="field"><span>Ijrochi</span><input className="input" value={performer} onChange={(e) => setPerformer(e.target.value)} /></label>
          <label className="field"><span>Izoh</span><input className="input" value={caption} onChange={(e) => setCaption(e.target.value)} /></label>
          <button className="btn primary" onClick={create}>Joylash</button>
          {msg && <div className="settings-msg">{msg}</div>}
        </>
      )}

      <div className="pane-sub">Takliflar</div>
      {music.length === 0 && <div className="muted">Hozircha musiqa taklifi yo'q</div>}
      {music.map((p) => (
        <div className="music-card" key={p.id}>
          <div className="music-info">
            <IconMusic size={22} />
            <div>
              <div className="music-title">{p.title}</div>
              <div className="muted">{p.performer || "Noma'lum ijrochi"}</div>
              {p.caption && <div className="muted">{p.caption}</div>}
            </div>
          </div>
          <div className="music-actions">
            <button className="icon-btn" title="Like" onClick={() => void react(p, "like")}><IconStar size={18} /></button>
            <button className="icon-btn" title="Dislike" onClick={() => void react(p, "dislike")}><IconX size={18} /></button>
          </div>
          {p.reactions.length > 0 && (
            <div className="muted">{p.reactions.length} ta reaksiya</div>
          )}
        </div>
      ))}
    </div>
  );
}

// ---------------- Admin ----------------
function AdminTab() {
  const { token, appUser } = useStore();
  const [accounts, setAccounts] = useState<AdminAccount[]>([]);
  const [admins, setAdmins] = useState<{ tg_user_id: number; role: string }[]>([]);
  const [interval, setInterval] = useState(2);
  const [allowed, setAllowed] = useState<number[]>([1, 2, 4, 6, 8]);
  const [newAdminId, setNewAdminId] = useState("");
  const [msg, setMsg] = useState("");
  const isOwner = !!appUser?.is_owner;

  useEffect(() => {
    if (!token) return;
    void api.adminOverview(token).then((r) => setAccounts(r.accounts));
    void api.listAdmins(token).then((r) => setAdmins(r.admins));
    void api.reportInterval(token).then((r) => { setInterval(r.hours); setAllowed(r.allowed); });
  }, [token]);

  if (!token) return null;

  async function toggleVip(a: AdminAccount) {
    const target = !a.app_user.is_vip;
    if (!window.confirm(`Haqiqatan ham ${a.bot_name || a.first_name || a.phone} ni ${target ? "VIP" : "oddiy"} qilinsinmi?`)) return;
    await api.setVip(a.id, target, token!);
    setAccounts((await api.adminOverview(token!)).accounts);
  }

  async function addAdmin() {
    const id = Number(newAdminId.trim());
    if (!id) return;
    setMsg("");
    try {
      await api.addAdmin(id, token!);
      setNewAdminId("");
      setAdmins((await api.listAdmins(token!)).admins);
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  async function setIntervalH(h: number) {
    setInterval(h);
    await api.setReportInterval(h, token!);
  }

  return (
    <div className="settings-pane">
      <div className="pane-sub">Ulangan akkauntlar ({accounts.length})</div>
      <div className="admin-list">
        {accounts.map((a) => (
          <div className="admin-row" key={a.id}>
            <Avatar name={a.bot_name || a.first_name || a.phone} size={40} />
            <div className="admin-row-body">
              <div className="admin-row-title">
                {a.bot_name || a.first_name || a.phone}
                {a.app_user.is_owner && <IconCrown size={14} />}
                {a.app_user.is_admin && !a.app_user.is_owner && <IconUser size={14} />}
                {a.app_user.is_vip && <IconStar size={14} />}
              </div>
              <div className="muted">{a.dialogs_count} chat, {a.messages_count} xabar</div>
            </div>
            <button className={`btn ${a.app_user.is_vip ? "danger" : "ghost"}`} onClick={() => void toggleVip(a)}>
              {a.app_user.is_vip ? "VIP dan olib tashlash" : "VIP qilish"}
            </button>
          </div>
        ))}
      </div>

      <div className="pane-sub">Hisobot oraliq (Admin AI)</div>
      <div className="seg">
        {allowed.map((h) => (
          <button key={h} className={`seg-btn ${interval === h ? "active" : ""}`} onClick={() => void setIntervalH(h)}>
            {h} soat
          </button>
        ))}
      </div>

      {isOwner && (
        <>
          <div className="pane-sub">Adminlar</div>
          {admins.map((a) => (
            <div className="target-item" key={a.tg_user_id}>
              <span>{a.tg_user_id}</span>
              <span className="muted">{a.role}</span>
            </div>
          ))}
          <div className="target-add">
            <input className="input" placeholder="Yangi admin Telegram ID" value={newAdminId} onChange={(e) => setNewAdminId(e.target.value)} />
            <button className="btn primary" onClick={addAdmin}>Qo'shish</button>
          </div>
        </>
      )}
      {msg && <div className="settings-msg">{msg}</div>}
    </div>
  );
}
