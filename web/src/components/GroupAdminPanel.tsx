import { useMemo, useState } from "react";
import { api } from "../api";
import type { Dialog, GroupAdmins, InviteLinkResult, TagAllResult } from "../types";
import { IconMegaphone, IconShieldCheck, IconSpinner, IconUsers } from "../icons";
import { ConfirmDialog } from "./ConfirmDialog";

type Props = {
  accountId: number;
  token: string;
  dialogs: Dialog[];
};

const RESTRICT_FLAGS = [
  { key: "media", label: "Media" },
  { key: "stickers", label: "Stiker" },
  { key: "preview", label: "Havola ko'rinishi" },
];

/**
 * Guruh / kanal boshqaruvi paneli.
 *
 * Akkaunt guruhda admin bo'lganda ishlaydigan to'liq boshqaruv to'plami:
 * adminlar ro'yxati, barchani teg qilish, so'rovnoma, taklif havolasi,
 * guruh sozlamalari, a'zolarni cheklash va ommaviy xabar.
 */
export function GroupAdminPanel({ accountId, token, dialogs }: Props) {
  const groups = useMemo(() => dialogs.filter((d) => d.type !== "user"), [dialogs]);

  const [dialogId, setDialogId] = useState(0);
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  // Adminlar
  const [admins, setAdmins] = useState<GroupAdmins | null>(null);

  // Barchani teg qilish
  const [tagText, setTagText] = useState("");
  const [tagPreview, setTagPreview] = useState<TagAllResult | null>(null);

  // So'rovnoma
  const [pollQ, setPollQ] = useState("");
  const [pollOpts, setPollOpts] = useState("");
  const [pollAnon, setPollAnon] = useState(false);
  const [pollMulti, setPollMulti] = useState(false);
  const [pollQuiz, setPollQuiz] = useState(false);
  const [pollCorrect, setPollCorrect] = useState(0);
  const [pollClose, setPollClose] = useState(0);

  // Taklif havolasi
  const [linkExpire, setLinkExpire] = useState(0);
  const [linkLimit, setLinkLimit] = useState(0);
  const [link, setLink] = useState<InviteLinkResult | null>(null);

  // Guruh sozlamalari
  const [newTitle, setNewTitle] = useState("");
  const [newAbout, setNewAbout] = useState("");
  const [slowmode, setSlowmode] = useState(0);

  // A'zo boshqaruvi
  const [userId, setUserId] = useState("");
  const [muteHours, setMuteHours] = useState(24);
  const [restrict, setRestrict] = useState<string[]>(["media"]);

  // Ommaviy xabar
  const [bcText, setBcText] = useState("");
  const [bcKind, setBcKind] = useState("");
  const [bcResult, setBcResult] = useState<{ sent: number; failed: number; total: number } | null>(null);
  const [confirmBc, setConfirmBc] = useState(false);

  // Xabarlarni o'chirish
  const [delCount, setDelCount] = useState(20);
  const [confirmDel, setConfirmDel] = useState(false);

  async function run<T>(label: string, fn: () => Promise<T>): Promise<T | null> {
    setBusy(label);
    setMsg("");
    setErr("");
    try {
      const r = await fn();
      setMsg(`${label} — bajarildi`);
      return r;
    } catch (e) {
      setErr(`${label}: ${(e as Error).message}`);
      return null;
    } finally {
      setBusy("");
    }
  }

  function needDialog(): boolean {
    if (!dialogId) {
      setErr("Avval guruh yoki kanalni tanlang");
      return false;
    }
    return true;
  }

  const groupOptions = groups.map((d) => (
    <option key={d.id} value={d.id}>
      {d.title}
    </option>
  ));

  return (
    <div className="pane">
      <div className="pane-title">Guruh va kanal boshqaruvi</div>
      <div className="hint">
        Bu bo'lim akkaunt guruh yoki kanalda admin bo'lganda ishlaydi. Barcha amallar sizning
        Telegram akkauntingiz nomidan bajariladi.
      </div>

      <div className="pane-sub">1. Guruh yoki kanal</div>
      <div className="target-add">
        <select className="input" value={dialogId} onChange={(e) => { setDialogId(Number(e.target.value)); setAdmins(null); setLink(null); setTagPreview(null); }}>
          <option value={0}>Tanlang</option>
          {groupOptions}
        </select>
        <button
          className="btn primary"
          disabled={!dialogId || busy === "admins"}
          onClick={() =>
            needDialog() &&
            void run("Adminlar", () =>
              api.vipAdmins(accountId, dialogId, token).then((r) => {
                setAdmins(r);
                return r;
              }),
            )
          }
        >
          {busy === "admins" ? <IconSpinner size={16} /> : <IconShieldCheck size={16} />}
          Admin huquqini tekshirish
        </button>
      </div>

      {admins && (
        <div className="analytics-grid">
          <div className="stat">
            <b>{admins.count}</b>
            <span>admin</span>
          </div>
          <div className="stat">
            <b>{admins.total_members ?? "?"}</b>
            <span>a'zo</span>
          </div>
          <div className="stat">
            <b>{admins.kind === "channel" ? "Kanal" : "Guruh"}</b>
            <span>turi</span>
          </div>
        </div>
      )}
      {admins?.creator && (
        <div className="muted">
          Egasi: @{admins.creator.username || admins.creator.first_name || admins.creator.id}
        </div>
      )}
      {admins && admins.admins.length > 0 && (
        <div className="admin-list">
          {admins.admins.map((a) => (
            <div className="admin-row" key={a.id}>
              <div className="admin-row-body">
                <div className="admin-row-title">
                  {a.is_creator && <IconShieldCheck size={14} />}
                  @{a.username || a.first_name || a.id}
                  {a.rank ? <span className="badge">{a.rank}</span> : null}
                  {a.bot ? <span className="chip">bot</span> : null}
                </div>
                <div className="muted">
                  {Object.entries(a.rights)
                    .filter(([, v]) => v)
                    .map(([k]) => k)
                    .join(", ") || "huquq yo'q"}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="pane-sub">2. Barchani teg qilish</div>
      <div className="hint">
        Barcha a'zolarning @username'larini xabarga qo'shadi. Uzun ro'yxat 50 tadan bo'laklanadi.
        Avval ko'rib chiqing, keyin yuboring.
      </div>
      <div className="target-add">
        <input
          className="input"
          placeholder="Xabar matni (ixtiyoriy)"
          value={tagText}
          onChange={(e) => setTagText(e.target.value)}
        />
        <button
          className="btn ghost"
          disabled={!dialogId || busy === "ko'rib chiqish"}
          onClick={() =>
            needDialog() &&
            void run("Ko'rib chiqish", () =>
              api.vipTagAll(accountId, { dialog_id: dialogId, text: tagText, preview: true }, token).then((r) => {
                setTagPreview(r);
                return r;
              }),
            )
          }
        >
          {busy === "ko'rib chiqish" ? <IconSpinner size={16} /> : <IconUsers size={16} />}
          Ko'rib chiqish
        </button>
        <button
          className="btn primary"
          disabled={!dialogId || !tagPreview || busy === "teg yuborish"}
          onClick={() =>
            needDialog() &&
            void run("Teg yuborish", () =>
              api.vipTagAll(accountId, { dialog_id: dialogId, text: tagText, preview: false }, token).then((r) => {
                setTagPreview(r);
                return r;
              }),
            )
          }
        >
          {busy === "teg yuborish" ? <IconSpinner size={16} /> : <IconMegaphone size={16} />}
          Yuborish
        </button>
      </div>
      {tagPreview && (
        <div className="muted">
          {tagPreview.total_members} a'zodan {tagPreview.with_username} tasida @username bor.
          {tagPreview.preview ? ` Rejada ${tagPreview.messages} ta xabar.` : ""}
          {tagPreview.messages_sent ? ` ${tagPreview.messages_sent} ta xabar yuborildi.` : ""}
        </div>
      )}
      {tagPreview?.chunks && tagPreview.chunks.length > 0 && (
        <div className="hint">{tagPreview.chunks[0]}</div>
      )}

      <div className="pane-sub">3. So'rovnoma</div>
      <div className="target-add">
        <input className="input" placeholder="Savol" value={pollQ} onChange={(e) => setPollQ(e.target.value)} />
        <input
          className="input"
          placeholder="Variantlar (vergul bilan)"
          value={pollOpts}
          onChange={(e) => setPollOpts(e.target.value)}
        />
        <label className="field">
          <input type="checkbox" checked={pollAnon} onChange={(e) => setPollAnon(e.target.checked)} />
          <span className="field-label">Anonim ovoz</span>
        </label>
        <label className="field">
          <input type="checkbox" checked={pollMulti} onChange={(e) => setPollMulti(e.target.checked)} />
          <span className="field-label">Bir nechta javob</span>
        </label>
        <label className="field">
          <input type="checkbox" checked={pollQuiz} onChange={(e) => setPollQuiz(e.target.checked)} />
          <span className="field-label">Viktorina</span>
        </label>
        {pollQuiz && (
          <input
            className="input"
            type="number"
            min={0}
            placeholder="To'g'ri javob raqami (0 dan)"
            value={pollCorrect}
            onChange={(e) => setPollCorrect(Number(e.target.value))}
          />
        )}
        <select className="input" value={pollClose} onChange={(e) => setPollClose(Number(e.target.value))}>
          <option value={0}>Muddatsiz</option>
          <option value={60}>1 daqiqada yopilsin</option>
          <option value={300}>5 daqiqada yopilsin</option>
          <option value={600}>10 daqiqada yopilsin</option>
        </select>
        <button
          className="btn primary"
          disabled={!dialogId || busy === "so'rovnoma"}
          onClick={() =>
            needDialog() &&
            void run("So'rovnoma", () =>
              api.vipPoll(
                accountId,
                dialogId,
                pollQ,
                pollOpts.split(",").map((s) => s.trim()).filter(Boolean),
                token,
                {
                  anonymous: pollAnon,
                  multiple_choice: pollMulti,
                  quiz: pollQuiz,
                  correct_option: pollCorrect,
                  close_period: pollClose,
                },
              ),
            )
          }
        >
          {busy === "so'rovnoma" ? <IconSpinner size={16} /> : null}
          So'rovnoma yuborish
        </button>
      </div>

      <div className="pane-sub">4. Taklif havolasi</div>
      <div className="target-add">
        <select className="input" value={linkExpire} onChange={(e) => setLinkExpire(Number(e.target.value))}>
          <option value={0}>Muddatsiz</option>
          <option value={24}>24 soat</option>
          <option value={168}>7 kun</option>
          <option value={720}>30 kun</option>
        </select>
        <input
          className="input"
          type="number"
          min={0}
          placeholder="Foydalanish soni (0 = cheksiz)"
          value={linkLimit}
          onChange={(e) => setLinkLimit(Number(e.target.value))}
        />
        <button
          className="btn primary"
          disabled={!dialogId || busy === "havola"}
          onClick={() =>
            needDialog() &&
            void run("Havola", () =>
              api
                .vipInviteLink(
                  accountId,
                  { dialog_id: dialogId, action: "create", expire_hours: linkExpire, usage_limit: linkLimit },
                  token,
                )
                .then((r) => {
                  setLink(r);
                  return r;
                }),
            )
          }
        >
          {busy === "havola" ? <IconSpinner size={16} /> : null}
          Yaratish
        </button>
        <button
          className="btn danger"
          disabled={!dialogId || busy === "bekor qilish"}
          onClick={() =>
            needDialog() &&
            void run("Bekor qilish", () =>
              api.vipInviteLink(accountId, { dialog_id: dialogId, action: "revoke" }, token).then((r) => {
                setLink(r);
                return r;
              }),
            )
          }
        >
          Eski havolani bekor qilish
        </button>
      </div>
      {link?.link && !link.revoked && (
        <div className="target-add">
          <input className="input" readOnly value={link.link} />
          <button
            className="btn ghost"
            onClick={() => {
              void navigator.clipboard?.writeText(link.link || "");
              setMsg("Havola nusxalandi");
            }}
          >
            Nusxalash
          </button>
        </div>
      )}
      {link?.expires && <div className="muted">Amal qilish muddati: {link.expires}</div>}

      <div className="pane-sub">5. Guruh sozlamalari</div>
      <div className="target-add">
        <input className="input" placeholder="Yangi nom" value={newTitle} onChange={(e) => setNewTitle(e.target.value)} />
        <button
          className="btn primary"
          disabled={!dialogId || !newTitle.trim() || busy === "nom"}
          onClick={() =>
            needDialog() &&
            void run("Nom", () =>
              api.vipGroupManage(accountId, { dialog_id: dialogId, user_id: 0, action: "set_title", title: newTitle }, token),
            )
          }
        >
          Nomni o'zgartirish
        </button>
        <input className="input" placeholder="Tavsif (about)" value={newAbout} onChange={(e) => setNewAbout(e.target.value)} />
        <button
          className="btn primary"
          disabled={!dialogId || !newAbout.trim() || busy === "tavsif"}
          onClick={() =>
            needDialog() &&
            void run("Tavsif", () =>
              api.vipGroupManage(accountId, { dialog_id: dialogId, user_id: 0, action: "set_about", title: newAbout }, token),
            )
          }
        >
          Tavsifni saqlash
        </button>
        <select className="input" value={slowmode} onChange={(e) => setSlowmode(Number(e.target.value))}>
          <option value={0}>Sekin rejim: o'chiq</option>
          <option value={10}>10 soniya</option>
          <option value={30}>30 soniya</option>
          <option value={60}>1 daqiqa</option>
          <option value={300}>5 daqiqa</option>
          <option value={3600}>1 soat</option>
        </select>
        <button
          className="btn primary"
          disabled={!dialogId || busy === "sekin rejim"}
          onClick={() =>
            needDialog() &&
            void run("Sekin rejim", () =>
              api.vipGroupManage(accountId, { dialog_id: dialogId, user_id: 0, action: "slowmode", title: String(slowmode) }, token),
            )
          }
        >
          Sekin rejimni sozlash
        </button>
      </div>

      <div className="pane-sub">6. A'zoni boshqarish</div>
      <div className="target-add">
        <input className="input" placeholder="Foydalanuvchi ID" value={userId} onChange={(e) => setUserId(e.target.value)} />
        <input
          className="input"
          type="number"
          min={1}
          placeholder="Soat"
          value={muteHours}
          onChange={(e) => setMuteHours(Number(e.target.value))}
        />
        <button
          className="btn primary"
          disabled={!dialogId || !userId.trim() || busy === "ovozni o'chirish"}
          onClick={() =>
            needDialog() &&
            void run("Ovozni o'chirish", () =>
              api.vipGroupManage(accountId, { dialog_id: dialogId, user_id: Number(userId), action: "mute", title: String(muteHours) }, token),
            )
          }
        >
          Ovozini o'chirish
        </button>
        <button
          className="btn ghost"
          disabled={!dialogId || !userId.trim() || busy === "ovozni ochish"}
          onClick={() =>
            needDialog() &&
            void run("Ovozni ochish", () =>
              api.vipGroupManage(accountId, { dialog_id: dialogId, user_id: Number(userId), action: "unmute" }, token),
            )
          }
        >
          Ovozini ochish
        </button>
        <div className="target-add">
          {RESTRICT_FLAGS.map((f) => (
            <label className="field" key={f.key}>
              <input
                type="checkbox"
                checked={restrict.includes(f.key)}
                onChange={(e) =>
                  setRestrict((prev) => (e.target.checked ? [...prev, f.key] : prev.filter((x) => x !== f.key)))
                }
              />
              <span className="field-label">{f.label}</span>
            </label>
          ))}
          <button
            className="btn primary"
            disabled={!dialogId || !userId.trim() || busy === "cheklash"}
            onClick={() =>
              needDialog() &&
              void run("Cheklash", () =>
                api.vipGroupManage(
                  accountId,
                  { dialog_id: dialogId, user_id: Number(userId), action: "restrict", title: restrict.join(",") },
                  token,
                ),
              )
            }
          >
            Cheklash
          </button>
          <button
            className="btn primary"
            disabled={!dialogId || !userId.trim() || busy === "admin qilish"}
            onClick={() =>
              needDialog() &&
              void run("Admin qilish", () =>
                api.vipGroupManage(accountId, { dialog_id: dialogId, user_id: Number(userId), action: "promote" }, token),
              )
            }
          >
            Admin qilish
          </button>
          <button
            className="btn ghost"
            disabled={!dialogId || !userId.trim() || busy === "adminlikdan olish"}
            onClick={() =>
              needDialog() &&
              void run("Adminlikdan olish", () =>
                api.vipGroupManage(accountId, { dialog_id: dialogId, user_id: Number(userId), action: "demote" }, token),
              )
            }
          >
            Adminlikdan olish
          </button>
        </div>
      </div>

      <div className="pane-sub">7. Xabarlarni tozalash</div>
      <div className="target-add">
        <input
          className="input"
          type="number"
          min={1}
          max={200}
          value={delCount}
          onChange={(e) => setDelCount(Number(e.target.value))}
        />
        <button className="btn danger" disabled={!dialogId || !userId.trim()} onClick={() => setConfirmDel(true)}>
          Shu foydalanuvchi xabarlarini o'chirish
        </button>
      </div>

      <div className="pane-sub">8. Ommaviy xabar</div>
      <div className="hint">Siz admin bo'lgan barcha guruh va kanallarga bir xil xabar yuboradi.</div>
      <div className="target-add">
        <textarea
          className="input"
          rows={3}
          placeholder="Xabar matni"
          value={bcText}
          onChange={(e) => setBcText(e.target.value)}
        />
        <select className="input" value={bcKind} onChange={(e) => setBcKind(e.target.value)}>
          <option value="">Barcha guruh va kanallar</option>
          <option value="group">Faqat guruhlar</option>
          <option value="channel">Faqat kanallar</option>
        </select>
        <button className="btn primary" disabled={!bcText.trim()} onClick={() => setConfirmBc(true)}>
          Ommaviy yuborish
        </button>
      </div>
      {bcResult && (
        <div className="analytics-grid">
          <div className="stat">
            <b>{bcResult.sent}</b>
            <span>yuborildi</span>
          </div>
          <div className="stat">
            <b>{bcResult.failed}</b>
            <span>xato</span>
          </div>
          <div className="stat">
            <b>{bcResult.total}</b>
            <span>jami chat</span>
          </div>
        </div>
      )}

      {msg && <div className="hint">{msg}</div>}
      {err && <div className="error">{err}</div>}

      <ConfirmDialog
        open={confirmBc}
        title="Ommaviy xabar yuborilsinmi?"
        text="Bu xabar siz admin bo'lgan barcha guruh va kanallarga yuboriladi. Amalni ortga qaytarib bo'lmaydi."
        confirmLabel="Yuborish"
        onCancel={() => setConfirmBc(false)}
        onConfirm={() => {
          setConfirmBc(false);
          void run("Ommaviy xabar", () =>
            api.vipBroadcast(accountId, { text: bcText, only_kind: bcKind }, token).then((r) => {
              setBcResult({ sent: r.sent, failed: r.failed, total: r.total });
              return r;
            }),
          );
        }}
      />
      <ConfirmDialog
        open={confirmDel}
        danger
        title="Xabarlar o'chirilsinmi?"
        text={`Foydalanuvchi ${userId} ning oxirgi ${delCount} ta xabari o'chiriladi. Amalni ortga qaytarib bo'lmaydi.`}
        confirmLabel="O'chirish"
        onCancel={() => setConfirmDel(false)}
        onConfirm={() => {
          setConfirmDel(false);
          void run("Xabarlarni o'chirish", () =>
            api.vipGroupManage(
              accountId,
              { dialog_id: dialogId, user_id: Number(userId), action: "delete_user_msgs", title: String(delCount) },
              token,
            ),
          );
        }}
      />
    </div>
  );
}
