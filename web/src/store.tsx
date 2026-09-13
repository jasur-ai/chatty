import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { api, dropToken, loadTokens, saveToken } from "./api";
import type { Account, AppUserInfo, DelegateDialog, DelegateMessage, Dialog, Message, WsEvent } from "./types";
import { getTgUser, getWebApp } from "./telegram";
import { ChattySocket } from "./ws";

interface Store {
  accounts: Account[];
  current: Account | null;
  appUser: AppUserInfo | null;
  dialogs: Dialog[];
  activeDialog: Dialog | null;
  messages: Message[];
  loadingChats: boolean;
  loadingMessages: boolean;
  chatsError: string;
  token: string | null;
  settingsOpen: boolean;
  lotusOpen: boolean;
  view: "chats" | "delegate" | "admin";
  delegateDialogs: DelegateDialog[];
  activeDelegateDialog: DelegateDialog | null;
  delegateMessages: DelegateMessage[];
  delegateLoading: boolean;
  delegateMessagesLoading: boolean;
  setView: (v: "chats" | "delegate" | "admin") => void;
  openAdmin: () => void;
  closeAdmin: () => void;
  loadDelegateDialogs: () => Promise<void>;
  openDelegateDialog: (d: DelegateDialog) => Promise<void>;
  delegateBack: () => void;
  delegateSend: (text: string) => Promise<void>;
  openSettings: () => void;
  closeSettings: () => void;
  openLotus: () => void;
  closeLotus: () => void;
  logout: () => Promise<void>;
  selectAccount: (id: number) => void;
  openDialog: (d: Dialog) => void;
  backToList: () => void;
  replyTo: Message | null;
  setReplyTo: (m: Message | null) => void;
  sendText: (text: string, replyTo?: Message | null) => Promise<void>;
  loadMore: () => Promise<void>;
  addAccount: (account: Account, token: string, appUser: AppUserInfo) => void;
  refreshAccounts: () => Promise<void>;
  silentLogin: () => Promise<boolean>;
}

const Ctx = createContext<Store | null>(null);

export function useStore(): Store {
  const s = useContext(Ctx);
  if (!s) throw new Error("Store yo'q");
  return s;
}

