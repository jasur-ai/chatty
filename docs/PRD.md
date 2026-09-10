# Chatty — PRD (Product Requirements Document)

> Professional spec. Uzbek tilida yozilgan, barcha talablar faza-faza bo'lib ajratilgan.
> Har bir faza mustaqil ishlaydigan, tekshiriladigan natija beradi.

---

## 1. Kontseptsiya

**Chatty** — Telegram akkauntlarini MTProto orqali ulab, ularni "bot-persona"ga aylantiruvchi
tizim. Odamlar sizning botingizga yozadi → siz buni Telegram interfeysidek chiroyli app'da
ko'rasiz → xuddi Telegram'dagidek javob yozasiz → javob bot nomidan boradi.

Bitta admin panel orqali bir nechta akkaunt (3+ ta) boshqariladi, oson switch qilinadi.

## 2. Arxitektura

```
┌──────────────────────────────────────────────────────────────┐
│  Web App (PWA) — React + Vite + TS                            │
│  Login · Chat list · Chat view · Sozlamalar · Admin panel     │
└──────────────┬───────────────────────────────────────────────┘
               │ REST + WebSocket (real-time)
┌──────────────▼───────────────────────────────────────────────┐
│  Server — Python FastAPI + Telethon (MTProto)                 │
│  • Account Manager (multi-session, StringSession DB'da)       │
│  • Xabar pipeline: update → DB → WS push                      │
│  • AI (Lotus) moduli · Auto-reply · Filtr (so'kinish)         │
│  • R2 (Cloudflare) media storage · JWT auth                   │
└──────────────┬───────────────────────────────────────────────┘
               │ MTProto (Telegram user API — 2FA bilan kirish)
        ┌──────▼──────┐
        │  Telegram   │  ← bot-persona sifatida ko'rinadi
        └─────────────┘
```

**Nega MTProto (Telethon)?** Bot API faqat bot uchun; odam akkaunti sifatida chatlarni
ko'rish, o'qilgan ✓✓ belgilar, media, guruhlar — bularning hammasi MTProto talab qiladi.
`api_id`/`api_hash` my.telegram.org saytidan olinadi (majburiy).

## 3. Tech stack

| Qatlam | Texnologiya |
|---|---|
| Backend | Python 3.14, FastAPI, Uvicorn, SQLAlchemy 2 (async), aiosqlite |
| MTProto | Telethon 1.44 |
| Storage | SQLite (dev) → PostgreSQL (prod tayyor), Cloudflare R2 (media) |
| Realtime | WebSocket |
| Frontend | React 18, Vite, TypeScript, PWA |
| AI | Lotus 0.0.1 (faza 5) — LLM + TTS/STT, ru/uz/en |

## 4. Faza 1 — Yadro (amalga oshirildi: 1-iteratsiya)

- [x] Monorepo scaffold (server + web + docs)
- [x] Telethon multi-account manager, login flow: telefon → kod → 2FA parol
- [x] StringSession shifrlangan holda DB'da
- [x] Xabar pipeline: kiruvchi xabar → DB → WebSocket → app
- [x] Xabar yuborish (matn), o'qilgan qilish (faqat user chatni ochganda!)
- [x] Dialoglar + xabarlar REST API
- [x] Web UI: Login (shartlar checkbox), chat list, chat view, ✓/✓✓, composer
- [x] R2 media storage (upload/download interfeys tayyor)
- [ ] Media yuborish (photo/video/round/audio/file) — 1.1
- [ ] O'qilgan/yo'q holat noto'g'ri auto-mark qilinmasligi (allaqachon yechilgan: mark-read faqat
      chat ochilganda) — 1.1 test

## 5. Faza 2 — Chat funksiyalari

