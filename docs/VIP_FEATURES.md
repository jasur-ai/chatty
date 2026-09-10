# VIP funksiyalar siyosati

> **Qaror (yakuniy):** Barcha asosiy funksiyalar **oddiy foydalanuvchilar uchun ham ochiq**.
> Faqat **AI (Lotus LLM)** VIP foydalanuvchilarga beriladi.

## Barcha foydalanuvchilar uchun (oddiy + VIP)

- Bot-persona: nom/rasm/story o'zgartirish
- Avto-javob (matn + takliflar + belgilangan odamlar + jadval)
- So'kinish filtri (warn/block/hide)
- Media yuborish: rasm, video, audio, fayl
- **Ovozli xabar** va **dumaloq video** yozib yuborish
- **Forward** (bir nechta chatga)
- **Rejalashtirilgan xabarlar** (jadval)
- **Qidiruv** (barcha chatlar bo'yicha)
- **Eksport** (JSON/CSV) va **to'liq zaxira**
- **Analitika** (xabarlar, faol soatlar, kunlik trend)
- **Avto-o'chirish** (yuborilgan xabarlar TTL)
- Musiqa taklifi + reaksiya

## VIP uchun

- **Lotus real AI (LLM)** — Groq/OpenRouter/Gemini orqali:
  - Aqlli kontekstli javoblar (salom/yordam/... dan tashqari erkin suhbat)
  - Xabarlarni **xulosa qilish**
  - **Tarjima** (uz/ru/en)
  - AI kontekstli avto-javob (kiruvchi xabarga qarab tabiiy javob)

Oddiy foydalanuvchilarda Lotus **offline rejimda** ishlaydi (buyruqlar: salom, yordam,
eslatma, til, hisobot) — hech qanday AI kalitisiz.

## LLM sozlash

`.env` da:

```
LOTUS_PROVIDER=groq       # groq | openrouter | gemini | custom
LOTUS_LLM_KEY=<sizning-key>
LOTUS_LLM_MODEL=llama-3.3-70b-versatile
```

- **Groq** (tavsiya): https://console.groq.com → tekin, karta shart emas, juda tez
- **OpenRouter**: https://openrouter.ai → `:free` modellar tekin
- **Gemini**: Google AI Studio → tekin (~1500 req/kun)

`LOTUS_LLM_KEY` bo'sh qolsa tizim to'liq offline ishlaydi (xatolik bermaydi).
