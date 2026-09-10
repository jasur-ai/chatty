# Chatty deploy qo'llanmasi

## Arxitektura

Chatty ikki qismdan iborat:

```
┌─────────────────────────┐      ┌──────────────────────────────┐
│  Frontend (React PWA +  │  →   │  Backend (Python FastAPI +    │
│  Telegram Mini App)     │      │  Telethon MTProto)            │
│  Cloudflare Pages ✓     │      │  Python talab qiladi          │
└─────────────────────────┘      └──────────────────────────────┘
```

- **Frontend** → Cloudflare Pages'da (statik, HTTPS). Telegram Mini App shu yerda.
- **Backend** → Python + Telethon. **Cloudflare Workers/Pages'da ISHLAMAYDI**
  (Workers serverless JS/WASM, Telethon'ga kerak bo'lgan doimiy TCP ulanish yo'q).

## Nima allaqachon qilingan (Cloudflare'da)

- ✅ **Frontend deployed**: `https://chatty-ws3.pages.dev`
- ✅ **Telegram Mini App** integratsiyasi (telegram-web-app.js, expand, theme)
- ✅ **Bot menu tugmasi** → "Chatty ochish" (`@chattiey_bot`)

## R2 (media storage) — hali aktivlashtirilmagan

Cloudflare Dashboard'da R2 hali yoqilmagan (API "Please enable R2" deb qaytardi).
**Buni qo'lda qilish kerak:**

1. https://dash.cloudflare.com → R2 → **Buy R2** (yoki "Enable R2")
2. Bucket yarating: `chatty-media`
3. `.env` da `R2_*` qiymatlari allaqachon to'g'ri (Account ID, keys, endpoint)

## Backend deploy (Render — tavsiya)

Repo allaqachon `Dockerfile` + `render.yaml` bilan tayyor:

1. https://render.com → GitHub bilan kirish
2. **New → Blueprint** → `jasur-ai/chatty` reponi tanlang
3. Secret env var'larni to'ldiring:
   - `TG_API_ID`, `TG_API_HASH`, `TG_BOT_TOKEN`
   - `R2_*` (agar R2 yoqilgan bo'lsa)
   - `SESSION_SECRET`, `JWT_SECRET`
   - `OWNER_ID=8004724563`, `ADMIN_IDS=8442078631`
   - `LOTUS_LLM_KEY` (Groq kaliti)
   - `BOT_REPLY_URL=https://chatty-ws3.pages.dev`
4. Deploy → backend URL olasiz, masalan `https://chatty.onrender.com`

### Frontend'ni backend'ga ulash

Backend URL olingach, frontend'ni qayta build qilib deploy qilish kerak:

```bash
cd web
VITE_API_BASE=https://chatty.onrender.com VITE_WS_BASE=wss://chatty.onrender.com npm run build
npx wrangler pages deploy dist --project-name=chatty
```

`VITE_API_BASE`/`VITE_WS_BASE` bo'sh qolsa frontend **o'zi bilan bir origin**'ga
(/api, /ws) murojaat qiladi — bu FastAPI `web/dist` xizmat qilganda to'g'ri ishlaydi.

## Muqobil: Fly.io yoki VPS

Backend'ni istalgan Python host'da ishga tushirish mumkin (Fly.io, VPS, Railway):

```bash
cd server
pip install -r requirements.txt
cp .env.example .env  # to'ldiring
python run.py         # yoki uvicorn app.main:app
```

## Mini App sinash

1. Telegram'da `@chattiey_bot` ni oching
2. Pastdagi **"Chatty ochish"** tugmasini bosing → mini app ochiladi
3. Backend ulangan bo'lsa, login (raqam → kod → 2FA) va chatlar ishlaydi
