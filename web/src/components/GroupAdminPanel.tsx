import { useMemo, useState } from "react";
import { api } from "../api";
import type { Contact, Dialog, GroupAdmins, InviteLinkResult, TagAllResult } from "../types";
import { IconCheck, IconMegaphone, IconPlus, IconShieldCheck, IconSpinner, IconTrash, IconUsers, IconX } from "../icons";
import { ConfirmDialog } from "./ConfirmDialog";

type Props = {
  accountId: number;
  token: string;
  dialogs: Dialog[];
};

/** Telegram huquq bayroqlarining o'zbekcha nomlari. */
const RIGHT_LABELS: Record<string, string> = {
  change_info: "Ma'lumotni o'zgartirish",
  post_messages: "Xabar yozish",
  edit_messages: "Xabarni tahrirlash",
  delete_messages: "Xabarni o'chirish",
  ban_users: "A'zolarni bloklash",
  invite_users: "A'zo taklif qilish",
  pin_messages: "Xabarni qadash",
  add_admins: "Admin qo'shish",
  anonymous: "Anonim qolish",
  manage_call: "Qo'ng'iroqlarni boshqarish",
  manage_topics: "Mavzularni boshqarish",
};

const RESTRICT_FLAGS = [
  { key: "media", label: "Media yuborish" },
  { key: "stickers", label: "Stiker yuborish" },
  { key: "preview", label: "Havola ko'rinishi" },
];

function memberLabel(m: { id: number; first_name?: string | null; last_name?: string | null; username?: string | null }) {
  const name = [m.first_name, m.last_name].filter(Boolean).join(" ").trim();
  return name || (m.username ? `@${m.username}` : `ID ${m.id}`);
}

/**
 * Guruh / kanal boshqaruvi paneli.
 *
 * Akkaunt guruhda admin bo'lganda ishlaydi. Qulaylik uchun a'zo amallari
 * ID yozish orqali emas, ro'yxatdan tanlash orqali bajariladi.
 */
