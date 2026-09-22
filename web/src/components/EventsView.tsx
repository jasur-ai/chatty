import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { IconBack, IconCalendar, IconSearch, IconSpinner } from "../icons";
import { useStore } from "../store";
import type { EventFolder, EventItem } from "../types";

const DAY_OPTIONS = [
  { v: 1, label: "1 kun" },
  { v: 3, label: "3 kun" },
  { v: 7, label: "1 hafta" },
  { v: 14, label: "2 hafta" },
];

function fmtDate(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleDateString([], { day: "2-digit", month: "short" });
}

/** ISO sanadan qisqa, o'qishli ko'rinish yasaydi: "23-sen, 10:00". */
function fmtEventDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  const months = ["yan","fev","mar","apr","may","iyn","iyl","avg","sen","okt","noy","dek"];
  const day = d.getDate();
  const mo = months[d.getMonth()];
  const hh = d.getHours().toString().padStart(2, "0");
  const mm = d.getMinutes().toString().padStart(2, "0");
  const hasTime = hh !== "00" || mm !== "00";
  return hasTime ? `${day}-${mo}, ${hh}:${mm}` : `${day}-${mo}`;
}

export function EventsView() {
  const { current, token, setView } = useStore();
  const [folders, setFolders] = useState<EventFolder[]>([]);
  const [folderId, setFolderId] = useState<number>(0);
  const [days, setDays] = useState<number>(7);
  const [keywords, setKeywords] = useState("");
  const [events, setEvents] = useState<EventItem[]>([]);
  const [meta, setMeta] = useState<{ scanned: number; folder_title: string; last_scan_at: string | null } | null>(
    null,
  );
  const [loading, setLoading] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState("");

  // Boshlang'ich yuklash: papkalar + saqlangan config + oxirgi natija
  const loadAll = useCallback(async () => {
    if (!current || !token) return;
    setLoading(true);
    setError("");
    try {
      const [fr, cfg, list] = await Promise.all([
        api.eventsFolders(current.id, token),
        api.eventsConfigGet(current.id, token),
        api.eventsList(current.id, token),
      ]);
      setFolders(fr.folders);
      const c = cfg.config;
      if (c) {
        setFolderId(c.folder_id);
        setDays(c.days || 7);
        setKeywords(c.extra_keywords || "");
      } else if (fr.folders.length > 0) {
        setFolderId(fr.folders[0].id);
      }
      setEvents(list.events);
      setMeta({
        scanned: list.events.length,
        folder_title: list.config.folder_title || "",
        last_scan_at: list.config.last_scan_at,
      });
    } catch (e) {
      setError((e as Error).message || "Yuklab bo'lmadi");
    } finally {
      setLoading(false);
    }
  }, [current, token]);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  const runScan = useCallback(async () => {
    if (!current || !token || !folderId) return;
    setScanning(true);
    setError("");
    try {
      const res = await api.eventsScan(current.id, { folder_id: folderId, days, extra_keywords: keywords }, token);
      setEvents(res.events);
      setMeta({ scanned: res.scanned, folder_title: res.folder_title, last_scan_at: new Date().toISOString() });
    } catch (e) {
      setError((e as Error).message || "Skanerlab bo'lmadi");
    } finally {
      setScanning(false);
    }
  }, [current, token, folderId, days, keywords]);

  const selFolder = folders.find((f) => f.id === folderId);

  return (
    <div className="events-page">
      <header className="events-header">
        <button className="icon-btn" title="Chatlarga qaytish" onClick={() => setView("chats")}>
          <IconBack size={22} />
        </button>
        <span className="events-title">
          <IconCalendar size={20} />
          Tadbirlar
        </span>
        <span className="tg-close-spacer" />
      </header>

      <div className="events-body">
        {/* Sozlamalar */}
        <section className="events-config">
          <div className="config-row">
            <label className="config-label">Papka</label>
            <select
              className="input config-select"
              value={folderId}
              disabled={loading || folders.length === 0}
              onChange={(e) => setFolderId(Number(e.target.value))}
            >
              {folders.length === 0 && <option value={0}>Papka topilmadi</option>}
              {folders.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.title} · {f.peers} kanal/guruh
                </option>
              ))}
            </select>
          </div>

          <div className="config-grid">
            <div className="config-row">
              <label className="config-label">Davr</label>
              <div className="day-chips">
                {DAY_OPTIONS.map((o) => (
                  <button
                    key={o.v}
                    className={`day-chip ${days === o.v ? "active" : ""}`}
                    onClick={() => setDays(o.v)}
                  >
                    {o.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="config-row">
              <label className="config-label">Qo'shimcha kalit so'zlar</label>
              <input
                className="input"
                placeholder="masalan: webinar, trening (vergul bilan)"
                value={keywords}
                onChange={(e) => setKeywords(e.target.value)}
              />
            </div>
          </div>

          <button
            className="btn primary events-scan"
            onClick={() => void runScan()}
            disabled={scanning || !folderId || folders.length === 0}
          >
            {scanning ? <IconSpinner size={18} /> : <IconSearch size={18} />}
            {scanning ? "Tekshirilmoqda…" : "Skanerlash"}
          </button>

          {selFolder && (
            <p className="config-hint">
              «{selFolder.title}» papkasidagi {selFolder.peers} ta kanal/guruh so'nggi{" "}
              {DAY_OPTIONS.find((o) => o.v === days)?.label ?? "1 hafta"} davomida kalit so'zlar bo'yicha
              tekshiriladi.
            </p>
          )}
        </section>

        {/* Xatolik */}
        {error && <div className="events-error">{error}</div>}

        {/* Yuklanmoqda */}
        {loading && (
          <div className="events-status">
            <IconSpinner size={22} />
            <span>Yuklanmoqda…</span>
          </div>
        )}

        {/* Natija */}
        {!loading && (
          <>
            {meta && (meta.last_scan_at || events.length > 0) && (
              <div className="events-summary">
                <span className="summary-count">{events.length} ta tadbir</span>
                {meta.folder_title && <span className="summary-item">Papka: {meta.folder_title}</span>}
                {meta.last_scan_at && (
                  <span className="summary-item">Oxirgi tekshiruv: {fmtDate(meta.last_scan_at)}</span>
                )}
              </div>
            )}

            {!scanning && events.length === 0 && (
              <div className="events-empty">
                <IconCalendar size={40} />
                <div className="empty-title">Hozircha tadbir topilmadi</div>
                <div className="empty-sub">Papkani tanlab «Skanerlash» tugmasini bosing.</div>
              </div>
            )}

            {scanning && (
              <div className="events-status">
                <IconSpinner size={26} />
                <span>Kanallar tekshirilmoqda… biroz vaqt olishi mumkin</span>
              </div>
            )}

            {!scanning && events.length > 0 && (
              <div className="events-result">
                {/* Keng ekran: jadval */}
                <table className="events-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Tadbir nomi</th>
                      <th>Maqsadi</th>
                      <th>Sana</th>
                      <th>Vaqti</th>
                      <th>Joyi</th>
                      <th>Manba</th>
                    </tr>
                  </thead>
                  <tbody>
                    {events.map((e, i) => (
                      <tr key={`${e.msg_tg_id ?? i}-${i}`}>
                        <td className="td-idx">{i + 1}</td>
                        <td className="td-name">
                          {e.name}
                          {e.by_ai && <span className="ai-tag">AI</span>}
                        </td>
                        <td className="td-purpose">{e.purpose || "—"}</td>
                        <td className="td-date">{fmtEventDate(e.event_at) || "—"}</td>
                        <td className="td-when">{e.when || "—"}</td>
                        <td className="td-place">{e.place || "—"}</td>
                        <td className="td-source">{e.source_title || ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                {/* Tor ekran (mobil): kartochkalar */}
                <div className="events-cards">
                  {events.map((e, i) => (
                    <div className="event-card" key={`${e.msg_tg_id ?? i}-${i}`}>
                      <div className="event-card-head">
                        <span className="event-card-idx">{i + 1}</span>
                        <span className="event-card-name">
                          {e.name}
                          {e.by_ai && <span className="ai-tag">AI</span>}
                        </span>
                      </div>
                      {e.purpose && (
                        <div className="event-field">
                          <span className="field-label">Maqsadi</span>
                          <span>{e.purpose}</span>
                        </div>
                      )}
                      {fmtEventDate(e.event_at) && (
                        <div className="ev-field">
                          <span className="field-label">Sana</span>
                          <span>{fmtEventDate(e.event_at)}</span>
                        </div>
                      )}
                      {e.when && (
                        <div className="event-field">
                          <span className="field-label">Vaqti</span>
                          <span>{e.when}</span>
                        </div>
                      )}
                      {e.place && (
                        <div className="event-field">
                          <span className="field-label">Joyi</span>
                          <span>{e.place}</span>
                        </div>
                      )}
                      {e.source_title && (
                        <div className="event-field muted">
                          <span className="field-label">Manba</span>
                          <span>{e.source_title}</span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
