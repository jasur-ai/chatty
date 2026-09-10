# VIP Premium funksiyalar (20 ta) — tasdiqlash uchun

> Bu funksiyalar yuqoridagi asosiy funksiyalardan TASHQARI qo'shimcha premium
> imkoniyatlardir. Har biri `is_vip` bo'lgan foydalanuvchilar uchun ochiladi.
> Tasdiqlaganingizdan keyin implementatsiya qilinadi.

## Aloqa / Chat

1. **Cheksiz akkaunt ulash** — oddiy foydalanuvchi 3 tagacha, VIP cheksiz akkaunt/bot ulaydi.
2. **AI kontekstli avto-javob** — avto-javob oddiy matn emas, kiruvchi xabarga qarab Lotus
   kontekstli, tabiiy javob yozadi (LLM rejimida).
3. **Rejalashtirilgan xabar** — ma'lum vaqtga xabar yozib qo'yish (jadval asosida avtomatik yuboriladi).
4. **Avto-tarjima** — kiruvchi/chiqim xabarlarni ru/uz/en o'rtasida avtomatik tarjima qilish.
5. **Ovozli xabar yuborish** — app ichida ovoz yozib (voice) yuborish.
6. **Dumaloq video yuborish** — app ichida video-note (round video) yozib yuborish.
7. **Stiker/GIF kutubxonasi** — tez-tez ishlatiladigan stiker/reaksiya tezkor paneli.
8. **Ko'p chatga forward** — bitta xabarni bir nechta chatga birdaniga yo'naltirish.

## Tashkilot / Mahsuldorlik

9. **Barcha chatlar bo'yicha qidiruv** — bir akkauntdagi hamma chat/xabarlardan qidirish.
10. **Chat tarixini eksport qilish** — istalgan chatni CSV/JSON ko'rinishda yuklab olish.
11. **Avto-o'chirish** — yuborilgan xabarlar belgilangan vaqtdan keyin avtomatik o'chiriladi.
12. **Avto-javob jadvali** — avto-javob faqat ma'lum soatlarda ishlaydi (masalan: 9:00–18:00).
13. **Xabarlarni xulosa qilish** — uzun chat/yozishmalarni Lotus yordamida qisqa xulosaga olish.
14. **Chat zaxirasi/qayta tiklash** — barcha chatlarni R2'ga zaxiralash va tiklash.

## Analitika / Shaxsiylashtirish

15. **Kengaytirilgan analitika** — xabarlar soni, javob vaqti, faol soatlar grafiklari.
16. **Tezkor push-xabarnoma** — oddiy foydalanuvchiga batched (yig'ma), VIP'ga bir zumda push.
17. **Shaxsiy AI uslubi** — Lotus foydalanuvchining yozish uslubiga moslashadi (fine-tune).
18. **Maxsus mavzular** — default/pink'dan tashqari shaxsiy rang mavzulari.

## Imtiyozlar

19. **Yangi funksiyalarga erta kirish** — yangi chiqqan funksiyalar avval VIP'larga ochiladi.
20. **Maxsus qo'llab-quvvatlash** — VIP'lar uchun alohida yordam kanali va ustuvorlik.

---

## AI (Lotus) VIP integratsiyasi

VIP foydalanuvchi Lotus'ning to'liq imkoniyatlariga ega bo'ladi:
- Real LLM (LOTUS_LLM_URL sozlanganda) orqali aqlli javoblar;
- Voice chat (STT/TTS) to'liq yoqiladi;
- AI xabarlarni xulosa qiladi, javob taklif qiladi, eslatmalarni boshqaradi.

Oddiy foydalanuvchida Lotus offline (buyruqlar) rejimida ishlaydi.
