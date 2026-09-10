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
  requestFullscreen?: () => void;
  isFullscreen?: boolean;
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
  onEvent?: (eventType: string, handler: () => void) => void;
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
  // Telegram sarlavhasini ham app foniga moslab, kengaytirilgan ko'rinish beramiz
  try {
    wa.setHeaderColor?.("#000000");
    wa.setBackgroundColor?.("#000000");
  } catch {
    /* ignore */
  }

  // To'liq ekran: avval requestFullscreen (haqiqiy fullscreen), bo'lmasa expand()
  let tries = 0;
  const doFullscreen = () => {
    tries++;
    try {
      if (typeof wa.requestFullscreen === "function") {
        wa.requestFullscreen();
      } else {
        wa.expand?.();
      }
    } catch {
      try {
        wa.expand?.();
      } catch {
        /* ignore */
      }
    }
    // viewport'ni to'liq balandlikka sozlaymiz
    document.documentElement.style.height = "100%";
    document.body.style.height = "100%";
    document.documentElement.style.setProperty("--tg-viewport-height", `${window.innerHeight}px`);

    const full = typeof wa.isFullscreen === "boolean" ? wa.isFullscreen : wa.isExpanded;
    if (tries < 8 && !full) {
      setTimeout(doFullscreen, 250);
    }
  };
  doFullscreen();

  // viewport o'lchami o'zgarganda qayta sozlash
  window.addEventListener("resize", () => {
    document.documentElement.style.setProperty("--tg-viewport-height", `${window.innerHeight}px`);
  });

  // Telegram rang sxemasi o'zgarsa ham qo'llash
  if (wa.colorScheme) {
    document.documentElement.setAttribute("data-color-scheme", wa.colorScheme);
  }
}
