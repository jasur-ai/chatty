import type { Account, Dialog, LoginResult, Message } from "./types";

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

async function req<T>(path: string, init: RequestInit = {}, token?: string): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(path, { ...init, headers });
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

  accounts: () => req<{ accounts: Account[] }>("/api/auth/accounts"),

  chats: (accountId: number, token: string) =>
    req<{ dialogs: Dialog[] }>(`/api/chats?account_id=${accountId}`, {}, token),

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
};