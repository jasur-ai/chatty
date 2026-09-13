import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { IconChart, IconCrown, IconMusic, IconPlus, IconShield, IconShieldCheck, IconSpinner, IconUsers, IconX } from "../icons";
import { useStore } from "../store";
import type { AdminUser } from "../types";

type Tab = "users" | "music" | "reports" | "admins";

export function AdminPanel() {
  const { token, appUser, closeAdmin } = useStore();
  const [tab, setTab] = useState<Tab>("users");
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError("");
    try {
      const res = await api.adminUsers(token);
      setUsers(res.users);
    } catch (e) {
      setError((e as Error).message || "Yuklanmadi");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load]);

  async function toggleVip(u: AdminUser) {
    if (!token) return;
    setBusyId(u.id);
    try {
      await api.setVip(u.id, !u.is_vip, token);
      setUsers((prev) => prev.map((x) => (x.id === u.id ? { ...x, is_vip: !u.is_vip } : x)));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusyId(null);
    }
  }

  const isOwner = appUser?.is_owner;

  return (
    <section className="admin-panel">
      <header className="chat-header">
        <button className="icon-btn mobile-back" onClick={closeAdmin}>
          <IconX size={22} />
        </button>
        <IconShield size={22} />
        <div className="chat-header-info">
          <div className="chat-header-title">Admin boshqaruvi</div>
          <div className="chat-header-status muted">Nazorat paneli</div>
        </div>
      </header>

      <nav className="admin-tabs">
        <button className={`admin-tab ${tab === "users" ? "active" : ""}`} onClick={() => setTab("users")}>
          <IconUsers size={18} /> Foydalanuvchilar
        </button>
        <button className={`admin-tab ${tab === "music" ? "active" : ""}`} onClick={() => setTab("music")}>
          <IconMusic size={18} /> Musiqa
        </button>
        <button className={`admin-tab ${tab === "reports" ? "active" : ""}`} onClick={() => setTab("reports")}>
          <IconChart size={18} /> Hisobotlar
        </button>
        {isOwner && (
          <button className={`admin-tab ${tab === "admins" ? "active" : ""}`} onClick={() => setTab("admins")}>
            <IconShieldCheck size={18} /> Adminlar
          </button>
        )}
      </nav>

      <div className="admin-body">
        {tab === "users" && (
          <UsersTab users={users} loading={loading} error={error} busyId={busyId} toggleVip={toggleVip} onReload={load} />
        )}
        {tab === "music" && <MusicTab />}
        {tab === "reports" && <ReportsTab />}
        {tab === "admins" && isOwner && <AdminsTab />}
      </div>
    </section>
  );
}