export function StoreProvider({ children }: { children: ReactNode }) {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [current, setCurrent] = useState<Account | null>(null);
  const [appUser, setAppUser] = useState<AppUserInfo | null>(null);
  const [dialogs, setDialogs] = useState<Dialog[]>([]);
  const [activeDialog, setActiveDialog] = useState<Dialog | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [replyTo, setReplyToState] = useState<Message | null>(null);
  const [loadingChats, setLoadingChats] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [chatsError, setChatsError] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [lotusOpen, setLotusOpen] = useState(false);
  const [view, setView] = useState<"chats" | "delegate" | "admin">("chats");
  const [delegateDialogs, setDelegateDialogs] = useState<DelegateDialog[]>([]);
  const [activeDelegateDialog, setActiveDelegateDialog] = useState<DelegateDialog | null>(null);
  const [delegateMessages, setDelegateMessages] = useState<DelegateMessage[]>([]);
  const [delegateLoading, setDelegateLoading] = useState(false);
  const [delegateMessagesLoading, setDelegateMessagesLoading] = useState(false);
  const hasMoreRef = useRef(false);
  const activeRef = useRef<Dialog | null>(null);
  const activeDelegateRef = useRef<DelegateDialog | null>(null);
  const socketRef = useRef<ChattySocket | null>(null);

  useEffect(() => {
    activeRef.current = activeDialog;
  }, [activeDialog]);

  const token = current ? (loadTokens()[current.id] ?? null) : null;

  // ---- WebSocket: joriy akkauntga ulanish ----
  useEffect(() => {
    if (!current || !token) return;
    if (!socketRef.current) socketRef.current = new ChattySocket(handleWsEvent);
    socketRef.current.connect(token);
    return () => socketRef.current?.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current?.id, token]);

  function handleWsEvent(ev: WsEvent) {
    if (ev.type === "message") {
      setDialogs((prev) => {
        const rest = prev.filter((d) => d.id !== ev.dialog.id);
        return [ev.dialog, ...rest];
      });
      const active = activeRef.current;
      if (active && active.id === ev.dialog.id) {
        setMessages((prev) =>
          prev.some((m) => m.tg_id === ev.message.tg_id) ? prev : [...prev, ev.message],
        );
      }
    } else if (ev.type === "read_outbox") {
      setMessages((prev) =>
        prev.map((m) =>
          m.out && m.dialog_id === ev.dialog_id && m.tg_id <= ev.max_tg_id ? { ...m, read: true } : m,
        ),
      );
    } else if (ev.type === "message_media") {
      setMessages((prev) =>
        prev.map((m) =>
          m.dialog_id === ev.dialog_id && m.tg_id === ev.tg_id
            ? { ...m, media_type: ev.media_type, media_url: ev.media_url }
            : m,
        ),
      );
    } else if (ev.type === "delegate_message") {
      setDelegateDialogs((prev) => {
        const rest = prev.filter((d) => d.id !== ev.dialog.id);
        return [ev.dialog, ...rest];
      });
      const active = activeDelegateRef.current;
      if (active && active.id === ev.dialog.id) {
        setDelegateMessages((prev) =>
          prev.some((m) => m.id === ev.message.id) ? prev : [...prev, ev.message],
        );
      }
    }
  }

  // ---- Chatlarni yuklash (current o'zgarganda avtomatik) ----
  const loadChats = useCallback(async (accId: number) => {
    const t = loadTokens()[accId];
    if (!t) return;
    setLoadingChats(true);
    setChatsError("");
    try {
      const res = await api.chats(accId, t);
      setDialogs(res.dialogs);
    } catch (e) {
      setChatsError((e as Error).message || "Chatlarni yuklab bo'lmadi");
    } finally {
      setLoadingChats(false);
    }
  }, []);

  // current akkaunt o'zgarganda chatlarni avtomatik yuklash
  // (login, refresh yoki switcher orqali tanlash — barchasi shu effect orqali)
  useEffect(() => {
    if (current) void loadChats(current.id);
  }, [current?.id, loadChats]);

  // ---- Akkaunt tanlash ----
  const selectAccount = useCallback(
    async (id: number) => {
      const acc = accounts.find((a) => a.id === id) ?? null;
      setCurrent(acc);
      setAppUser(acc?.app_user ?? null);
      setDialogs([]);
      setActiveDialog(null);
      setMessages([]);
      if (acc) void loadChats(acc.id);
    },
    [accounts, loadChats],
  );

  const refreshAccounts = useCallback(async () => {
    try {
      const res = await api.accounts();
      setAccounts(res.accounts);
      const ready = res.accounts.filter((a) => a.auth_step === "ready");
      setCurrent((prev) => {
        if (prev && res.accounts.some((a) => a.id === prev.id)) return prev;
        const withToken = ready.find((a) => loadTokens()[a.id]);
        return withToken ?? ready[0] ?? null;
      });
      // appUser'ni tanlangan akkauntga moslab yangilash (admin/delegate tugmalari uchun)
      setAppUser((prev) => {
        if (prev) return prev;
        const withToken = ready.find((a) => loadTokens()[a.id]);
        const acc = withToken ?? ready[0];
        return acc?.app_user ?? null;
      });
    } catch {
      /* ignore */
    }
  }, []);

  // ---- Chat ochish ----
  const openDialog = useCallback(
    async (d: Dialog) => {
      if (!current || !token) return;
      setActiveDialog(d);
      setLoadingMessages(true);
      try {
        const res = await api.messages(current.id, d.id, token);
        setMessages(res.messages);
        hasMoreRef.current = res.has_more;
        void api.read(current.id, d.id, token).then(() => {
          setMessages((prev) => prev.map((m) => (m.out ? m : { ...m, read: true })));
          setDialogs((prev) => prev.map((x) => (x.id === d.id ? { ...x, unread_count: 0 } : x)));
        });
      } catch {
        setMessages([]);
      } finally {
        setLoadingMessages(false);
      }
    },
    [current, token],
  );

  const backToList = useCallback(() => {
    setActiveDialog(null);
    setMessages([]);
    setReplyToState(null);
  }, []);

  const setReplyTo = useCallback((m: Message | null) => setReplyToState(m), []);

  const sendText = useCallback(
    async (text: string, replyToMsg?: Message | null) => {
      if (!current || !token || !activeDialog) return;
      const rep = replyToMsg ?? replyTo;
      const optimistic: Message = {
        id: -Date.now(),
        tg_id: -Date.now(),
        dialog_id: activeDialog.id,
        out: true,
        text,
        media_type: "none",
        media_url: null,
        media_size: null,
        date: new Date().toISOString(),
        reply_to: rep ? rep.tg_id : null,
        read: false,
        hidden: false,
      };
      setMessages((prev) => [...prev, optimistic]);
      setReplyToState(null);
      try {
        const sent = await api.send(current.id, activeDialog.id, text, token, {
          replyTo: rep ? rep.tg_id : undefined,
        });
        setMessages((prev) => prev.map((m) => (m.id === optimistic.id ? sent : m)));
        setDialogs((prev) =>
          prev.map((d) =>
            d.id === activeDialog.id
              ? { ...d, last_msg_text: text, last_msg_date: sent.date, last_out: true }
              : d,
          ),
        );
      } catch (e) {
        setMessages((prev) => prev.filter((m) => m.id !== optimistic.id));
        console.error(e);
      }
    },
    [current, token, activeDialog, replyTo],
  );

  const loadMore = useCallback(async () => {
    if (!current || !token || !activeDialog || !hasMoreRef.current || loadingMessages) return;
    const oldest = messages[0];
    if (!oldest) return;
    setLoadingMessages(true);
    try {
      const res = await api.messages(current.id, activeDialog.id, token, oldest.tg_id);
      setMessages((prev) => [...res.messages, ...prev]);
      hasMoreRef.current = res.has_more;
    } catch {
      /* ignore */
    } finally {
      setLoadingMessages(false);
    }
  }, [current, token, activeDialog, messages, loadingMessages]);

  const addAccount = useCallback(
    (account: Account, tk: string, info: AppUserInfo) => {
      saveToken(account.id, tk);
      setAccounts((prev) => {
        const rest = prev.filter((a) => a.id !== account.id);
        return [...rest, account];
      });
      setAppUser(info);
      setCurrent(account);
      setDialogs([]);
      setActiveDialog(null);
      setMessages([]);
    },
    [],
  );

  // Boshlang'ich yuklash
  useEffect(() => {
    void refreshAccounts();
  }, [refreshAccounts]);

  const openSettings = useCallback(() => setSettingsOpen(true), []);
  const closeSettings = useCallback(() => setSettingsOpen(false), []);
  const openLotus = useCallback(() => setLotusOpen(true), []);
  const closeLotus = useCallback(() => setLotusOpen(false), []);

  // ---- Delegat (vakil) + Admin ----
  useEffect(() => {
    activeDelegateRef.current = activeDelegateDialog;
  }, [activeDelegateDialog]);

  const isAdminLike = appUser?.is_admin || appUser?.is_owner;

  const loadDelegateDialogs = useCallback(async () => {
    const t = current ? loadTokens()[current.id] : null;
    if (!t) return;
    setDelegateLoading(true);
    try {
      const res = await api.delegateDialogs(t);
      setDelegateDialogs(res.dialogs);
    } catch {
      /* ignore */
    } finally {
      setDelegateLoading(false);
    }
  }, [current]);

  // Admin/owner bo'lsa va delegat ko'rinishiga o'tganda yuklash
  useEffect(() => {
    if (view === "delegate" && isAdminLike) void loadDelegateDialogs();
  }, [view, isAdminLike, loadDelegateDialogs]);

  const openDelegateDialog = useCallback(
    async (d: DelegateDialog) => {
      const t = current ? loadTokens()[current.id] : null;
      if (!t) return;
      setActiveDelegateDialog(d);
      setDelegateMessagesLoading(true);
      try {
        const res = await api.delegateMessages(d.id, t);
        setDelegateMessages(res.messages);
        void api.delegateRead(d.id, t).then(() => {
          setDelegateDialogs((prev) => prev.map((x) => (x.id === d.id ? { ...x, unread_count: 0 } : x)));
        });
      } catch {
        setDelegateMessages([]);
      } finally {
        setDelegateMessagesLoading(false);
      }
    },
    [current],
  );

  const delegateBack = useCallback(() => {
    setActiveDelegateDialog(null);
    setDelegateMessages([]);
  }, []);

  const delegateSend = useCallback(
    async (text: string) => {
      const t = current ? loadTokens()[current.id] : null;
      if (!t || !activeDelegateDialog) return;
      const dlg = activeDelegateDialog;
      const optimistic: DelegateMessage = {
        id: -Date.now(),
        dialog_id: dlg.id,
        direction: "out",
        text,
        media_type: "none",
        media_url: null,
        date: new Date().toISOString(),
      };
      setDelegateMessages((prev) => [...prev, optimistic]);
      try {
        const res = await api.delegateSend(dlg.id, { text }, t);
        setDelegateMessages((prev) => prev.map((m) => (m.id === optimistic.id ? res.message : m)));
        setDelegateDialogs((prev) => prev.map((d) => (d.id === dlg.id ? res.dialog : d)));
      } catch (e) {
        setDelegateMessages((prev) => prev.filter((m) => m.id !== optimistic.id));
        console.error(e);
      }
    },
    [current, activeDelegateDialog],
  );

  const openAdmin = useCallback(() => setView("admin"), []);
  const closeAdmin = useCallback(() => setView("chats"), []);

  const silentLogin = useCallback(async (): Promise<boolean> => {
    // Telegram Mini App ichida — initData orqali avtomatik kirish (telefon/kod/2FA shart emas).
    const initData = getWebApp()?.initData ?? null;
    const tgUser = getTgUser();
    if (!initData && !tgUser) return false;
    try {
      const res = await api.silentAuth(initData, tgUser?.id ?? null);
      addAccount(res.account, res.token, res.app_user);
      return true;
    } catch {
      return false;
    }
  }, [addAccount]);

  const logout = useCallback(async () => {
    if (!current || !token) return;
    try {
      await api.logout(current.id);
    } catch {
      /* sessiya allaqachon yopilgan bo'lishi mumkin */
    }
    dropToken(current.id);
    socketRef.current?.disconnect();
    socketRef.current = null;
    setDialogs([]);
    setActiveDialog(null);
    setMessages([]);
    setCurrent(null);
    setAppUser(null);
    void refreshAccounts();
  }, [current, token, refreshAccounts]);

  const store = useMemo<Store>(
    () => ({
      accounts,
      current,
      appUser,
      dialogs,
      activeDialog,
      messages,
      loadingChats,
      loadingMessages,
      chatsError,
      replyTo,
      setReplyTo,
      token,
      settingsOpen,
      lotusOpen,
      view,
      delegateDialogs,
      activeDelegateDialog,
      delegateMessages,
      delegateLoading,
      delegateMessagesLoading,
      setView,
      openAdmin,
      closeAdmin,
      loadDelegateDialogs,
      openDelegateDialog,
      delegateBack,
      delegateSend,
      openSettings,
      closeSettings,
      openLotus,
      closeLotus,
      logout,
      silentLogin,
      selectAccount,
      openDialog,
      backToList,
      sendText,
      loadMore,
      addAccount,
      refreshAccounts,
    }),
    [
      accounts,
      current,
      appUser,
      dialogs,
      activeDialog,
      messages,
      loadingChats,
      loadingMessages,
      chatsError,
      replyTo,
      setReplyTo,
      token,
      settingsOpen,
      lotusOpen,
      view,
      delegateDialogs,
      activeDelegateDialog,
      delegateMessages,
      delegateLoading,
      delegateMessagesLoading,
      setView,
      openAdmin,
      closeAdmin,
      loadDelegateDialogs,
      openDelegateDialog,
      delegateBack,
      delegateSend,
      openSettings,
      closeSettings,
      openLotus,
      closeLotus,
      logout,
      silentLogin,
      selectAccount,
      openDialog,
      backToList,
      sendText,
      loadMore,
      addAccount,
      refreshAccounts,
    ],
  );

  return <Ctx.Provider value={store}>{children}</Ctx.Provider>;
}