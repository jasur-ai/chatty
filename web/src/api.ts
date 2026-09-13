import type {
  Account,
  AdminAccount,
  AdminUser,
  Analytics,
  BotSettings,
  Contact,
  DelegateDialog,
  DelegateMessage,
  Dialog,
  ForwardRule,
  LoginResult,
  Message,
  MusicPost,
  QuickReply,
  SearchResult,
  StarredMsg,
} from "./types";
import { API_BASE } from "./env";

const TOKEN_KEY = "chatty_tokens";

export function loadTokens(): Record<number, string> {
  try {
    return JSON.parse(localStorage.getItem(TOKEN_KEY) || "{}");
  } catch {
    return {};
  }
}

export function saveToken(accountId: number, token: string) {
  const all = loadTokens();
  all[accountId] = token;
  localStorage.setItem(TOKEN_KEY, JSON.stringify(all));
}

export function dropToken(accountId: number) {
  const all = loadTokens();
  delete all[accountId];
  localStorage.setItem(TOKEN_KEY, JSON.stringify(all));
}

async function req<T>(path: string, init: RequestInit = {}, token?: string, timeoutMs = 20000): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  // Timeout — server javob bermasa frontend osilib qolmasin.
  // Render bepul tarifi uyqudan 30-60s da uyg'onadi, shuning uchun auth so'rovlarida 90s.
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(API_BASE + path, { ...init, headers, signal: ctrl.signal });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = await res.json();
        detail = body.detail || detail;
      } catch {
        /* ignore */
      }
      throw new Error(detail);
    }
    return res.json() as Promise<T>;
  } catch (e) {
    if ((e as Error).name === "AbortError") throw new Error("Server javob bermadi (timeout)");
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

// Cold-start'ga chidamli so'rov: muvaffaqiyatsiz bo'lsa qayta urinadi
async function reqWithRetry<T>(path: string, init: RequestInit = {}, token?: string, timeoutMs = 90000): Promise<T> {
  let lastErr: Error | null = null;
  for (let i = 0; i < 3; i++) {
    try {
      return await req<T>(path, init, token, timeoutMs);
    } catch (e) {
      lastErr = e as Error;
      // faqat timeout/xato (server uyg'onayotgan) bo'lsa qayta urinamiz
      if ((e as Error).message?.includes("timeout")) {
        await new Promise((r) => setTimeout(r, 2500));
        continue;
      }
      throw e;
    }
  }
  throw lastErr;
}

export const api = {
  health: () => req<{ ok: boolean }>("/api/health"),

  startLogin: (phone: string) =>
    req<{ step: string }>("/api/auth/start", {
      method: "POST",
      body: JSON.stringify({ phone }),
    }),

  verifyCode: (phone: string, code: string) =>
    req<{ step: string } | LoginResult>("/api/auth/verify", {
      method: "POST",
      body: JSON.stringify({ phone, code }),
    }),

  submitPassword: (phone: string, password: string) =>
    req<LoginResult>("/api/auth/password", {
      method: "POST",
      body: JSON.stringify({ phone, password }),
    }),

  silentAuth: (initData: string | null, tgUserId: number | null) =>
    reqWithRetry<LoginResult>("/api/auth/silent", {
      method: "POST",
      body: JSON.stringify({ init_data: initData, tg_user_id: tgUserId }),
    }),

  accounts: () => reqWithRetry<{ accounts: Account[] }>("/api/auth/accounts"),

  logout: (accountId: number) =>
    req<{ ok: boolean }>("/api/auth/logout", { method: "POST", body: JSON.stringify({ account_id: accountId }) }),

  chats: (accountId: number, token: string) =>
    reqWithRetry<{ dialogs: Dialog[] }>(`/api/chats?account_id=${accountId}`, {}, token),

  messages: (accountId: number, dialogId: number, token: string, before?: number) =>
    req<{ messages: Message[]; has_more: boolean }>(
      `/api/chats/${dialogId}/messages?account_id=${accountId}${before ? `&before=${before}` : ""}`,
      {},
      token,
    ),

  read: (accountId: number, dialogId: number, token: string) =>
    req<{ ok: boolean }>(
      `/api/chats/${dialogId}/read?account_id=${accountId}`,
      { method: "POST" },
      token,
    ),

  send: (
    accountId: number,
    dialogId: number,
    text: string,
    token: string,
    opts?: { replyTo?: number; mediaKey?: string; mediaType?: string },
  ) =>
    req<Message>(
      "/api/messages",
      {
        method: "POST",
        body: JSON.stringify({
          account_id: accountId,
          dialog_id: dialogId,
          text,
          reply_to: opts?.replyTo ?? null,
          media_key: opts?.mediaKey ?? null,
          media_type: opts?.mediaType ?? null,
        }),
      },
      token,
    ),

  uploadMedia: (accountId: number, file: File, token: string) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("account_id", String(accountId));
    return req<{ media_key: string; media_type: string; size: number }>(
      "/api/media/upload",
      { method: "POST", body: fd },
      token,
    );
  },

  // ---- Bot-persona sozlamalari ----
  botSettings: (accountId: number, token: string) =>
    req<BotSettings>(`/api/bot/settings?account_id=${accountId}`, {}, token),

  updateBotSettings: (
    accountId: number,
    body: { bot_name?: string },
    token: string,
  ) => req<{ account: Account }>("/api/bot/settings", { method: "POST", body: JSON.stringify({ account_id: accountId, ...body }) }, token),

  setBotPhoto: (accountId: number, file: File, token: string) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("account_id", String(accountId));
    return req<{ account: Account; photo_url: string }>("/api/bot/photo", { method: "POST", body: fd }, token);
  },

  postStory: (accountId: number, file: File, caption: string, token: string) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("account_id", String(accountId));
    fd.append("caption", caption);
    return req<{ ok: boolean }>("/api/bot/story", { method: "POST", body: fd }, token);
  },

  setAutoReply: (
    accountId: number,
    body: { enabled?: boolean; text?: string; selected_text?: string; schedule_from?: string; schedule_to?: string },
    token: string,
  ) => req<{ ok: boolean }>("/api/bot/auto-reply", { method: "POST", body: JSON.stringify({ account_id: accountId, ...body }) }, token),

  addTarget: (accountId: number, tgUserId: number, name: string | null, token: string) =>
    req<{ ok: boolean }>("/api/bot/auto-reply/targets", { method: "POST", body: JSON.stringify({ account_id: accountId, tg_user_id: tgUserId, name }) }, token),

  removeTarget: (accountId: number, tgUserId: number, token: string) =>
    req<{ ok: boolean }>(`/api/bot/auto-reply/targets/${tgUserId}?account_id=${accountId}`, { method: "DELETE" }, token),

  // ---- Musiqa ----
  musicList: (accountId: number, token: string) =>
    req<{ music: MusicPost[] }>(`/api/bot/music?account_id=${accountId}`, {}, token),

  createMusic: (accountId: number, body: { title: string; performer?: string; caption?: string }, token: string) =>
    req<{ id: number }>("/api/bot/music", { method: "POST", body: JSON.stringify({ account_id: accountId, ...body }) }, token),

  reactMusic: (body: { music_post_id: number; reaction: string; user_tg_id: number; comment?: string }, token: string) =>
    req<{ ok: boolean }>("/api/bot/music/reaction", { method: "POST", body: JSON.stringify(body) }, token),

  // ---- Admin ----
  adminOverview: (token: string) =>
    req<{ accounts: AdminAccount[] }>("/api/admin/overview", {}, token),

  adminUsers: (token: string) =>
    req<{ users: AdminUser[] }>("/api/admin/users", {}, token),

  // ---- Delegat (vakil) ----
  delegateDialogs: (token: string) =>
    req<{ dialogs: DelegateDialog[] }>("/api/delegate/dialogs", {}, token),

  delegateMessages: (dialogId: number, token: string, before?: number) =>
    req<{ messages: DelegateMessage[]; has_more: boolean }>(
      `/api/delegate/dialogs/${dialogId}/messages${before ? `?before=${before}` : ""}`,
      {},
      token,
    ),

  delegateSend: (dialogId: number, body: { text: string; media_type?: string; file_id?: string }, token: string) =>
    req<{ message: DelegateMessage; dialog: DelegateDialog }>(
      `/api/delegate/dialogs/${dialogId}/send`,
      { method: "POST", body: JSON.stringify(body) },
      token,
    ),

  delegateRead: (dialogId: number, token: string) =>
    req<{ ok: boolean }>(`/api/delegate/dialogs/${dialogId}/read`, { method: "POST" }, token),

  setVip: (accountId: number, vip: boolean, token: string) =>
    req<{ ok: boolean }>("/api/admin/vip", { method: "POST", body: JSON.stringify({ account_id: accountId, vip }) }, token),

  listAdmins: (token: string) =>
    req<{ admins: { tg_user_id: number; role: string }[] }>("/api/admin/admins", {}, token),

  addAdmin: (tgUserId: number, token: string) =>
    req<{ ok: boolean }>("/api/admin/admins", { method: "POST", body: JSON.stringify({ tg_user_id: tgUserId }) }, token),

  removeAdmin: (tgUserId: number, token: string) =>
    req<{ ok: boolean }>(`/api/admin/admins/${tgUserId}`, { method: "DELETE" }, token),

  reportInterval: (token: string) =>
    req<{ hours: number; allowed: number[] }>("/api/admin/report-interval", {}, token),

  setReportInterval: (hours: number, token: string) =>
    req<{ ok: boolean }>("/api/admin/report-interval", { method: "POST", body: JSON.stringify({ hours }) }, token),

  adminReports: (token: string) =>
    req<{ reports: { id: number; body: string; created_at: string }[] }>("/api/admin/reports", {}, token),

  // ---- Lotus AI ----
  lotusChat: (text: string, token: string) =>
    req<{ reply: string; language: string }>("/api/lotus/chat", { method: "POST", body: JSON.stringify({ text }) }, token),

  lotusSettings: (token: string) =>
    req<{ name: string; language: string; voice_enabled: boolean; languages: string[] }>("/api/lotus/settings", {}, token),

  updateLotusSettings: (body: { language?: string; voice_enabled?: boolean }, token: string) =>
    req<{ language: string; voice_enabled: boolean }>("/api/lotus/settings", { method: "POST", body: JSON.stringify(body) }, token),

  lotusReminders: (token: string) =>
    req<{ reminders: { id: number; text: string; due_at: string; done: boolean }[] }>("/api/lotus/reminders", {}, token),

  lotusSummarize: (text: string, token: string) =>
    req<{ summary: string }>("/api/lotus/summarize", { method: "POST", body: JSON.stringify({ text }) }, token),

  lotusTranslate: (text: string, target: string, token: string) =>
    req<{ translated: string }>("/api/lotus/translate", { method: "POST", body: JSON.stringify({ text, target }) }, token),

  // ---- Pro funksiyalar (barcha foydalanuvchilar uchun) ----
  scheduleMessage: (
    accountId: number,
    body: { dialog_id: number; text: string; send_at: string },
    token: string,
  ) => req<{ ok: boolean; id: number }>("/api/bot/schedule", { method: "POST", body: JSON.stringify({ account_id: accountId, ...body }) }, token),

  scheduledList: (accountId: number, token: string) =>
    req<{ scheduled: { id: number; dialog_id: number; text: string; send_at: string; sent: boolean }[] }>(
      `/api/bot/schedule?account_id=${accountId}`,
      {},
      token,
    ),

  deleteScheduled: (id: number, token: string) =>
    req<{ ok: boolean }>(`/api/bot/schedule/${id}`, { method: "DELETE" }, token),

  forward: (accountId: number, body: { dialog_id: number; msg_tg_id: number; target_dialog_ids: number[] }, token: string) =>
    req<{ ok: boolean; forwarded_to: number[] }>("/api/bot/forward", { method: "POST", body: JSON.stringify({ account_id: accountId, ...body }) }, token),

  searchMessages: (accountId: number, q: string, token: string) =>
    req<{ results: SearchResult[] }>(`/api/bot/search?account_id=${accountId}&q=${encodeURIComponent(q)}`, {}, token),

  exportDialog: (accountId: number, dialogId: number, fmt: string, token: string) =>
    req<{ key: string; url: string; format: string; count: number }>(
      `/api/bot/export/${dialogId}?account_id=${accountId}&fmt=${fmt}`,
      {},
      token,
    ),

  analytics: (accountId: number, token: string) =>
    req<Analytics>(`/api/bot/analytics?account_id=${accountId}`, {}, token),

  backup: (accountId: number, token: string) =>
    req<{ key: string; url: string; dialogs: number }>(
      `/api/bot/backup?account_id=${accountId}`,
      { method: "POST" },
      token,
    ),

  autoDeleteGet: (accountId: number, token: string) =>
    req<{ ttl_seconds: number }>(`/api/bot/auto-delete?account_id=${accountId}`, {}, token),

  autoDeleteSet: (accountId: number, ttlSeconds: number, token: string) =>
    req<{ ok: boolean; ttl_seconds: number }>(
      "/api/bot/auto-delete",
      { method: "POST", body: JSON.stringify({ account_id: accountId, ttl_seconds: ttlSeconds }) },
      token,
    ),

  // ---- VIP funksiyalar ----
  vipEdit: (accountId: number, dialogId: number, msgTgId: number, text: string, token: string) =>
    req<{ ok: boolean }>("/api/vip/edit", { method: "POST", body: JSON.stringify({ account_id: accountId, dialog_id: dialogId, msg_tg_id: msgTgId, text }) }, token),

  vipDelete: (accountId: number, dialogId: number, msgTgId: number, token: string) =>
    req<{ ok: boolean }>("/api/vip/delete", { method: "POST", body: JSON.stringify({ account_id: accountId, dialog_id: dialogId, msg_tg_id: msgTgId }) }, token),

  vipPin: (accountId: number, dialogId: number, pinned: boolean, token: string) =>
    req<{ ok: boolean }>("/api/vip/pin", { method: "POST", body: JSON.stringify({ account_id: accountId, dialog_id: dialogId, pinned }) }, token),

  vipFlags: (accountId: number, dialogId: number, flags: { muted?: boolean; archived?: boolean }, token: string) =>
    req<{ ok: boolean }>("/api/vip/flags", { method: "POST", body: JSON.stringify({ account_id: accountId, dialog_id: dialogId, ...flags }) }, token),

  vipReact: (accountId: number, dialogId: number, msgTgId: number, reaction: string, token: string) =>
    req<{ ok: boolean }>("/api/vip/react", { method: "POST", body: JSON.stringify({ account_id: accountId, dialog_id: dialogId, msg_tg_id: msgTgId, reaction }) }, token),

  vipStar: (accountId: number, body: { dialog_id: number; tg_id: number; text: string; dialog_title: string }, token: string) =>
    req<{ ok: boolean; starred: boolean }>("/api/vip/star", { method: "POST", body: JSON.stringify({ account_id: accountId, ...body }) }, token),

  vipStarred: (accountId: number, token: string) =>
    req<{ starred: StarredMsg[] }>(`/api/vip/starred?account_id=${accountId}`, {}, token),

  vipStarRemove: (id: number, token: string) =>
    req<{ ok: boolean }>(`/api/vip/starred/${id}`, { method: "DELETE" }, token),

  vipQuickReplies: (accountId: number, token: string) =>
    req<{ quick_replies: QuickReply[] }>(`/api/vip/quick-replies?account_id=${accountId}`, {}, token),

  vipQuickReplyAdd: (accountId: number, label: string, text: string, token: string) =>
    req<{ ok: boolean; id: number }>("/api/vip/quick-replies", { method: "POST", body: JSON.stringify({ account_id: accountId, label, text }) }, token),

  vipQuickReplyRemove: (id: number, token: string) =>
    req<{ ok: boolean }>(`/api/vip/quick-replies/${id}`, { method: "DELETE" }, token),

  vipThemeGet: (accountId: number, token: string) =>
    req<{ accent: string; name: string }>(`/api/vip/theme?account_id=${accountId}`, {}, token),

  vipThemeSet: (accountId: number, accent: string, token: string) =>
    req<{ ok: boolean; accent: string }>("/api/vip/theme", { method: "POST", body: JSON.stringify({ account_id: accountId, accent }) }, token),

  vipMediaGallery: (accountId: number, dialogId: number, token: string) =>
    req<{ media: { tg_id: number; media_type: string; date: string; out: boolean }[] }>(
      `/api/vip/media-gallery/${dialogId}?account_id=${accountId}`,
      {},
      token,
    ),

  vipReadReceipts: (accountId: number, dialogId: number, token: string) =>
    req<{ sent: number; read: number; delivered_not_read: number; read_rate: number }>(
      `/api/vip/read-receipts/${dialogId}?account_id=${accountId}`,
      {},
      token,
    ),

  vipProfile: (accountId: number, body: { first_name?: string; bio?: string; username?: string }, token: string) =>
    req<{ ok: boolean }>("/api/vip/profile", { method: "POST", body: JSON.stringify({ account_id: accountId, ...body }) }, token),

  vipPoll: (accountId: number, dialogId: number, question: string, options: string[], token: string) =>
    req<{ ok: boolean }>("/api/vip/poll", { method: "POST", body: JSON.stringify({ account_id: accountId, dialog_id: dialogId, question, options }) }, token),

  vipSticker: (accountId: number, dialogId: number, emoji: string, token: string) =>
    req<{ ok: boolean }>("/api/vip/sticker", { method: "POST", body: JSON.stringify({ account_id: accountId, dialog_id: dialogId, emoji }) }, token),

  vipContacts: (accountId: number, token: string) =>
    req<{ contacts: Contact[] }>(`/api/vip/contacts?account_id=${accountId}`, {}, token),

  vipAutoForwardList: (accountId: number, token: string) =>
    req<{ rules: ForwardRule[] }>(`/api/vip/auto-forward?account_id=${accountId}`, {}, token),

  vipAutoForwardAdd: (accountId: number, body: { keyword: string; source_dialog_id: number; target_dialog_id: number }, token: string) =>
    req<{ ok: boolean; id: number }>("/api/vip/auto-forward", { method: "POST", body: JSON.stringify({ account_id: accountId, ...body }) }, token),

  vipAutoForwardRemove: (id: number, token: string) =>
    req<{ ok: boolean }>(`/api/vip/auto-forward/${id}`, { method: "DELETE" }, token),

  vipGroupManage: (accountId: number, body: { dialog_id: number; user_id: number; action: string; title?: string }, token: string) =>
    req<{ ok: boolean }>("/api/vip/group-manage", { method: "POST", body: JSON.stringify({ account_id: accountId, ...body }) }, token),

  vipMembers: (accountId: number, dialogId: number, token: string) =>
    req<{ members: Contact[] }>(`/api/vip/members/${dialogId}?account_id=${accountId}`, {}, token),

  vipChannelPost: (accountId: number, body: { dialog_id: number; text: string; send_at: string; silent: boolean }, token: string) =>
    req<{ ok: boolean }>("/api/vip/channel-post", { method: "POST", body: JSON.stringify({ account_id: accountId, ...body }) }, token),
};