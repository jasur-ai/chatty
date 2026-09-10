export interface Account {
  id: number;
  phone: string;
  first_name: string | null;
  username: string | null;
  bot_name: string | null;
  bot_photo: string | null;
  auth_step: string;
  is_active: boolean;
  app_user?: AppUserInfo;
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

export interface BotSettings {
  account: Account;
  auto_reply: {
    enabled: boolean;
    text: string | null;
    selected_text: string | null;
    schedule_from: string | null;
    schedule_to: string | null;
    targets: { tg_user_id: number; name: string | null }[];
  };
  suggested_replies: string[];
}

export interface MusicPost {
  id: number;
  title: string;
  performer: string | null;
  caption: string;
  media_url: string | null;
  created_at: string | null;
  reactions: { user_tg_id: number; reaction: string; comment: string | null }[];
}

export interface AdminAccount {
  id: number;
  phone: string;
  first_name: string | null;
  bot_name: string | null;
  is_active: boolean;
  auth_step: string;
  app_user: { is_owner: boolean; is_admin: boolean; is_vip: boolean; theme: string };
  dialogs_count: number;
  messages_count: number;
}

export interface SearchResult {
  tg_id: number;
  dialog_id: number;
  dialog_title: string;
  text: string;
  date: string;
  out: boolean;
}

export interface Analytics {
  total_messages: number;
  out_messages: number;
  in_messages: number;
  dialogs: number;
  by_hour: Record<string, number>;
  by_day: Record<string, number>;
}