function UsersTab({
  users,
  loading,
  error,
  busyId,
  toggleVip,
  onReload,
}: {
  users: AdminUser[];
  loading: boolean;
  error: string;
  busyId: number | null;
  toggleVip: (u: AdminUser) => void;
  onReload: () => void;
}) {
  if (loading) {
    return (
      <div className="admin-status">
        <IconSpinner size={22} /> <span>Yuklanmoqda…</span>
      </div>
    );
  }
  if (error) {
    return (
      <div className="admin-status error">
        {error}
        <button className="btn ghost" onClick={onReload}>Qayta urinish</button>
      </div>
    );
  }
  return (
    <div className="user-table">
      <div className="user-row user-row-head">
        <span>Foydalanuvchi</span>
        <span>Telefon</span>
        <span>Chatlar</span>
        <span>Xabarlar</span>
        <span>Status</span>
        <span>VIP</span>
      </div>
      {users.map((u) => (
        <div className="user-row" key={u.id}>
          <span className="user-cell-name">
            <strong>{u.bot_name || u.first_name || "—"}</strong>
            {u.username && <span className="muted"> @{u.username}</span>}
            {u.is_owner && <span className="badge badge-owner">Owner</span>}
            {u.is_admin && !u.is_owner && <span className="badge badge-admin">Admin</span>}
          </span>
          <span className="muted mono">{u.phone}</span>
          <span>{u.dialogs_count}</span>
          <span>{u.messages_count}</span>
          <span>
            <span className={`dot ${u.auth_step === "ready" ? "ok" : "off"}`} />
            {u.auth_step === "ready" ? "Faol" : "Ulangan emas"}
          </span>
          <span>
            <button
              className={`btn small ${u.is_vip ? "vip-on" : "ghost"}`}
              disabled={busyId === u.id || u.is_owner}
              onClick={() => toggleVip(u)}
              title={u.is_vip ? "VIP'ni olish" : "VIP qilish"}
            >
              {busyId === u.id ? <IconSpinner size={16} /> : <IconCrown size={16} />}
              {u.is_vip ? "VIP" : "Yo'q"}
            </button>
          </span>
        </div>
      ))}
      {users.length === 0 && <div className="admin-status muted">Foydalanuvchilar yo'q</div>}
    </div>
  );
}

function MusicTab() {
  const { token, current } = useStore();
  const [posts, setPosts] = useState<{ id: number; title: string; performer: string | null; caption: string; reactions: unknown[] }[]>([]);
  const [title, setTitle] = useState("");
  const [performer, setPerformer] = useState("");
  const [caption, setCaption] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  async function load() {
    if (!token || !current) return;
    setLoading(true);
    try {
      const res = await api.musicList(current.id, token);
      setPosts(res.music);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, current?.id]);

  async function submit() {
    if (!token || !current || !title.trim() || saving) return;
    setSaving(true);
    setMsg("");
    try {
      await api.createMusic(current.id, { title: title.trim(), performer: performer.trim() || undefined, caption }, token);
      setTitle("");
      setPerformer("");
      setCaption("");
      setMsg("Musiqa qo'shildi");
      await load();
    } catch (e) {
      setMsg((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="music-admin">
      <div className="pane">
        <div className="pane-title">Yangi musiqa qo'shish</div>
        <input className="input" placeholder="Nomi (masalan: Qo'shiq nomi)" value={title} onChange={(e) => setTitle(e.target.value)} />
        <input className="input" placeholder="Ijrochi (ixtiyoriy)" value={performer} onChange={(e) => setPerformer(e.target.value)} />
        <input className="input" placeholder="Izoh (ixtiyoriy)" value={caption} onChange={(e) => setCaption(e.target.value)} />
        <button className="btn primary" disabled={!title.trim() || saving} onClick={() => void submit()}>
          {saving ? <IconSpinner size={18} /> : <IconPlus size={18} />} Qo'shish
        </button>
        {msg && <div className="admin-status">{msg}</div>}
      </div>

      <div className="music-list">
        {loading ? (
          <div className="admin-status"><IconSpinner size={20} /> Yuklanmoqda…</div>
        ) : posts.length === 0 ? (
          <div className="admin-status muted">Musiqa yo'q</div>
        ) : (
          posts.map((p) => (
            <div className="music-item" key={p.id}>
              <div className="music-item-body">
                <strong>{p.title}</strong>
                {p.performer && <span className="muted"> — {p.performer}</span>}
                {p.caption && <div className="muted">{p.caption}</div>}
              </div>
              <span className="muted">{p.reactions.length} reaksiya</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function ReportsTab() {
  const { token } = useStore();
  const [reports, setReports] = useState<{ id: number; body: string; created_at: string }[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    api.adminReports(token)
      .then((r) => setReports(r.reports))
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) return <div className="admin-status"><IconSpinner size={20} /> Yuklanmoqda…</div>;
  if (reports.length === 0) return <div className="admin-status muted">AI hisobotlar hozircha yo'q</div>;
  return (
    <div className="report-list">
      {reports.map((r) => (
        <div className="report-item" key={r.id}>
          <div className="muted small">{new Date(r.created_at).toLocaleString("uz-UZ")}</div>
          <div className="report-body">{r.body}</div>
        </div>
      ))}
    </div>
  );
}

function AdminsTab() {
  const { token } = useStore();
  const [admins, setAdmins] = useState<{ tg_user_id: number; role: string }[]>([]);
  const [tgId, setTgId] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  async function load() {
    if (!token) return;
    setLoading(true);
    try {
      const res = await api.listAdmins(token);
      setAdmins(res.admins);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function add() {
    const id = Number(tgId.trim());
    if (!token || !id || busy) return;
    setBusy(true);
    setMsg("");
    try {
      await api.addAdmin(id, token);
      setTgId("");
      setMsg("Admin qo'shildi");
      await load();
    } catch (e) {
      setMsg((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: number) {
    if (!token) return;
    try {
      await api.removeAdmin(id, token);
      await load();
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  return (
    <div className="admins-admin">
      <div className="pane">
        <div className="pane-title">Admin qo'shish (tg_user_id)</div>
        <input className="input mono" placeholder="Telegram user ID" value={tgId} onChange={(e) => setTgId(e.target.value)} />
        <button className="btn primary" disabled={!tgId.trim() || busy} onClick={() => void add()}>
          {busy ? <IconSpinner size={18} /> : <IconPlus size={18} />} Qo'shish
        </button>
        {msg && <div className="admin-status">{msg}</div>}
      </div>
      <div className="user-table">
        <div className="user-row user-row-head"><span>tg_user_id</span><span>Rol</span><span>Amal</span></div>
        {loading ? (
          <div className="admin-status"><IconSpinner size={18} /> Yuklanmoqda…</div>
        ) : (
          admins.map((a) => (
            <div className="user-row" key={a.tg_user_id}>
              <span className="mono">{a.tg_user_id}</span>
              <span>{a.role === "owner" ? "Owner" : "Admin"}</span>
              <span>
                <button className="btn small danger" onClick={() => void remove(a.tg_user_id)}>
                  <IconX size={16} />
                </button>
              </span>
            </div>
          ))
        )}
        {!loading && admins.length === 0 && <div className="admin-status muted">Adminlar yo'q</div>}
      </div>
    </div>
  );
}