- [ ] Media yuborish: rasm, video (dumaloq round video), audio, musiqa, fayl
- [ ] Javob berish (reply), forward
- [ ] Xabarnomalar: app ochiq bo'lmasa ham push ("3:21 min audio", "matn", "rasm" + **Javob yozish** tugmasi)
- [ ] Faqat odamlardan kelgan xabarlar push; kanal/guruh xabarlari faqat app ichida
- [ ] Qidiruv, chat pin, mute
- [ ] Story yuborish, profil rasmini o'zgartirish
- [ ] Bot sozlamalari: bot nomi/rasmi (default = user akkaunti bilan bir xil, keyin alohida o'zgartiriladi)

## 6. Faza 3 — Avto-javob va filtr

- [ ] Avto-javob: faqat belgilangan odamlarga o'zi yozadi; belgilanmagan bo'lsa user tuzgan matn
- [ ] Taklifiy matnlar: "Hozir bandman, keyinroq yozing", "Salom, nima bilan murojaat qilyapsiz?" ...
- [ ] So'kinish filtri: har safar ogohlantirish, 3 marta → blok
- [ ] Guruhda: faqat ogohlantirish; 3+ marta → o'sha odam xabarlari chatda ko'rinmaydigan qilinadi

## 7. Faza 4 — Admin tizimi

- [ ] Owner: id `8004724563` (barcha huquqlar)
- [ ] Admin panel: barcha ulangan akkauntlar/botlar kuzatuvi, 3+ akkaunt ochish va switch
- [ ] Akkauntlar tepasida ism ("Nilufar", "Bekzod" ...)
- [ ] Admin bo'limi: yangi admin qo'shish; owner yuqorida turadi
- [ ] User'ni VIP qilish (id kiritish yoki ro'yxatdan), tasdiqlash dialogi: "Haqiqatan ham VIP qilinsinmi?"
- [ ] VIP funksiyalar: research qilinib (20 ta), user tasdiqlagach qo'shiladi
- [ ] Shartlar matni oxiri: "...hamma narsa qattiq admin nazorati va kuzatuvi ostida olib boriladi"
- [ ] Musiqa taklifi: admin musiqa qo'ysa → "Sinab ko'rish" (tug'ilgan kun kabi banner) + like/dislike/reaksiya/komment

## 8. Faza 5 — Lotus AI 0.0.1

- [ ] Jarvis'ga o'xshash tekin AI, nomi **Lotus 0.0.1**, chiroyli rasm
- [ ] Butun appda yurib yuradi: yordam taklif qiladi, eslatma qo'yadi, eslatib turadi
- [ ] Real voice chat: voice chat yoqilgan holda chatga buyruq yozish mumkin
- [ ] Tillar: ru / uz / en (default: uz)
- [ ] Akkaunt ulangan bo'lsa hamma ruxsatga ega (app va Telegram)
- [ ] Birinchi kirishda raqam kiritishdan oldin foydalanish shartlari
- [ ] Admin AI: 1/2/4/6/8 soatda hisobot (default 2 soat, sozlanadigan), voice chat enable,
      eslatma qilishdan oldin so'raydi, til o'zgartirishni tasdiqlatadi
      ("Tilni o'zgartirishni xohlaysizmi?" → Ha), sozlamalarni tahrirlay oladi
      (masalan: "hamma meni guruhga qo'sha oladigan bo'lmasin")

## 9. Faza 6 — UI/UX va rejimlar

- [ ] Default: Telegram rasmiy ko'k rang, dark mode qora — official Telegram style
- [ ] Pink rejim: id `8442078631` ulanganda "Taklifni qabul qilish (rejimni o'zgartirish)" →
      butun tizim pink ("Pick me pink" Pinterest fon) — faqat admin
- [ ] Emoji yo'q — faqat icon ishlatiladi (professional UI/UX, senior daraja)
- [ ] PWA: telefonga o'rnatish, offline cache

## 10. Muhim texnik qarorlar

1. **O'qilgan belgilar**: kiruvchi xabarlar hech qachon avtomatik o'qilgan qilinmaydi.
   Telethon default'da mark_read qilmaydi; faqat user chatni app'da ochganda
   `messages.mark_read` chaqiriladi. Shu bilan "botga yuborilgan hamma narsa oqilgan" muammosi yechiladi.
2. **Session xavfsizligi**: StringSession lokaldagi secret bilan shifrlanib DB'da saqlanadi.
3. **R2**: media fayllar S3-compatible R2'ga yuklanadi, public URL qaytariladi.
4. **Admin nazorati**: barcha akkauntlar, chatlar, xabarlar DB'da; owner/admin hammasini ko'radi.

## 11. Ishga tushirish

```bash
# Server
cd server
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
cp .env.example .env   # api_id, api_hash, R2 kredensiallarini to'ldir
.venv/Scripts/python run.py

# Web
cd web
npm install
npm run dev
```

**Majburiy**: my.telegram.org → API development tools → `api_id` + `api_hash` (.env'ga).