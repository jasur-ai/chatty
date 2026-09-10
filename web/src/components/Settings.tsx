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
import type {
  AdminAccount,
  Analytics,
  BotSettings,
  Contact,
  Dialog,
  ForwardRule,
  MusicPost,
  QuickReply,
  SearchResult,
  StarredMsg,
} from "../types";
import { Avatar } from "./Avatar";

type Tab = "bot" | "auto" | "pro" | "lotus" | "music" | "vip" | "admin";

export function Settings() {
  const { current, token, appUser, closeSettings } = useStore();
  const [tab, setTab] = useState<Tab>("bot");
  const isAdmin = !!appUser?.is_admin || !!appUser?.is_owner;
  const isVip = isAdmin || !!appUser?.is_vip;

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
          <NavBtn id="pro" icon={<IconStar size={18} />} label="Pro" active={tab === "pro"} onClick={() => setTab("pro")} />
          <NavBtn id="lotus" icon={<IconStar size={18} />} label="Lotus" active={tab === "lotus"} onClick={() => setTab("lotus")} />
          <NavBtn id="music" icon={<IconMusic size={18} />} label="Musiqa" active={tab === "music"} onClick={() => setTab("music")} />
          {isVip && (
            <NavBtn id="vip" icon={<IconCrown size={18} />} label="VIP" active={tab === "vip"} onClick={() => setTab("vip")} />
          )}
          {isAdmin && (
            <NavBtn id="admin" icon={<IconCrown size={18} />} label="Admin" active={tab === "admin"} onClick={() => setTab("admin")} />
          )}
        </nav>

        <div className="settings-body">
          {tab === "bot" && <BotTab />}
          {tab === "auto" && <AutoTab />}
          {tab === "pro" && <ProTab />}
          {tab === "lotus" && <LotusTab />}
          {tab === "music" && <MusicTab />}
          {tab === "vip" && isVip && <VipTab />}
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

// ---------------- Pro funksiyalar (barcha foydalanuvchilar uchun) ----------------
function ProTab() {
  const { current, token, dialogs } = useStore();
  const [searchQ, setSearchQ] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [scheduled, setScheduled] = useState<{ id: number; dialog_id: number; text: string; send_at: string }[]>([]);
  const [schedText, setSchedText] = useState("");
  const [schedDialog, setSchedDialog] = useState(0);
  const [schedAt, setSchedAt] = useState("");
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [ttl, setTtl] = useState(0);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    if (!current || !token) return;
    void api.scheduledList(current.id, token).then((r) => setScheduled(r.scheduled));
    void api.analytics(current.id, token).then((a) => setAnalytics(a));
    void api.autoDeleteGet(current.id, token).then((r) => setTtl(r.ttl_seconds));
  }, [current, token]);

  if (!current || !token) return null;

  async function doSearch() {
    if (!searchQ.trim()) return;
    const r = await api.searchMessages(current!.id, searchQ.trim(), token!);
    setResults(r.results);
  }

  async function addSchedule() {
    if (!schedText.trim() || !schedDialog || !schedAt) return;
    const send_at = new Date(schedAt).toISOString();
    await api.scheduleMessage(current!.id, { dialog_id: schedDialog, text: schedText, send_at }, token!);
    setSchedText("");
    setSchedAt("");
    setScheduled((await api.scheduledList(current!.id, token!)).scheduled);
  }

  async function delSchedule(id: number) {
    await api.deleteScheduled(id, token!);
    setScheduled((await api.scheduledList(current!.id, token!)).scheduled);
  }

  async function doExport(fmt: string) {
    setMsg("");
    try {
      const r = await api.exportDialog(current!.id, schedDialog, fmt, token!);
      setMsg(`Eksport tayyor: ${r.count} ta xabar — ${r.url}`);
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  async function doBackup() {
    setMsg("");
    try {
      const r = await api.backup(current!.id, token!);
      setMsg(`Zaxira tayyor: ${r.dialogs} ta chat — ${r.url}`);
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  async function setAutoDelete(v: number) {
    setTtl(v);
    await api.autoDeleteSet(current!.id, v, token!);
  }

  return (
    <div className="settings-pane">
      <div className="pane-sub">Rejalashtirilgan xabarlar</div>
      <div className="target-add">
        <select className="input" value={schedDialog} onChange={(e) => setSchedDialog(Number(e.target.value))}>
          <option value={0}>Chat tanlang</option>
          {dialogs.map((d) => (
            <option key={d.id} value={d.id}>{d.title}</option>
          ))}
        </select>
        <input className="input" type="datetime-local" value={schedAt} onChange={(e) => setSchedAt(e.target.value)} />
      </div>
      <div className="target-add">
        <input className="input" placeholder="Xabar matni" value={schedText} onChange={(e) => setSchedText(e.target.value)} />
        <button className="btn primary" onClick={addSchedule}>Rejalash</button>
      </div>
      {scheduled.map((s) => (
        <div className="target-item" key={s.id}>
          <span>{s.text}</span>
          <span className="muted">{new Date(s.send_at).toLocaleString()}</span>
          <button className="icon-btn" onClick={() => void delSchedule(s.id)}><IconTrash size={16} /></button>
        </div>
      ))}
      {scheduled.length === 0 && <div className="muted">Rejalashtirilgan xabar yo'q</div>}

      <div className="pane-sub">Qidiruv (barcha chatlar)</div>
      <div className="composer-mini">
        <input className="input" placeholder="Qidiruv..." value={searchQ} onChange={(e) => setSearchQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && void doSearch()} />
        <button className="btn primary" onClick={() => void doSearch()}>Qidirish</button>
      </div>
      {results.map((r) => (
        <div className="target-item" key={`${r.dialog_id}-${r.tg_id}`}>
          <div>
            <div className="admin-row-title">{r.dialog_title}</div>
            <div className="muted">{r.text}</div>
          </div>
          <span className="muted">{new Date(r.date).toLocaleString()}</span>
        </div>
      ))}

      <div className="pane-sub">Analitika</div>
      {analytics && (
        <div className="analytics-grid">
          <div className="stat"><b>{analytics.total_messages}</b><span>jami xabar</span></div>
          <div className="stat"><b>{analytics.in_messages}</b><span>kiruvchi</span></div>
          <div className="stat"><b>{analytics.out_messages}</b><span>chiqim</span></div>
          <div className="stat"><b>{analytics.dialogs}</b><span>chatlar</span></div>
        </div>
      )}

      <div className="pane-sub">Eksport va zaxira</div>
      <div className="pane-row">
        <select className="input" value={schedDialog} onChange={(e) => setSchedDialog(Number(e.target.value))}>
          <option value={0}>Chat tanlang (eksport)</option>
          {dialogs.map((d) => (
            <option key={d.id} value={d.id}>{d.title}</option>
          ))}
        </select>
        <button className="btn ghost" disabled={!schedDialog} onClick={() => void doExport("json")}>JSON</button>
        <button className="btn ghost" disabled={!schedDialog} onClick={() => void doExport("csv")}>CSV</button>
        <button className="btn ghost" onClick={() => void doBackup()}>To'liq zaxira</button>
      </div>

      <div className="pane-sub">Avto-o'chirish (yuborilgan xabarlar)</div>
      <div className="seg">
        {[{ v: 0, l: "O'chiq" }, { v: 3600, l: "1 soat" }, { v: 86400, l: "24 soat" }, { v: 604800, l: "7 kun" }].map((o) => (
          <button key={o.v} className={`seg-btn ${ttl === o.v ? "active" : ""}`} onClick={() => void setAutoDelete(o.v)}>{o.l}</button>
        ))}
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

// ---------------- VIP (20 mustaqil funksiya) ----------------
function VipTab() {
  const { current, token, dialogs } = useStore();
  const [accent, setAccent] = useState("#3390ec");
  const [quickReplies, setQuickReplies] = useState<QuickReply[]>([]);
  const [qrLabel, setQrLabel] = useState("");
  const [qrText, setQrText] = useState("");
  const [starred, setStarred] = useState<StarredMsg[]>([]);
  const [rules, setRules] = useState<ForwardRule[]>([]);
  const [afKeyword, setAfKeyword] = useState("");
  const [afTarget, setAfTarget] = useState(0);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [members, setMembers] = useState<Contact[]>([]);
  const [membersDialog, setMembersDialog] = useState(0);
  const [receipts, setReceipts] = useState<{ sent: number; read: number; delivered_not_read: number; read_rate: number } | null>(null);
  const [receiptsDialog, setReceiptsDialog] = useState(0);
  const [media, setMedia] = useState<{ tg_id: number; media_type: string; date: string }[]>([]);
  const [mediaDialog, setMediaDialog] = useState(0);
  const [groupAction, setGroupAction] = useState("kick");
  const [groupUserId, setGroupUserId] = useState("");
  const [groupDialog, setGroupDialog] = useState(0);
  const [pollQ, setPollQ] = useState("");
  const [pollOpts, setPollOpts] = useState("");
  const [pollDialog, setPollDialog] = useState(0);
  const [sticker, setSticker] = useState("");
  const [stickerDialog, setStickerDialog] = useState(0);
  const [bio, setBio] = useState("");
  const [username, setUsername] = useState("");
  const [chanText, setChanText] = useState("");
  const [chanDialog, setChanDialog] = useState(0);
  const [chanAt, setChanAt] = useState("");
  const [msg, setMsg] = useState("");

  useEffect(() => {
    if (!current || !token) return;
    void api.vipQuickReplies(current.id, token).then((r) => setQuickReplies(r.quick_replies));
    void api.vipStarred(current.id, token).then((r) => setStarred(r.starred));
    void api.vipAutoForwardList(current.id, token).then((r) => setRules(r.rules));
    void api.vipThemeGet(current.id, token).then((r) => setAccent(r.accent));
  }, [current, token]);

  if (!current || !token) return null;

  async function run(fn: () => Promise<unknown>, ok = "Bajarildi") {
    setMsg("");
    try {
      await fn();
      setMsg(ok);
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  async function addQuickReply() {
    if (!qrLabel.trim() || !qrText.trim()) return;
    await api.vipQuickReplyAdd(current!.id, qrLabel, qrText, token!);
    setQrLabel("");
    setQrText("");
    setQuickReplies((await api.vipQuickReplies(current!.id, token!)).quick_replies);
  }

  async function addRule() {
    if (!afKeyword.trim() || !afTarget) return;
    await api.vipAutoForwardAdd(current!.id, { keyword: afKeyword, source_dialog_id: 0, target_dialog_id: afTarget }, token!);
    setAfKeyword("");
    setRules((await api.vipAutoForwardList(current!.id, token!)).rules);
  }

  return (
    <div className="settings-pane">
      <div className="pane-sub">Shaxsiy mavzu</div>
      <div className="pane-row">
        {["#3390ec", "#f06292", "#7c4dff", "#00b894", "#e17055", "#00a8ff"].map((c) => (
          <button
            key={c}
            className="color-swatch"
            style={{ background: c, outline: accent === c ? `3px solid ${c}` : "none" }}
            onClick={() => void run(() => api.vipThemeSet(current!.id, c, token!), "Mavzu saqlandi")}
          />
        ))}
      </div>

      <div className="pane-sub">Tezkor javoblar</div>
      <div className="target-add">
        <input className="input" placeholder="Yorliq" value={qrLabel} onChange={(e) => setQrLabel(e.target.value)} />
        <input className="input" placeholder="Matn" value={qrText} onChange={(e) => setQrText(e.target.value)} />
        <button className="btn primary" onClick={addQuickReply}>Qo'shish</button>
      </div>
      {quickReplies.map((q) => (
        <div className="target-item" key={q.id}>
          <b>{q.label}</b>
          <span>{q.text}</span>
          <button className="icon-btn" onClick={() => void run(() => api.vipQuickReplyRemove(q.id, token!).then(() => setQuickReplies((prev) => prev.filter((x) => x.id !== q.id))))}>
            <IconTrash size={16} />
          </button>
        </div>
      ))}

      <div className="pane-sub">Avto-forward qoidalari</div>
      <div className="target-add">
        <input className="input" placeholder="Kalit so'z" value={afKeyword} onChange={(e) => setAfKeyword(e.target.value)} />
        <select className="input" value={afTarget} onChange={(e) => setAfTarget(Number(e.target.value))}>
          <option value={0}>Target chat</option>
          {dialogs.map((d) => <option key={d.id} value={d.id}>{d.title}</option>)}
        </select>
        <button className="btn primary" onClick={addRule}>Qo'shish</button>
      </div>
      {rules.map((r) => (
        <div className="target-item" key={r.id}>
          <b>{r.keyword}</b>
          <span className="muted">→ chat #{r.target_dialog_id}</span>
          <button className="icon-btn" onClick={() => void run(() => api.vipAutoForwardRemove(r.id, token!).then(() => setRules((prev) => prev.filter((x) => x.id !== r.id))))}>
            <IconTrash size={16} />
          </button>
        </div>
      ))}

      <div className="pane-sub">Yulduzchalangan xabarlar ({starred.length})</div>
      {starred.map((s) => (
        <div className="target-item" key={s.id}>
          <div><div className="admin-row-title">{s.dialog_title}</div><div className="muted">{s.text}</div></div>
          <button className="icon-btn" onClick={() => void run(() => api.vipStarRemove(s.id, token!).then(() => setStarred((prev) => prev.filter((x) => x.id !== s.id))))}>
            <IconTrash size={16} />
          </button>
        </div>
      ))}
      {starred.length === 0 && <div className="muted">Yulduzchalangan xabar yo'q (xabardagi yulduzcha tugmasi bilan qo'shiladi)</div>}

      <div className="pane-sub">Profil tahriri</div>
      <div className="target-add">
        <input className="input" placeholder="Username (yangi)" value={username} onChange={(e) => setUsername(e.target.value)} />
        <input className="input" placeholder="Bio" value={bio} onChange={(e) => setBio(e.target.value)} />
        <button className="btn primary" onClick={() => void run(() => api.vipProfile(current!.id, { bio: bio || undefined, username: username || undefined }, token!))}>
          Saqlash
        </button>
      </div>

      <div className="pane-sub">Guruh boshqaruvi</div>
      <div className="target-add">
        <select className="input" value={groupDialog} onChange={(e) => setGroupDialog(Number(e.target.value))}>
          <option value={0}>Guruh</option>
          {dialogs.filter((d) => d.type !== "user").map((d) => <option key={d.id} value={d.id}>{d.title}</option>)}
        </select>
        <select className="input" value={groupAction} onChange={(e) => setGroupAction(e.target.value)}>
          {["kick", "ban", "unban", "promote", "demote"].map((a) => <option key={a} value={a}>{a}</option>)}
        </select>
        <input className="input" placeholder="User ID" value={groupUserId} onChange={(e) => setGroupUserId(e.target.value)} />
        <button className="btn primary" onClick={() => void run(() => api.vipGroupManage(current!.id, { dialog_id: groupDialog, user_id: Number(groupUserId), action: groupAction }, token!))}>
          Bajarish
        </button>
      </div>

      <div className="pane-sub">Guruh a'zolari</div>
      <div className="target-add">
        <select className="input" value={membersDialog} onChange={(e) => setMembersDialog(Number(e.target.value))}>
          <option value={0}>Guruh</option>
          {dialogs.filter((d) => d.type !== "user").map((d) => <option key={d.id} value={d.id}>{d.title}</option>)}
        </select>
        <button className="btn primary" onClick={() => void run(() => api.vipMembers(current!.id, membersDialog, token!).then((r) => setMembers(r.members)), "Yuklandi")}>
          Ro'yxat
        </button>
      </div>
      {members.length > 0 && <div className="muted">{members.length} ta a'zo</div>}

      <div className="pane-sub">Kontaktlar</div>
      <button className="btn ghost" onClick={() => void run(() => api.vipContacts(current!.id, token!).then((r) => setContacts(r.contacts)), "Yuklandi")}>
        Kontaktlarni yuklash
      </button>
      {contacts.length > 0 && <div className="muted">{contacts.length} ta kontakt</div>}

      <div className="pane-sub">O'qish hisoboti (✓/✓✓)</div>
      <div className="target-add">
        <select className="input" value={receiptsDialog} onChange={(e) => setReceiptsDialog(Number(e.target.value))}>
          <option value={0}>Chat</option>
          {dialogs.map((d) => <option key={d.id} value={d.id}>{d.title}</option>)}
        </select>
        <button className="btn primary" onClick={() => void run(() => api.vipReadReceipts(current!.id, receiptsDialog, token!).then((r) => setReceipts(r)), "Yuklandi")}>
          Hisobot
        </button>
      </div>
      {receipts && (
        <div className="analytics-grid">
          <div className="stat"><b>{receipts.sent}</b><span>yuborilgan</span></div>
          <div className="stat"><b>{receipts.read}</b><span>o'qilgan</span></div>
          <div className="stat"><b>{receipts.read_rate}%</b><span>o'qish darajasi</span></div>
        </div>
      )}

      <div className="pane-sub">Media galereya</div>
      <div className="target-add">
        <select className="input" value={mediaDialog} onChange={(e) => setMediaDialog(Number(e.target.value))}>
          <option value={0}>Chat</option>
          {dialogs.map((d) => <option key={d.id} value={d.id}>{d.title}</option>)}
        </select>
        <button className="btn primary" onClick={() => void run(() => api.vipMediaGallery(current!.id, mediaDialog, token!).then((r) => setMedia(r.media)), "Yuklandi")}>
          Ko'rish
        </button>
      </div>
      {media.length > 0 && <div className="muted">{media.length} ta media</div>}

      <div className="pane-sub">So'rov (poll)</div>
      <div className="target-add">
        <select className="input" value={pollDialog} onChange={(e) => setPollDialog(Number(e.target.value))}>
          <option value={0}>Chat</option>
          {dialogs.filter((d) => d.type !== "user").map((d) => <option key={d.id} value={d.id}>{d.title}</option>)}
        </select>
        <input className="input" placeholder="Savol" value={pollQ} onChange={(e) => setPollQ(e.target.value)} />
        <input className="input" placeholder="Variantlar (vergul bilan)" value={pollOpts} onChange={(e) => setPollOpts(e.target.value)} />
        <button className="btn primary" onClick={() => void run(() => api.vipPoll(current!.id, pollDialog, pollQ, pollOpts.split(",").map((s) => s.trim()).filter(Boolean), token!))}>
          Yaratish
        </button>
      </div>

      <div className="pane-sub">Stiker/GIF (emoji)</div>
      <div className="target-add">
        <select className="input" value={stickerDialog} onChange={(e) => setStickerDialog(Number(e.target.value))}>
          <option value={0}>Chat</option>
          {dialogs.map((d) => <option key={d.id} value={d.id}>{d.title}</option>)}
        </select>
        <input className="input" placeholder="Emoji (masalan 👍)" value={sticker} onChange={(e) => setSticker(e.target.value)} />
        <button className="btn primary" onClick={() => void run(() => api.vipSticker(current!.id, stickerDialog, sticker, token!))}>
          Yuborish
        </button>
      </div>

      <div className="pane-sub">Kanalga rejalashtirilgan post</div>
      <div className="target-add">
        <select className="input" value={chanDialog} onChange={(e) => setChanDialog(Number(e.target.value))}>
          <option value={0}>Kanal</option>
          {dialogs.filter((d) => d.type === "channel").map((d) => <option key={d.id} value={d.id}>{d.title}</option>)}
        </select>
        <input className="input" type="datetime-local" value={chanAt} onChange={(e) => setChanAt(e.target.value)} />
      </div>
      <div className="target-add">
        <input className="input" placeholder="Post matni" value={chanText} onChange={(e) => setChanText(e.target.value)} />
        <button className="btn primary" onClick={() => void run(() => api.vipChannelPost(current!.id, { dialog_id: chanDialog, text: chanText, send_at: new Date(chanAt).toISOString(), silent: false }, token!))}>
          Rejalash
        </button>
      </div>

      {msg && <div className="settings-msg">{msg}</div>}
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
  const [openAcc, setOpenAcc] = useState<number | null>(null);
  const [openDialogs, setOpenDialogs] = useState<Dialog[]>([]);
  const [loadingDialogs, setLoadingDialogs] = useState(false);
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

  async function toggleDialogs(a: AdminAccount) {
    if (openAcc === a.id) {
      setOpenAcc(null);
      setOpenDialogs([]);
      return;
    }
    setOpenAcc(a.id);
    setLoadingDialogs(true);
    try {
      const r = await api.chats(a.id, token!);
      setOpenDialogs(r.dialogs);
    } catch (e) {
      setMsg((e as Error).message);
      setOpenDialogs([]);
    } finally {
      setLoadingDialogs(false);
    }
  }

  return (
    <div className="settings-pane">
      <div className="pane-sub">Ulangan akkauntlar ({accounts.length})</div>
      <div className="admin-list">
        {accounts.map((a) => (
          <div className="admin-account" key={a.id}>
            <div className="admin-row">
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
              <button className="btn ghost" onClick={() => void toggleDialogs(a)}>
                {openAcc === a.id ? "Yopish" : "Chatlarni ko'rish"}
              </button>
              <button className={`btn ${a.app_user.is_vip ? "danger" : "ghost"}`} onClick={() => void toggleVip(a)}>
                {a.app_user.is_vip ? "VIP dan olib tashlash" : "VIP qilish"}
              </button>
            </div>

            {openAcc === a.id && (
              <div className="admin-dialogs">
                {loadingDialogs && <div className="muted">Yuklanmoqda…</div>}
                {!loadingDialogs && openDialogs.length === 0 && (
                  <div className="muted">Chatlar yo'q</div>
                )}
                {!loadingDialogs &&
                  openDialogs.map((d) => (
                    <div className="admin-dialog-row" key={d.id}>
                      <Avatar name={d.title} size={34} />
                      <div className="admin-dialog-body">
                        <span className="admin-dialog-title">{d.title}</span>
                        <span className="muted">{d.last_msg_text || ""}</span>
                      </div>
                      {d.unread_count > 0 && <span className="unread-badge">{d.unread_count}</span>}
                    </div>
                  ))}
              </div>
            )}
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
