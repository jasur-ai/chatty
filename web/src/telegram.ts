/** Telegram Mini App integratsiyasi.
 *
 * Mini app Telegram ichida ochilganda WebApp SDK orqali:
 *  - ready() + expand() (to'liq ekran)
 *  - colorScheme asosida dark/light rejim
 *  - Telegram foydalanuvchisi ma'lumotlari (initDataUnsafe.user)
 */

export interface TgUser {
  id: number;
  firstName?: string;
  lastName?: string;
  username?: string;
}

interface TgWebAppLike {
  ready?: () => void;
  expand?: () => void;
  isExpanded?: boolean;
  colorScheme?: "light" | "dark";
  initData?: string;
  initDataUnsafe?: {
    user?: {
      id: number;
      first_name?: string;
      last_name?: string;
      username?: string;
    };
  };
  setHeaderColor?: (c: string) => void;
  setBackgroundColor?: (c: string) => void;
  version?: string;
}

declare global {
  interface Window {
    Telegram?: { WebApp?: TgWebAppLike };
  }
}

export function getWebApp(): TgWebAppLike | null {
  return typeof window !== "undefined" ? window.Telegram?.WebApp ?? null : null;
}

export function isTelegramMiniApp(): boolean {
  return getWebApp() !== null;
}

export function getTgUser(): TgUser | null {
  const u = getWebApp()?.initDataUnsafe?.user;
  if (!u) return null;
  return {
    id: u.id,
    firstName: u.first_name,
    lastName: u.last_name,
    username: u.username,
  };
}

/** Telegram colorScheme bo'yicha dark/light rejimni qo'llash (pink rejimni buzmaydi). */
export function applyTelegramColorScheme() {
  const wa = getWebApp();
  if (!wa?.colorScheme) return;
  const root = document.documentElement;
  // Pink rejim bo'lmasa, Telegram scheme bo'yicha dark qo'llash
  if (root.getAttribute("data-theme") !== "pink") {
    root.setAttribute("data-color-scheme", wa.colorScheme);
  }
}

/** Mini app ishga tushirilganda chaqiriladi — to'liq ekran + theme. */
export function initTelegram() {
  const wa = getWebApp();
  if (!wa) return;
  try {
    wa.ready?.();
    applyTelegramColorScheme();
  } catch {
    /* ignore */
  }
  // expand() ba'zan SDK hali tayyor bo'lmaganda ishlamaydi — retry qilamiz
  let tries = 0;
  const doExpand = () => {
    tries++;
    try {
      wa.expand?.();
      // Mini app to'liq ekranga chiqishi uchun viewport'ni sozlaymiz
      document.documentElement.style.height = "100%";
      document.body.style.height = "100%";
    } catch {
      /* ignore */
    }
    if (tries < 5 && !wa.isExpanded) {
      setTimeout(doExpand, 300);
    }
  };
  doExpand();
  // Telegram rang sxemasi o'zgarsa ham qo'llash
  if (wa.colorScheme) {
    document.documentElement.setAttribute("data-color-scheme", wa.colorScheme);
  }
}
