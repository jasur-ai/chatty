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
| 2. Chat funksiyalari: media, push-xabarnomalar, story | ⏳ navbatda |
| 3. Avto-javob + so'kinish filtri | ⏳ navbatda |
| 4. Admin panel + VIP | ⏳ navbatda |
| 5. Lotus AI 0.0.1 | ⏳ navbatda |
| 6. Pink rejim + final UI | ⏳ navbatda |

## Xavfsizlik

- `api_id`/`api_hash`, R2 kredensiallari faqat `.env` da (gitignore qilingan)
- StringSession'lar `SESSION_SECRET` bilan Fernet shifrlangan holda DB'da
- Web app JWT bilan himoyalangan