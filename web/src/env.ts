/** Backend manzili sozlamasi.
 *
 * VITE_API_BASE / VITE_WS_BASE build paytida berilmasa, prod backend URL ishlatiladi.
 * (Frontend Cloudflare Pages'da, backend Render'da bo'lgani uchun aniq URL ko'rsatiladi —
 *  aks holda API chaqiruvlar frontend origin'iga borib 404 bo'lardi.)
 */
const DEFAULT_API_BASE = "https://chatty-3eje.onrender.com";
const DEFAULT_WS_BASE = "wss://chatty-3eje.onrender.com/ws";

export const API_BASE: string =
  (import.meta.env.VITE_API_BASE as string) || DEFAULT_API_BASE;
export const WS_BASE: string =
  (import.meta.env.VITE_WS_BASE as string) || DEFAULT_WS_BASE;

export function wsUrl(token: string): string {
  const tokenParam = encodeURIComponent(token);
  const sep = WS_BASE.includes("?") ? "&" : "?";
  return `${WS_BASE}${sep}token=${tokenParam}`;
}
