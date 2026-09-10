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
import { api, loadTokens, saveToken } from "./api";
import type { Account, AppUserInfo, Dialog, Message, WsEvent } from "./types";
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
  token: string | null;
  selectAccount: (id: number) => void;
  openDialog: (d: Dialog) => void;
  backToList: () => void;
  sendText: (text: string) => Promise<void>;
  loadMore: () => Promise<void>;
  addAccount: (account: Account, token: string, appUser: AppUserInfo) => void;
  refreshAccounts: () => Promise<void>;
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
  const [loadingChats, setLoadingChats] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const hasMoreRef = useRef(false);
  const activeRef = useRef<Dialog | null>(null);
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
    }
  }

  // ---- Akkaunt tanlash ----
  const selectAccount = useCallback(
    async (id: number) => {
      const acc = accounts.find((a) => a.id === id) ?? null;
      setCurrent(acc);
      setDialogs([]);
      setActiveDialog(null);
      setMessages([]);
      if (!acc) return;
      const t = loadTokens()[acc.id];
      if (!t) return;
      setLoadingChats(true);
      try {
        const res = await api.chats(acc.id, t);
        setDialogs(res.dialogs);
      } catch {
        /* ignore */
      } finally {
        setLoadingChats(false);
      }
    },
    [accounts],
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
  }, []);

  const sendText = useCallback(
    async (text: string) => {
      if (!current || !token || !activeDialog) return;
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
        reply_to: null,
        read: false,
        hidden: false,
      };
      setMessages((prev) => [...prev, optimistic]);
      try {
        const sent = await api.send(current.id, activeDialog.id, text, token);
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
    [current, token, activeDialog],
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
      token,
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
      token,
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