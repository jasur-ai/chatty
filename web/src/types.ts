export interface Account {
  id: number;
  phone: string;
  first_name: string | null;
  username: string | null;
  bot_name: string | null;
  bot_photo: string | null;
  auth_step: string;
  is_active: boolean;
}

export interface AppUserInfo {
  is_owner: boolean;
  is_admin: boolean;
  is_vip: boolean;
  theme: string;
}

export interface Dialog {
  id: number;
  tg_id: number;
  type: "user" | "chat" | "channel";
  title: string;
  username: string | null;
  unread_count: number;
  last_msg_id: number | null;
  last_msg_text: string | null;
  last_msg_date: string | null;
  last_out: boolean;
  photo: string | null;
}

export interface Message {
  id: number;
  tg_id: number;
  dialog_id: number;
  out: boolean;
  text: string;
  media_type: string;
  media_url: string | null;
  media_size: number | null;
  date: string | null;
  reply_to: number | null;
  read: boolean;
  hidden: boolean;
}

export type WsEvent =
  | { type: "message"; dialog: Dialog; message: Message }
  | { type: "read_outbox"; dialog_id: number; max_tg_id: number };

export interface LoginResult {
  token: string;
  account: Account;
  app_user: AppUserInfo;
}