export function GroupAdminPanel({ accountId, token, dialogs }: Props) {
  const groups = useMemo(() => dialogs.filter((d) => d.type !== "user"), [dialogs]);

  const [dialogId, setDialogId] = useState(0);
  const [busy, setBusy] = useState("");
  const [ok, setOk] = useState("");
  const [err, setErr] = useState("");

  // Adminlar
  const [admins, setAdmins] = useState<GroupAdmins | null>(null);

  // A'zolar (tanlash uchun)
  const [members, setMembers] = useState<Contact[]>([]);
  const [memberQuery, setMemberQuery] = useState("");
  const [picked, setPicked] = useState<Contact | null>(null);

  // Barchani teg qilish
  const [tagText, setTagText] = useState("");
  const [tagPreview, setTagPreview] = useState<TagAllResult | null>(null);
  const [confirmTag, setConfirmTag] = useState(false);

  // So'rovnoma
  const [pollQ, setPollQ] = useState("");
  const [pollOpts, setPollOpts] = useState<string[]>(["", ""]);
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

  // A'zo cheklovlari
  const [muteHours, setMuteHours] = useState(24);
  const [restrict, setRestrict] = useState<string[]>(["media"]);
  const [confirmKick, setConfirmKick] = useState(false);

  // Ommaviy xabar
  const [bcText, setBcText] = useState("");
  const [bcKind, setBcKind] = useState("");
  const [bcResult, setBcResult] = useState<{ sent: number; failed: number; total: number } | null>(null);
  const [confirmBc, setConfirmBc] = useState(false);

  // Xabarlarni o'chirish
  const [delCount, setDelCount] = useState(20);
  const [confirmDel, setConfirmDel] = useState(false);

  async function run<T>(label: string, fn: () => Promise<T>, done?: string | ((r: T) => string)): Promise<T | null> {
    setBusy(label);
    setOk("");
    setErr("");
    try {
      const r = await fn();
      setOk(typeof done === "function" ? done(r) : done || `${label} bajarildi`);
      return r;
    } catch (e) {
      setErr(`${label}: ${(e as Error).message}`);
      return null;
    } finally {
      setBusy("");
    }
  }

  function resetDialog(id: number) {
    setDialogId(id);
    setAdmins(null);
    setLink(null);
    setTagPreview(null);
    setMembers([]);
    setPicked(null);
    setMemberQuery("");
    setOk("");
    setErr("");
  }

  const pollOptions = pollOpts.map((o) => o.trim()).filter(Boolean);
  const shownMembers = useMemo(() => {
    const q = memberQuery.trim().toLowerCase();
    if (!q) return members.slice(0, 100);
    return members
      .filter((m) => memberLabel(m).toLowerCase().includes(q) || String(m.username || "").toLowerCase().includes(q))
      .slice(0, 100);
  }, [members, memberQuery]);

  const memberActionsDisabled = !dialogId || !picked;

  return (
    <div className="ga">
      <div className="pane-head">
        <div className="pane-title">Guruh va kanal boshqaruvi</div>
      </div>
      <div className="hint">
        Bu bo'lim akkaunt guruh yoki kanalda admin bo'lganda ishlaydi. Barcha amallar sizning
        Telegram akkauntingiz nomidan bajariladi.
      </div>

      {ok && (
        <div className="ga-status ok">
          <IconCheck size={16} />
          {ok}
        </div>
      )}
      {err && (
        <div className="ga-status err">
          <IconX size={16} />
          {err}
        </div>
      )}

      {/* 1. Guruh tanlash va admin holati */}
      <div className="ga-card">
        <div className="ga-head">
          <div className="ga-num">1</div>
          <div className="ga-heading">
            <div className="ga-title">Guruh yoki kanal</div>
            <div className="ga-desc">Boshqariladigan chatni tanlang va admin huquqingizni tekshiring.</div>
          </div>
        </div>
        <div className="ga-body">
          <div className="ga-row">
            <select className="input" value={dialogId} onChange={(e) => resetDialog(Number(e.target.value))}>
              <option value={0}>Tanlang</option>
              {groups.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.title}
                </option>
              ))}
            </select>
            <button
              className="btn primary"
              disabled={!dialogId || busy === "Tekshirilmoqda"}
              onClick={() =>
                void run(
                  "Tekshirilmoqda",
                  () => api.vipAdmins(accountId, dialogId, token).then((r) => { setAdmins(r); return r; }),
                  (r) => `Siz bu chatda admin. ${r.count} ta admin, ${r.total_members ?? "?"} ta a'zo.`,
                )
              }
            >
              {busy === "Tekshirilmoqda" ? <IconSpinner size={16} /> : <IconShieldCheck size={16} />}
              Admin huquqini tekshirish
            </button>
          </div>

          {admins && (
            <>
              <div className="ga-row">
                <div className="ga-pick">
                  <IconUsers size={14} />
                  {admins.total_members ?? "?"} a'zo · {admins.count} admin ·{" "}
                  {admins.kind === "channel" ? "kanal" : "guruh"}
                </div>
                {admins.creator && (
                  <div className="ga-pick">
                    <IconShieldCheck size={14} />
                    Egasi: @{admins.creator.username || admins.creator.first_name || admins.creator.id}
                  </div>
                )}
              </div>
              {admins.admins.length > 0 && (
                <div className="ga-list">
                  {admins.admins.map((a) => (
                    <div className="ga-item" key={a.id} role="presentation">
                      <div className="ga-item-main">
                        <div>@{a.username || a.first_name || a.id}</div>
                        <div className="ga-item-sub">
                          {a.is_creator ? "Guruh egasi" : "Admin"}
                          {a.rank ? ` · ${a.rank}` : ""}
                          {a.bot ? " · bot" : ""}
                        </div>
                        <div className="ga-rights">
                          {Object.entries(a.rights)
                            .filter(([, v]) => v)
                            .map(([k]) => (
                              <span className="ga-right on" key={k}>
                                {RIGHT_LABELS[k] || k}
                              </span>
                            ))}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* 2. A'zoni tanlash */}
      <div className="ga-card">
        <div className="ga-head">
          <div className="ga-num">2</div>
          <div className="ga-heading">
            <div className="ga-title">A'zoni tanlash</div>
            <div className="ga-desc">
             Quyidagi amallar uchun a'zoni ro'yxatdan tanlang — ID yozish shart emas.
            </div>
          </div>
        </div>
        <div className="ga-body">
          <div className="ga-row">
            <button
              className="btn primary"
              disabled={!dialogId || busy === "A'zolar yuklanmoqda"}
              onClick={() =>
                void run(
                  "A'zolar yuklanmoqda",
                  () => api.vipMembers(accountId, dialogId, token).then((r) => { setMembers(r.members); return r; }),
                  (r) => `${r.members.length} ta a'zo yuklandi — ro'yxatdan tanlang`,
                )
              }
            >
              {busy === "A'zolar yuklanmoqda" ? <IconSpinner size={16} /> : <IconUsers size={16} />}
              A'zolarni yuklash
            </button>
            {members.length > 0 && (
              <input
                className="input"
                placeholder="Ism yoki @username bo'yicha qidirish"
                value={memberQuery}
                onChange={(e) => setMemberQuery(e.target.value)}
              />
            )}
          </div>

          {picked && (
            <div className="ga-row">
              <div className="ga-pick">
                <IconCheck size={14} />
                {memberLabel(picked)}
                {picked.username ? ` · @${picked.username}` : ""}
                <button
                  type="button"
                  aria-label="Tanlovni bekor qilish"
                  onClick={() => setPicked(null)}
                >
                  <IconX size={14} />
                </button>
              </div>
            </div>
          )}

          {members.length > 0 && (
            <div className="ga-list">
              {shownMembers.map((m) => (
                <button
                  type="button"
                  key={m.id}
                  className={picked?.id === m.id ? "ga-item active" : "ga-item"}
                  onClick={() => setPicked(m)}
                >
                  <div className="ga-item-main">
                    <div>{memberLabel(m)}</div>
                    <div className="ga-item-sub">{m.username ? `@${m.username}` : `ID ${m.id}`}</div>
                  </div>
                  {picked?.id === m.id && <IconCheck size={16} />}
                </button>
              ))}
              {shownMembers.length === 0 && (
                <div className="ga-item" role="presentation">
                  <div className="ga-item-main">
                    <div className="ga-item-sub">Hech kim topilmadi</div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 3. Barchani teg qilish */}
      <div className="ga-card">
        <div className="ga-head">
          <div className="ga-num">3</div>
          <div className="ga-heading">
            <div className="ga-title">Barchani teg qilish</div>
            <div className="ga-desc">
              Barcha a'zolarning @username'larini xabarga qo'shadi. Uzun ro'yxat 50 tadan bo'laklanadi.
            </div>
          </div>
        </div>
        <div className="ga-body">
          <div className="ga-row">
            <input
              className="input"
              placeholder="Xabar matni (ixtiyoriy)"
              value={tagText}
              onChange={(e) => setTagText(e.target.value)}
            />
            <button
              className="btn ghost"
              disabled={!dialogId || busy === "Ko'rib chiqilmoqda"}
              onClick={() =>
                void run(
                  "Ko'rib chiqilmoqda",
                  () =>
                    api
                      .vipTagAll(accountId, { dialog_id: dialogId, text: tagText, preview: true }, token)
                      .then((r) => { setTagPreview(r); return r; }),
                  "Hech narsa yuborilmadi — natijani ko'rib chiqing",
                )
              }
            >
              {busy === "Ko'rib chiqilmoqda" ? <IconSpinner size={16} /> : <IconUsers size={16} />}
              Ko'rib chiqish
            </button>
            <button className="btn primary" disabled={!dialogId || !tagPreview} onClick={() => setConfirmTag(true)}>
              <IconMegaphone size={16} />
              Yuborish
            </button>
          </div>
          {tagPreview && (
            <div className="hint">
              {tagPreview.total_members} a'zodan {tagPreview.with_username} tasida @username bor.
              {tagPreview.preview ? ` Rejada ${tagPreview.messages} ta xabar.` : ""}
              {tagPreview.messages_sent ? ` ${tagPreview.messages_sent} ta xabar yuborildi.` : ""}
            </div>
          )}
          {tagPreview?.chunks && tagPreview.chunks.length > 0 && (
            <div className="ga-link">{tagPreview.chunks[0]}</div>
          )}
        </div>
      </div>

      {/* 4. So'rovnoma */}
      <div className="ga-card">
        <div className="ga-head">
          <div className="ga-num">4</div>
          <div className="ga-heading">
            <div className="ga-title">So'rovnoma</div>
            <div className="ga-desc">Haqiqiy Telegram so'rovnomasi — 2 tadan 10 tagacha javob varianti.</div>
          </div>
        </div>
        <div className="ga-body">
          <input
            className="input"
            placeholder="Savol"
            value={pollQ}
            onChange={(e) => setPollQ(e.target.value)}
          />
          {pollOpts.map((o, i) => (
            <div className="ga-opt" key={i}>
              <span className="ga-opt-idx">{i + 1}</span>
              <input
                className="input"
                placeholder={`${i + 1}-variant`}
                value={o}
                onChange={(e) => setPollOpts((prev) => prev.map((x, j) => (j === i ? e.target.value : x)))}
              />
              <button
                type="button"
                className="btn ghost"
                aria-label="Variantni o'chirish"
                disabled={pollOpts.length <= 2}
                onClick={() => setPollOpts((prev) => prev.filter((_, j) => j !== i))}
              >
                <IconTrash size={14} />
              </button>
            </div>
          ))}
          <div className="ga-row">
            <button
              className="btn ghost"
              disabled={pollOpts.length >= 10}
              onClick={() => setPollOpts((prev) => [...prev, ""])}
            >
              <IconPlus size={14} />
              Variant qo'shish
            </button>
          </div>
          <div className="ga-grid">
            <label className="check-row">
              <input type="checkbox" checked={pollAnon} onChange={(e) => setPollAnon(e.target.checked)} />
              Anonim ovoz
            </label>
            <label className="check-row">
              <input type="checkbox" checked={pollMulti} onChange={(e) => setPollMulti(e.target.checked)} />
              Bir nechta javob
            </label>
            <label className="check-row">
              <input type="checkbox" checked={pollQuiz} onChange={(e) => setPollQuiz(e.target.checked)} />
              Viktorina
            </label>
          </div>
          <div className="ga-grid">
            {pollQuiz && (
              <label className="field">
                <span className="field-label">To'g'ri javob</span>
                <select
                  className="input"
                  value={pollCorrect}
                  onChange={(e) => setPollCorrect(Number(e.target.value))}
                >
                  {pollOpts.map((o, i) => (
                    <option key={i} value={i}>
                      {i + 1}. {o.trim() || "bo'sh"}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <label className="field">
              <span className="field-label">Yopilish muddati</span>
              <select className="input" value={pollClose} onChange={(e) => setPollClose(Number(e.target.value))}>
                <option value={0}>Muddatsiz</option>
                <option value={60}>1 daqiqada</option>
                <option value={300}>5 daqiqada</option>
                <option value={600}>10 daqiqada</option>
              </select>
            </label>
          </div>
          <div className="ga-row">
            <button
              className="btn primary"
              disabled={!dialogId || !pollQ.trim() || pollOptions.length < 2 || busy === "So'rovnoma yuborilmoqda"}
              onClick={() =>
                void run(
                  "So'rovnoma yuborilmoqda",
                  () =>
                    api.vipPoll(accountId, dialogId, pollQ, pollOptions, token, {
                      anonymous: pollAnon,
                      multiple_choice: pollMulti,
                      quiz: pollQuiz,
                      correct_option: pollCorrect,
                      close_period: pollClose,
                    }),
                  "So'rovnoma guruhga yuborildi",
                )
              }
            >
              {busy === "So'rovnoma yuborilmoqda" ? <IconSpinner size={16} /> : null}
              So'rovnoma yuborish
            </button>
          </div>
        </div>
      </div>

      {/* 5. Taklif havolasi */}
      <div className="ga-card">
        <div className="ga-head">
          <div className="ga-num">5</div>
          <div className="ga-heading">
            <div className="ga-title">Taklif havolasi</div>
            <div className="ga-desc">Muddatli va cheklangan havola yarating yoki eskisini bekor qiling.</div>
          </div>
        </div>
        <div className="ga-body">
          <div className="ga-grid">
            <label className="field">
              <span className="field-label">Amal qilish muddati</span>
              <select className="input" value={linkExpire} onChange={(e) => setLinkExpire(Number(e.target.value))}>
                <option value={0}>Muddatsiz</option>
                <option value={24}>24 soat</option>
                <option value={168}>7 kun</option>
                <option value={720}>30 kun</option>
              </select>
            </label>
            <label className="field">
              <span className="field-label">Foydalanish soni</span>
              <input
                className="input"
                type="number"
                min={0}
                placeholder="0 = cheksiz"
                value={linkLimit}
                onChange={(e) => setLinkLimit(Number(e.target.value))}
              />
            </label>
          </div>
          <div className="ga-row">
            <button
              className="btn primary"
              disabled={!dialogId || busy === "Havola yaratilmoqda"}
              onClick={() =>
                void run(
                  "Havola yaratilmoqda",
                  () =>
                    api
                      .vipInviteLink(
                        accountId,
                        { dialog_id: dialogId, action: "create", expire_hours: linkExpire, usage_limit: linkLimit },
                        token,
                      )
                      .then((r) => { setLink(r); return r; }),
                  "Havola yaratildi",
                )
              }
            >
              {busy === "Havola yaratilmoqda" ? <IconSpinner size={16} /> : null}
              Havola yaratish
            </button>
            <button
              className="btn danger"
              disabled={!dialogId || busy === "Bekor qilinmoqda"}
              onClick={() =>
                void run(
                  "Bekor qilinmoqda",
                  () =>
                    api
                      .vipInviteLink(accountId, { dialog_id: dialogId, action: "revoke" }, token)
                      .then((r) => { setLink(r); return r; }),
                  "Eski havolalar bekor qilindi",
                )
              }
            >
              Eskisini bekor qilish
            </button>
          </div>
          {link?.link && !link.revoked && (
            <>
              <div className="ga-link">{link.link}</div>
              <div className="ga-row">
                <button
                  className="btn ghost"
                  onClick={() => {
                    void navigator.clipboard?.writeText(link.link || "");
                    setOk("Havola nusxalandi");
                    setErr("");
                  }}
                >
                  Nusxalash
                </button>
                {link.expires && <span className="ga-item-sub">Muddati: {link.expires}</span>}
                {link.usage_limit ? <span className="ga-item-sub">Limit: {link.usage_limit}</span> : null}
              </div>
            </>
          )}
        </div>
      </div>

      {/* 6. Guruh sozlamalari */}
      <div className="ga-card">
        <div className="ga-head">
          <div className="ga-num">6</div>
          <div className="ga-heading">
            <div className="ga-title">Guruh sozlamalari</div>
            <div className="ga-desc">Nom, tavsif va sekin rejim (slow mode).</div>
          </div>
        </div>
        <div className="ga-body">
          <div className="ga-row">
            <input
              className="input"
              placeholder="Yangi nom"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
            />
            <button
              className="btn primary"
              disabled={!dialogId || !newTitle.trim() || busy === "Nom saqlanmoqda"}
              onClick={() =>
                void run(
                  "Nom saqlanmoqda",
                  () =>
                    api.vipGroupManage(
                      accountId,
                      { dialog_id: dialogId, user_id: 0, action: "set_title", title: newTitle },
                      token,
                    ),
                  "Guruh nomi o'zgartirildi",
                )
              }
            >
              Nomni o'zgartirish
            </button>
          </div>
          <div className="ga-row">
            <input
              className="input"
              placeholder="Tavsif (about)"
              value={newAbout}
              onChange={(e) => setNewAbout(e.target.value)}
            />
            <button
              className="btn primary"
              disabled={!dialogId || !newAbout.trim() || busy === "Tavsif saqlanmoqda"}
              onClick={() =>
                void run(
                  "Tavsif saqlanmoqda",
                  () =>
                    api.vipGroupManage(
                      accountId,
                      { dialog_id: dialogId, user_id: 0, action: "set_about", title: newAbout },
                      token,
                    ),
                  "Tavsif saqlandi",
                )
              }
            >
              Tavsifni saqlash
            </button>
          </div>
          <div className="ga-row">
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
              disabled={!dialogId || busy === "Sekin rejim saqlanmoqda"}
              onClick={() =>
                void run(
                  "Sekin rejim saqlanmoqda",
                  () =>
                    api.vipGroupManage(
                      accountId,
                      { dialog_id: dialogId, user_id: 0, action: "slowmode", title: String(slowmode) },
                      token,
                    ),
                  slowmode ? `Sekin rejim ${slowmode} soniyaga o'rnatildi` : "Sekin rejim o'chirildi",
                )
              }
            >
              Sekin rejimni sozlash
            </button>
          </div>
        </div>
      </div>

      {/* 7. A'zoni boshqarish */}
      <div className="ga-card">
        <div className="ga-head">
          <div className="ga-num">7</div>
          <div className="ga-heading">
            <div className="ga-title">A'zoni boshqarish</div>
            <div className="ga-desc">
              {picked ? `Tanlangan: ${memberLabel(picked)}` : "Avval 2-bo'limda a'zoni tanlang."}
            </div>
          </div>
        </div>
        <div className="ga-body">
          <div className="ga-row">
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
              disabled={memberActionsDisabled || busy === "Ovoz o'chirilmoqda"}
              onClick={() =>
                void run(
                  "Ovoz o'chirilmoqda",
                  () =>
                    api.vipGroupManage(
                      accountId,
                      {
                        dialog_id: dialogId,
                        user_id: picked!.id,
                        action: "mute",
                        title: String(muteHours),
                      },
                      token,
                    ),
                  `${memberLabel(picked!)} ovozi ${muteHours} soatga o'chirildi`,
                )
              }
            >
              Ovozini o'chirish
            </button>
            <button
              className="btn ghost"
              disabled={memberActionsDisabled || busy === "Ovoz ochilmoqda"}
              onClick={() =>
                void run(
                  "Ovoz ochilmoqda",
                  () =>
                    api.vipGroupManage(
                      accountId,
                      { dialog_id: dialogId, user_id: picked!.id, action: "unmute" },
                      token,
                    ),
                  `${memberLabel(picked!)} ovozi ochildi`,
                )
              }
            >
              Ovozini ochish
            </button>
          </div>

          <div className="ga-grid">
            {RESTRICT_FLAGS.map((f) => (
              <label className="check-row" key={f.key}>
                <input
                  type="checkbox"
                  checked={restrict.includes(f.key)}
                  onChange={(e) =>
                    setRestrict((prev) => (e.target.checked ? [...prev, f.key] : prev.filter((x) => x !== f.key)))
                  }
                />
                {f.label}
              </label>
            ))}
          </div>
          <div className="ga-row">
            <button
              className="btn primary"
              disabled={memberActionsDisabled || restrict.length === 0 || busy === "Cheklanmoqda"}
              onClick={() =>
                void run(
                  "Cheklanmoqda",
                  () =>
                    api.vipGroupManage(
                      accountId,
                      {
                        dialog_id: dialogId,
                        user_id: picked!.id,
                        action: "restrict",
                        title: restrict.join(","),
                      },
                      token,
                    ),
                  `${memberLabel(picked!)} cheklandi`,
                )
              }
            >
              Cheklash
            </button>
            <button
              className="btn primary"
              disabled={memberActionsDisabled || busy === "Admin qilinmoqda"}
              onClick={() =>
                void run(
                  "Admin qilinmoqda",
                  () =>
                    api.vipGroupManage(
                      accountId,
                      { dialog_id: dialogId, user_id: picked!.id, action: "promote" },
                      token,
                    ),
                  `${memberLabel(picked!)} admin qilindi`,
                )
              }
            >
              Admin qilish
            </button>
            <button
              className="btn ghost"
              disabled={memberActionsDisabled || busy === "Adminlikdan olinmoqda"}
              onClick={() =>
                void run(
                  "Adminlikdan olinmoqda",
                  () =>
                    api.vipGroupManage(
                      accountId,
                      { dialog_id: dialogId, user_id: picked!.id, action: "demote" },
                      token,
                    ),
                  `${memberLabel(picked!)} adminlikdan olindi`,
                )
              }
            >
              Adminlikdan olish
            </button>
            <button className="btn danger" disabled={memberActionsDisabled} onClick={() => setConfirmKick(true)}>
              Guruhdan chiqarish
            </button>
          </div>

          <div className="ga-row">
            <input
              className="input"
              type="number"
              min={1}
              max={200}
              value={delCount}
              onChange={(e) => setDelCount(Number(e.target.value))}
            />
            <button className="btn danger" disabled={memberActionsDisabled} onClick={() => setConfirmDel(true)}>
              Xabarlarini o'chirish
            </button>
          </div>
        </div>
      </div>

      {/* 8. Ommaviy xabar */}
      <div className="ga-card">
        <div className="ga-head">
          <div className="ga-num">8</div>
          <div className="ga-heading">
            <div className="ga-title">Ommaviy xabar</div>
            <div className="ga-desc">Siz admin bo'lgan barcha guruh va kanallarga bir xil xabar.</div>
          </div>
        </div>
        <div className="ga-body">
          <textarea
            className="input"
            rows={3}
            placeholder="Xabar matni"
            value={bcText}
            onChange={(e) => setBcText(e.target.value)}
          />
          <div className="ga-row">
            <select className="input" value={bcKind} onChange={(e) => setBcKind(e.target.value)}>
              <option value="">Barcha guruh va kanallar</option>
              <option value="group">Faqat guruhlar</option>
              <option value="channel">Faqat kanallar</option>
            </select>
            <button className="btn primary" disabled={!bcText.trim()} onClick={() => setConfirmBc(true)}>
              <IconMegaphone size={16} />
              Ommaviy yuborish
            </button>
          </div>
          {bcResult && (
            <div className="ga-row">
              <div className="ga-pick">
                <IconCheck size={14} />
                {bcResult.sent} yuborildi · {bcResult.failed} xato · {bcResult.total} chat
              </div>
            </div>
          )}
        </div>
      </div>

      <ConfirmDialog
        open={confirmTag}
        title="Barchaga teg yuborilsinmi?"
        text={`Guruhdagi ${tagPreview?.with_username ?? 0} ta a'zoga @username bilan xabar yuboriladi. Amalni ortga qaytarib bo'lmaydi.`}
        confirmLabel="Yuborish"
        onCancel={() => setConfirmTag(false)}
        onConfirm={() => {
          setConfirmTag(false);
          void run(
            "Teg yuborilmoqda",
            () =>
              api
                .vipTagAll(accountId, { dialog_id: dialogId, text: tagText, preview: false }, token)
                .then((r) => { setTagPreview(r); return r; }),
            `${tagPreview?.with_username ?? 0} ta a'zoga teg yuborildi`,
          );
        }}
      />

      <ConfirmDialog
        open={confirmBc}
        title="Ommaviy xabar yuborilsinmi?"
        text="Bu xabar siz admin bo'lgan barcha guruh va kanallarga yuboriladi. Amalni ortga qaytarib bo'lmaydi."
        confirmLabel="Yuborish"
        onCancel={() => setConfirmBc(false)}
        onConfirm={() => {
          setConfirmBc(false);
          void run(
            "Ommaviy xabar yuborilmoqda",
            () =>
              api.vipBroadcast(accountId, { text: bcText, only_kind: bcKind }, token).then((r) => {
                setBcResult({ sent: r.sent, failed: r.failed, total: r.total });
                return r;
              }),
            "Ommaviy xabar yuborildi",
          );
        }}
      />

      <ConfirmDialog
        open={confirmDel}
        danger
        title="Xabarlar o'chirilsinmi?"
        text={`${picked ? memberLabel(picked) : "Foydalanuvchi"} ning oxirgi ${delCount} ta xabari o'chiriladi. Amalni ortga qaytarib bo'lmaydi.`}
        confirmLabel="O'chirish"
        onCancel={() => setConfirmDel(false)}
        onConfirm={() => {
          setConfirmDel(false);
          void run(
            "Xabarlar o'chirilmoqda",
            () =>
              api.vipGroupManage(
                accountId,
                {
                  dialog_id: dialogId,
                  user_id: picked!.id,
                  action: "delete_user_msgs",
                  title: String(delCount),
                },
                token,
              ),
            "Xabarlar o'chirildi",
          );
        }}
      />

      <ConfirmDialog
        open={confirmKick}
        danger
        title="Guruhdan chiqarilsinmi?"
        text={picked ? `${memberLabel(picked)} guruhdan chiqariladi.` : "Foydalanuvchi guruhdan chiqariladi."}
        confirmLabel="Chiqarish"
        onCancel={() => setConfirmKick(false)}
        onConfirm={() => {
          setConfirmKick(false);
          void run(
            "Chiqarilmoqda",
            () =>
              api.vipGroupManage(
                accountId,
                { dialog_id: dialogId, user_id: picked!.id, action: "kick" },
                token,
              ),
            `${picked ? memberLabel(picked) : "Foydalanuvchi"} guruhdan chiqarildi`,
          );
        }}
      />
    </div>
  );
}

