/** Backend manzili sozlamasi.
 *
 * Bo'sh (default) = frontend bilan bir xil origin (FastAPI web/dist xizmat qilganda).
 * Frontend Cloudflare Pages'da, backend boshqa joyda bo'lsa — build paytida
 * VITE_API_BASE / VITE_WS_BASE env'lari bilan backend URL beriladi.
 */
export const API_BASE: string = (import.meta.env.VITE_API_BASE as string) || "";
export const WS_BASE: string = (import.meta.env.VITE_WS_BASE as string) || "";

export function wsUrl(token: string): string {
  const tokenParam = encodeURIComponent(token);
  if (WS_BASE) {
    const sep = WS_BASE.includes("?") ? "&" : "?";
    return `${WS_BASE}${sep}token=${tokenParam}`;
  }
  const proto = location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${location.host}/ws?token=${tokenParam}`;
}
