# Chatty deploy qo'llanmasi

## Arxitektura

```
┌─────────────────────────┐      ┌──────────────────────────────┐
│  Frontend (React PWA +  │  →   │  Backend (Python FastAPI +    │
│  Telegram Mini App)     │      │  Telethon MTProto)            │
│  Cloudflare Pages       │      │  Render (Docker)              │
└─────────────────────────┘      └──────────────────────────────┘
```

- **Frontend** → Cloudflare Pages (`https://chatty-ws3.pages.dev`).
- **Backend** → Render (`https://chatty-3eje.onrender.com`).

## ⚠️ ENG MUHIM: Ma'lumotlar saqlanishi (persistence)

Chatty sessiyalar, akkauntlar, chatlar va xabarlarni **ma'lumotlar bazasida** saqlaydi
(SQLite `data/chatty.db` yoki Postgres).

**Render'da bu disk EPHEMERAL (vaqtinchalik) — har deploy/restart'da o'chib ketadi.**
Shuning uchun akkauntlar/chatlar yo'qoladi va har safar qayta kod so'raydi.

Yechim — IKKI variantdan biri (birini tanlang):

### Variant A: Persistent disk (oddiy)

1. Render'da service **Starter (pullik) plan**'da bo'lishi kerak (Free plan'da disk yo'q).
2. Service → **Disks** bo'limida yangi disk qo'shing:
   - **Mount path**: `/app/data`
   - **Size**: 1 GB
3. Redeploy qiling.

`render.yaml`'da bu disk allaqachon yozilgan (`mountPath: /app/data`, `sizeGB: 1`),
lekin blueprint orqali yaratilmagan bo'lsa disk biriktirilmagan bo'ladi — qo'lda tekshiring.

### Variant B: Postgres (tavsiya — mustahkam)

1. Postgres bazasi yarating:
   - **Render Postgres** (dashboard) yoki
   - **Neon / Supabase** (bepul tier).
2. `DATABASE_URL` env var'ini qo'shing:
   ```
   postgresql+asyncpg://USER:PASSWORD@HOST:5432/DBNAME
   ```
3. Redeploy qiling. Kod `DATABASE_URL` bor bo'lsa avtomatik Postgres ishlatadi.

## Nima allaqachon qilingan

- ✅ Frontend deployed: `https://chatty-ws3.pages.dev` (backend URL `env.ts` da default).
- ✅ Telegram Mini App integratsiyasi + to'liq ekran (auto expand/fullscreen).
- ✅ Bot menu tugmasi → "Chatty ochish" (`@chattiey_bot`).
- ✅ Media R2'siz ham ishlaydi — lokal disk fallback (`data/media/`).

## R2 (media storage) — ixtiyoriy

R2 hali aktivlashtirilmagan, lekin **shart emas** — media lokal disk'ga (`data/media/`)
tushadi. R2 qo'shmoqchi bo'lsangiz:

1. https://dash.cloudflare.com → R2 → Enable
2. Bucket: `chatty-media`
3. `.env` da `R2_*` qiymatlari allaqachon to'g'ri.

## Backend deploy (Render)

Repo `Dockerfile` + `render.yaml` bilan tayyor:

1. render.com → GitHub bilan kirish
2. **New → Blueprint** → `jasur-ai/chatty`
3. Secret env var'lar:
   - `TG_API_ID`, `TG_API_HASH`, `TG_BOT_TOKEN`
   - `SESSION_SECRET`, `JWT_SECRET`
   - `OWNER_ID=8004724563`, `ADMIN_IDS=` (bo'sh)
   - `LOTUS_LLM_KEY` (Groq)
   - `BOT_REPLY_URL=https://chatty-ws3.pages.dev`
   - `DATABASE_URL` (Variant B bo'lsa)
4. Deploy.

## Frontend build & deploy (Cloudflare)

Backend URL `web/src/env.ts` da default sifatida qo'yilgan (`https://chatty-3eje.onrender.com`),
shuning uchun oddiy `npm run build` yetarli. Boshqa URL kerak bo'lsa:

```bash
cd web
VITE_API_BASE=https://YOUR_BACKEND VITE_WS_BASE=wss://YOUR_BACKEND/ws npm run build
npx wrangler pages deploy dist --project-name=chatty --commit-dirty=true
```

## Mini App sinash

1. Telegram'da `@chattiey_bot` ni oching
2. "Chatty ochish" tugmasi → mini app
3. Login (raqam → kod → 2FA) → chatlar.
