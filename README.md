# Chatty

Telegram akkauntlarini MTProto orqali ulab, ularni **bot-persona**ga aylantiruvchi platforma.
Odamlar botga yozadi → siz Telegram interfeysidek app'da ko'rasiz → bot nomidan javob berasiz.

- **Server**: Python 3.14 · FastAPI · Telethon (MTProto) · SQLAlchemy · Cloudflare R2
- **Web app**: React 18 · Vite · TypeScript · PWA (Telegram official style)

To'liq spec: [`docs/PRD.md`](docs/PRD.md)

## Talablar

- Python 3.12+ (3.14 test qilingan)
- Node.js 20+
- `api_id` + `api_hash` — [my.telegram.org](https://my.telegram.org) → API development tools (**majburiy**)
- Cloudflare R2 kredensiallari (media storage uchun)

## Ishga tushirish

```bash
# 1. Server
cd server
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # Windows Git Bash
cp .env.example .env                            # api_id, api_hash, R2 ni to'ldiring
.venv/Scripts/python run.py                     # http://127.0.0.1:8000

# 2. Web app (boshqa terminal)
cd web
npm install
npm run dev                                     # http://127.0.0.1:5173
```

## Login jarayoni

1. Foydalanish shartlariga rozilik (raqam kiritishdan oldin)
2. Telefon raqam → Telegram'dan kod keladi
3. Kod → (2FA yoqilgan bo'lsa) parol → sessiya shifrlangan holda DB'da saqlanadi

> **Muhim**: 2FA yoqilgan bo'lishi shart — bu akkaunt xavfsizligi uchun zarur.

## Arxitektura

```
Web app (React PWA)  ⇄  REST + WebSocket  ⇄  FastAPI server  ⇄  MTProto (Telethon)  ⇄  Telegram
                                                    │
                                              Cloudflare R2 (media)
```

- **O'qilgan belgilar**: kiruvchi xabarlar hech qachon avtomatik o'qilgan qilinmaydi;
  faqat chat app'da ochilganda mark-read yuboriladi. ✓ / ✓✓ to'liq qo'llab-quvvatlanadi.
- **Ko'p akkaunt**: bitta serverda bir nechta Telegram akkaunt, app'da oson switch.
- **Admin**: owner id `8004724563`; barcha akkauntlar/chatlar/xabarlar kuzatuvi.

## Faza holati

| Faza | Holat |
|---|---|
| 1. Yadro: login, chatlar, xabarlar, read-receipts, WS, R2 | ✅ tayyor |
| 2. Chat funksiyalari: media, push-xabarnomalar, story, bot-persona | ✅ tayyor |
| 3. Avto-javob + so'kinish filtri (warn/block/hide) | ✅ tayyor |
| 4. Admin panel + VIP + adminlar boshqaruvi | ✅ tayyor |
| 5. Lotus AI 0.0.1 (offline + LLM, ru/uz/en, eslatmalar) + Admin AI hisobot | ✅ tayyor |
| 6. Pink rejim + final UI | ✅ tayyor |
| 7. Musiqa taklifi (banner + reaksiya) | ✅ tayyor |
| 8. 20 ta VIP funksiya | ⏳ tasdiqlash kutilmoqda ([docs/VIP_FEATURES.md](docs/VIP_FEATURES.md)) |

## Muhim sozlamalar

Login ishlashi uchun `.env` da quyidagilar **majburiy**:

- `TG_API_ID` / `TG_API_HASH` — my.telegram.org (bo'sh bo'lsa "TG_API_ID sozlanishi shart" xatosi)
- `TG_BOT_TOKEN` — xabarnoma boti (@BotFather'dan) — push-xabarnoma va "Javob yozish" tugmasi uchun
- `OWNER_ID=8004724563`, `ADMIN_IDS=8442078631`
- `REPORT_INTERVAL_HOURS=2` — Admin AI hisobot oraliq (1/2/4/6/8)
- `LOTUS_LLM_URL` / `LOTUS_LLM_KEY` — (ixtiyoriy) real AI uchun; bo'sh bo'lsa Lotus offline rejimda ishlaydi

## Xususiyatlar

- **Avto-javob**: yoqish + matn (tayyor takliflar) + "belgilangan odamlar" ro'yxati
- **So'kinish filtri**: 1-2 marta ogohlantirish, 3-marta blok; guruhda xabarlar yashiriladi
- **Bot-persona**: nom/rasm default akkaunt bilan bir xil, keyin alohida o'zgartiriladi; story joylash
- **Admin**: barcha akkauntlar kuzatuvi, VIP (tasdiqlash bilan), admin qo'shish/olib tashlash,
  hisobot oraliq sozlash, hisobotlar tarixi
- **Lotus 0.0.1**: yordamchi AI (salom/yordam/eslatma/til/hisobot buyruqlari), suzuvchi oyna
- **Pink rejim**: id `8442078631` ulanganda butun tizim "pick me pink" rejimga o'tadi

## Deploy (Render)

Loyiha Docker'ga tayyor (`Dockerfile`). Render'da:

1. [render.com](https://render.com) → **New > Blueprint** → `render.yaml` (repo ichida)
2. GitHub reponi ulang (`jasur-ai/chatty`)
3. Dashboard'da secret env var'larni to'ldiring: `TG_API_ID`, `TG_API_HASH`, `TG_BOT_TOKEN`,
   `R2_*`, `SESSION_SECRET`, `JWT_SECRET`, `BOT_REPLY_URL=https://<sizning-url>.onrender.com`
4. Deploy — `render.yaml` avtomatik disk (`/app/data` — sessiyalar saqlanadi) va health check sozlaydi

> Render **Starter** ($7/oy) doimiy ishlaydi; bepul plan 15 daqiqa harakatsizlikda uxlab qoladi (bot uchun yaroqsiz).
> Muqobil: Fly.io (CLI, bepul allowance) yoki VPS.

## Xavfsizlik

- `api_id`/`api_hash`, R2 kredensiallari faqat `.env` da (gitignore qilingan)
- StringSession'lar `SESSION_SECRET` bilan Fernet shifrlangan holda DB'da
- Web app JWT bilan himoyalangan