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

export type DialogKind = "user" | "bot" | "group" | "channel";

export interface Dialog {
  id: number;
  tg_id: number;
  type: "user" | "chat" | "channel";
  /** Bo'lim: bot | user | group | channel */
  kind: DialogKind;
  title: string;
  username: string | null;
  unread_count: number;
  last_msg_id: number | null;
  last_msg_text: string | null;
  last_msg_date: string | null;
  last_out: boolean;
  pinned: boolean;
  muted: boolean;
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
  | { type: "read_outbox"; dialog_id: number; max_tg_id: number }
  | { type: "message_media"; dialog_id: number; tg_id: number; media_type: string; media_url: string }
  | { type: "delegate_message"; dialog: DelegateDialog; message: DelegateMessage };

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

export interface AdminUser {
  id: number;
  phone: string;
  first_name: string | null;
  username: string | null;
  bot_name: string | null;
  auth_step: string;
  is_active: boolean;
  created_at: string | null;
  tg_user_id: number | null;
  is_owner: boolean;
  is_admin: boolean;
  is_vip: boolean;
  theme: string;
  dialogs_count: number;
  messages_count: number;
}

export interface DelegateDialog {
  id: number;
  bot_chat_id: number;
  first_name: string | null;
  username: string | null;
  last_msg_text: string | null;
  last_msg_date: string | null;
  last_out: boolean;
  unread_count: number;
  pinned: boolean;
}

export interface DelegateMessage {
  id: number;
  dialog_id: number;
  direction: "in" | "out";
  text: string;
  media_type: string;
  media_url?: string | null;
  date: string | null;
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

export interface QuickReply {
  id: number;
  label: string;
  text: string;
}

export interface StarredMsg {
  id: number;
  dialog_id: number;
  tg_id: number;
  text: string;
  dialog_title: string;
  created_at: string;
}

export interface ForwardRule {
  id: number;
  keyword: string;
  source_dialog_id: number;
  target_dialog_id: number;
  enabled: boolean;
}

export interface Contact {
  id: number;
  first_name: string | null;
  last_name: string | null;
  username: string | null;
  phone: string | null;
}

// ---- Tadbirlar / Events ----
export interface EventFolder {
  id: number;
  title: string;
  peers: number;
}

export interface EventItem {
  id?: number;
  name: string;
  purpose: string;
  when: string;
  place: string;
  /** Server tahlil qilgan tadbir sanasi (ISO). O'tganlar jadvalga kirmaydi. */
  event_at?: string | null;
  source_title?: string;
  source_kind?: string;
  msg_tg_id?: number;
  msg_date?: string | null;
  by_ai?: boolean;
}

export interface EventsScanResult {
  events: EventItem[];
  scanned: number;
  folder_title: string;
  days: number;
}

export interface EventsConfig {
  folder_id: number;
  folder_title: string;
  days: number;
  extra_keywords: string;
  last_scan_at: string | null;
}
// ---- Guruh / kanal boshqaruvi (admin) ----
export interface GroupAdmin {
  id: number;
  first_name: string;
  last_name: string;
  username: string | null;
  is_creator: boolean;
  bot: boolean;
  rank: string | null;
  can_edit: boolean;
  promoted_by: number | null;
  rights: Record<string, boolean>;
}

export interface GroupAdmins {
  admins: GroupAdmin[];
  creator: { id: number; first_name: string; username: string | null } | null;
  count: number;
  kind: string;
  peer_type: string;
  title: string;
  total_members: number | null;
}

export interface TagAllResult {
  ok: boolean;
  preview?: boolean;
  total_members: number;
  with_username: number;
  messages?: number;
  messages_sent?: number;
  chunks?: string[];
}

export interface InviteLinkResult {
  ok: boolean;
  revoked: boolean;
  link: string | null;
  expires?: string | null;
  usage_limit?: number | null;
  requested?: boolean;
}

export interface BroadcastResult {
  ok: boolean;
  sent: number;
  failed: number;
  total: number;
  details?: { title: string; ok: boolean; error?: string }[];
}
