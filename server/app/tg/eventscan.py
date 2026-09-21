"""Telegram papkalaridan tadbir/event'larni aniqlash (skaner).

Berilgan papka (kanallar/guruhlar to'plami) ichidagi so'nggi N kunlik xabarlarni
kalit so'zlar bo'yicha tekshiradi va topilgan tadbirlarni tartibli jadval
ko'rinishida qaytaradi: nomi, maqsadi, vaqti, o'tkaziladigan joyi.

Ishlash tartibi:
  1. Akkauntning Telegram papkalari olinadi (GetDialogFilters).
  2. Tanlangan papkadagi kanal/guruhlar bo'ylab so'nggi `days` kunlik xabarlar
     o'qiladi (eng yangidan eskiga, kesish sanasiga yetganda to'xtaydi).
  3. Kalit so'zga mos xabarlar ajratilib, ulardan tadbir maydonlari ajratib olinadi
     (nomi, maqsadi, vaqti, joyi). Asosiy ajratish — lokal evristika (bepul, tez).
     LLM sozlangan bo'lsa, natija AI bilan aniqlashtiriladi (VIP).
"""
import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone

from telethon import functions
from telethon.tl.types import DialogFilterDefault, InputPeerUser, PeerUser

from .manager import manager
from .sync import kind_of

log = logging.getLogger("chatty.eventscan")

# So'nggi qancha kunlik xabarlar tekshiriladi (default)
DEFAULT_DAYS = 7
# Bir skanerlashda ko'pi bilan qancha kanal/guruh va xabar o'qiladi (Telegram'ni
# ortiqcha yuklamaslik va javobni uzoq kuttirmaslik uchun)
MAX_CHANNELS = 25
MAX_PER_CHANNEL = 80

# Tadbir/event belgilari — kalit so'zlar (uz/ru/en). Lug'at kengaytirilishi mumkin.
EVENT_KEYWORDS = [
    # o'zbek
    "tadbir", "seminar", "konferensiya", "konferens", "trening", "vebinar", "webinar",
    "kurs", "master-klass", "masterklass", "hakaton", "olimpiada", "marafon", "tanlov",
    "musobaqa", "festival", "anjuman", "forum", "uchrashuv", "yarmarka", "korgazma",
    "ko'rgazma", "konsert", "spektakl", "premyera", "saylov", "aksiya", "ochiq eshik",
    "qabul kun", "ro'yxatdan o'tish", "royxatdan otish", "eksposisiya", "vorkshop",
    # rus
    "мероприятие", "семинар", "конференция", "вебинар", "тренинг", "мастер-класс",
    "воркшоп", "хакатон", "олимпиада", "конкурс", "фестиваль", "форум", "лекция",
    "экскурсия", "выставка", "концерт", "спектакль", "премьера", "ярмарка", "отбор",
    # ingliz
    "event", "meetup", "workshop", "hackathon", "conference", "seminar", "webinar",
    "masterclass", "bootcamp",
]

# O'zbek/rus oylari (vaqt ajratish uchun)
_MONTHS = (
    "yanvar|fevral|mart|aprel|may|iyun|iyul|avgust|sentabr|oktabr|noyabr|dekabr|"
    "январ|феврал|март|апрел|ма[йя]|июн|июл|август|сентябр|октябр|ноябр|декабр|"
    "yan|fev|mar|apr|iyn|iyl|avg|sen|okt|noy|dek"
)
_WEEKDAYS = (
    "dushanba|seshanba|chorshanba|payshanba|juma|shanba|yakshanba|"
    "понедельник|вторник|среда|четверг|пятниц|суббот|воскресенье"
)


# ---------------- umumiy yordamchilar ----------------
async def _require_client(account_id: int):
    client = manager.get(account_id)
    if client is None:
        raise ValueError("Akkaunt Telegram'ga ulangan emas")
    return client


def _norm_keywords(extra: str | None) -> list[str]:
    """Standart lug'atga qo'shimcha kalit so'zlarni qo'shadi (kichik harfda)."""
    words = [w.strip().lower() for w in (extra or "").replace("\n", ",").split(",")]
    words = [w for w in words if w]
    merged = [_norm_apos(w.lower()) for w in EVENT_KEYWORDS]
    for w in words:
        if w not in merged:
            merged.append(w)
    return merged


# ---- E'lon va hisobotni ajratish ----
# Skaner avval "tadbir" so'zi bor HAR QANDAY postni olayotgan edi, shuning uchun
# natijada o'tib bo'lgan tadbirlarning hisobotlari ("...dan video lavha",
# "Natija", "g'oliblar") chiqardi — foydalanuvchi ularni "real emas" deb topdi.

# Tadbir ALLAQACHON o'tib bo'lganini bildiruvchi belgilar (hisobot/lavha)
PAST_SIGNALS = [
    "bo'lib o'tdi", "bo'lib otdi", "o'tib bo'lgan", "o'tib bolgan",
    "yakunlandi", "yakuniga yetdi", "yakunlari", "o'tkazildi", "otkazildi",
    "tashrif buyurdi", "tashrif buyurdik", "tashrif",
    "lavha", "lavhalar", "foto lavha", "video lavha", "fotosessiya",
    "fotoreportaj", "foto hisobot", "qisqacha", "esdalik", "unutilmas",
    "natijalar", "natija", "g'oliblar", "goliblar", "rahmat", "minnatdor",
    "kecha bo'lib", "bugun bo'lib",
    "состоялось", "состоялся", "состоялась", "прошел", "прошла", "прошло",
    "завершился", "завершилась", "итог", "итоги", "благодарим", "спасибо",
    "фоторепортаж", "победители",
]

# Tadbir KELGUSIDA bo'lishini bildiruvchi belgilar (haqiqiy e'lon)
FUTURE_SIGNALS = [
    "bo'lib o'tadi", "bo'lib otadi", "o'tkaziladi", "otkaziladi",
    "o'tkazilmoqda", "otkazilmoqda", "kutilmoqda", "rejalashtirilgan",
    "taklif etamiz", "taklif qilamiz", "taklif etiladi", "taklif etmoqda",
    "ro'yxatdan o'ting", "ro'yxatdan o'tish", "royxatdan otish", "royxatdan oting",
    "boshlanadi", "unutmang", "unutlang", "shoshiling", "imkoniyatni qo'ldan",
    "sana:", "vaqt:", "manzil:", "joyi:", "boshlanish vaqti", "boshlanish sanasi",
    "budet", "будет", "пройдет", "пройдёт", "приглашаем", "регистрация",
    "ждём", "ждем", "не пропустите", "успейте", "заявки",
]


def _dedup_sig(name: str, when_: str, source: str) -> str:
    """Dublikatni aniqlash uchun qisqa imzo.

    Bir xil tadbir bir nechta kanalda e'lon qilinadi; shuningdek bitta post
    '(1-qism)'/'(2-qism)' bo'laklariga bo'linib takrorlanadi. Nom + vaqt
    bo'yicha takrorlanishni oldini olamiz.
    """
    n = re.sub(r"\(\s*\d+\s*[- ]?qism\s*\)", " ", name or "", flags=re.I)
    n = re.sub(r"[^\w\s]", "", n.lower())
    n = re.sub(r"\s+", " ", n).strip()
    n = " ".join(n.split()[:6])
    w = re.sub(r"[^\w\s:]", "", (when_ or "").lower()).strip()
    return f"{n}|{w}"


# Apostrof normallashtirish. O'zbek matnlarida ' (U+2018) va ' (U+2019)
# ishlatiladi, signal/kalit so'zlarimizda esa ASCII '. Shu sababli
# "bo'lib o'tdi" kabi signallar haqiqiy matnda HECH QACHON topilmasdi —
# hisobot filtri shuning uchun ishlamagan.
_APOS_MAP = str.maketrans({"\u2018": "'", "\u2019": "'", "\u02bb": "'", "`": "'", "\u00b4": "'"})


def _norm_apos(text: str) -> str:
    return (text or "").translate(_APOS_MAP)


def classify_post(text_low: str) -> str:
    """Post turini aniqlaydi: 'past' (hisobot) | 'future' (e'lon) | 'unknown'."""
    t = _norm_apos(text_low)
    if any(sig in t for sig in PAST_SIGNALS):
        return "past"
    if any(sig in t for sig in FUTURE_SIGNALS):
        return "future"
    return "unknown"


def _matches_event(text_low: str, keywords: list[str]) -> bool:
    """Haqiqiy tadbir E'LONI bo'lsa True.

    Qoida:
      - hisobot/lavha postlari — butunlay tashlanadi (o'tib bo'lgan tadbir);
      - kelgusi belgisi bor postlar — olinadi;
      - belgi aniqlanmagan postlar — faqat sana/vaqt topilsa olinadi
        (aks holda bu shunchaki "tadbir" so'zi uchragan oddiy post).
    """
    t = _norm_apos(text_low)
    if not any(k in t for k in keywords):
        return False
    kind = classify_post(t)
    if kind == "past":
        return False
    if kind == "future":
        return True
    return bool(extract_when(t))


_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"  # belgilar, rasmlar, emoji
    "\u2600-\u27BF"  # turli belgilar
    "\u2B00-\u2BFF"  # strelkalar/yulduzchalar
    "\u2190-\u21FF"  # strelkalar
    "\uFE0F\u200d"  # emoji selektor/biriktiruvchi
    "\u2460-\u24FF"  # o'ralgan raqamlar
    "]+"
)


def _clean_line(s: str, limit: int = 200) -> str:
    """Emoji/hashtag/shovqinni tozalab, qatorni qisqartiradi."""
    s = _EMOJI_RE.sub(" ", s or "")
    s = re.sub(r"[#\u200b-\u200f\ufeff]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" \t•·—–-:|")
    return s[:limit].strip()


# ---------------- papkalar ----------------
def _iter_filters(res):
    """GetDialogFiltersRequest javobidan papka ro'yxatini qaytaradi.

    Javob — DialogFilters OBYEKTI (iterable emas); ro'yxat .filters atributida.
    Shu helper orqali o'qiymiz, chunki xuddi shu xato ikki joyda takrorlangan edi
    (list_folders va scan_folder).
    """
    items = getattr(res, "filters", None)
    if items is None and isinstance(res, (list, tuple)):
        items = res
    for item in items or []:
        yield getattr(item, "filter", item)  # DialogFilterSuggested -> .filter


def _to_naive_utc(dt):
    """Har qanday datetime'ni naive UTC'ga keltiradi.

    Telethon 1.45'da `msg.date` — timezone-AWARE. Kod esa cutoff'ni naive
    qilib hisoblardi, natijada har bir kanalning BIRINCHI xabarida
    "can't compare offset-naive and offset-aware datetimes" TypeError chiqardi.
    Bu xato `except Exception` ichida yutilgani uchun barcha kanal jim
    o'tkazib yuborilardi va skaner doim 0 ta tadbir qaytarardi.
    """
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _folder_title(title) -> str:
    """Papka nomini oddiy matnga aylantiradi.

    Yangi Telegram qatlamlarida `title` — TextWithEntities OBYEKTI
    ({'text': 'channels', 'entities': []}), oddiy str emas. Shu sababli
    ro'yxatda nomi xom ko'rinishda chiqardi.
    """
    if title is None:
        return "Papka"
    text = getattr(title, "text", None)
    if text is None and isinstance(title, dict):
        text = title.get("text")
    if text is None:
        text = str(title)
    return text.strip() or "Papka"


async def list_folders(account_id: int) -> list[dict]:
    """Akkauntning Telegram papkalarini qaytaradi (faqat kanal/guruh borlari).

    Peer'larni ochib o'tirmasdan, papkadagi kanal/guruh sonini hisoblaymiz
    (InputPeerChannel/InputPeerChat — kanal yoki guruh; InputPeerUser — odam, tashlanadi).
    """
    client = await _require_client(account_id)
    try:
        res = await asyncio.wait_for(client(functions.messages.GetDialogFiltersRequest()), timeout=20)
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"Papkalarni o'qib bo'lmadi: {e}") from e

    # MUHIM: javob — DialogFilters OBYEKTI (iterable emas), ro'yxat uning
    # .filters atributida. Avval `for f in res` yozilgani uchun
    # "'DialogFilters' object is not iterable" xatosi chiqardi.
    folders: list[dict] = []
    for f in _iter_filters(res):
        if f is None or isinstance(f, DialogFilterDefault):
            continue

        peers = list(getattr(f, "include_peers", []) or [])
        peers += list(getattr(f, "pinned_peers", []) or [])
        n = sum(1 for p in peers if not isinstance(p, (InputPeerUser, PeerUser)))

        # Qoidaga asoslangan papkalar (groups=True / broadcasts=True) aniq peer
        # ro'yxatiga ega bo'lmaydi — lekin aynan shular kanal/guruh papkasi.
        # Ularni tashlab yubormaslik kerak, aks holda foydalanuvchi papkasini
        # ro'yxatdan topa olmaydi.
        by_rule = bool(getattr(f, "groups", False) or getattr(f, "broadcasts", False))
        if n == 0 and not by_rule:
            continue  # faqat odamlar bor papka — tadbir skaneri uchun keraksiz

        folders.append(
            {
                "id": int(getattr(f, "id", 0)),
                "title": _folder_title(getattr(f, "title", "")),
                "peers": n,
                "by_rule": by_rule and n == 0,
            }
        )
    return folders


# ---------------- ajratish (evristika) ----------------
def extract_when(text: str) -> str:
    """Matndan sana/vaqt ma'lumotini ajratib oladi."""
    parts: list[str] = []
    low = text.lower()
    # "soat 15:00" / "15:00 da"
    for m in re.finditer(r"\b(\d{1,2})[:.](\d{2})\b", text):
        parts.append(f"{int(m.group(1)):02d}:{m.group(2)}")
    # 25.09.2026 / 25/09 / 25-09-2026
    for m in re.finditer(r"\b(\d{1,2})[./-](\d{1,2})(?:[./-](\d{2,4}))?\b", text):
        d, mo = m.group(1), m.group(2)
        y = m.group(3)
        parts.append(f"{d}.{mo}" + (f".{y}" if y else ""))
    # "25-sentabr" / "25 sentabr" / "25 сентября"
    for m in re.finditer(rf"\b(\d{{1,2}})\s*[-–]?\s*({_MONTHS})\w*", low):
        parts.append(f"{m.group(1)} {m.group(2).capitalize()}")
    # kun nomi
    for m in re.finditer(rf"\b({_WEEKDAYS})\b", low):
        parts.append(m.group(1).capitalize())
    # dublikatlarni olib tashlab, tartibda birlashtirish
    seen, out = set(), []
    for p in parts:
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return ", ".join(out[:5])


def extract_place(text: str) -> str:
    """O'tkaziladigan joyni ajratib oladi (manzil belgisi yoki manzil naqshlari)."""
    # 1) aniq belgilar: "manzil:", "joy:", "location:", "адрес:", "место:" ...
    m = re.search(
        r"(?:manzil|joy|o['’]tkaziladigan joy|location|address|адрес|место|локация)\s*[:：]\s*([^\n]+)",
        text,
        flags=re.I,
    )
    if m:
        return _clean_line(m.group(1), 180)
    # 2) qatorlar ichida manzil naqshlari.
    #    Kirish sharti ham kengaytirildi — avval faqat ko'cha/tuman/shahar
    #    tekshirilardi, shuning uchun "kampus", "saroy", "auditoriya",
    #    "bino" dagi joylar umuman topilmasdi.
    for line in text.splitlines():
        if _PLACE_HINT_RE.search(line):
            cleaned = _short_place(line)
            if cleaned:
                return cleaned
    return ""


# Joy belgilari (kirish sharti va _short_place ichida bir xil ishlatiladi)
_PLACE_HINT_RE = re.compile(
    r"ko['’]chasi|ko['’]cha|tumani|tumanida|shahar|shahrida|prospekt|prospektida|"
    r"bino|auditoriya|auditoriyada|saroy|saroyida|maydon|maydonida|"
    r"universitet|universiteti|kampus|kampusida|"
    r"проспект|улица|ул\.|город|дом|здание|аудитория",
    re.I,
)


def _short_place(line: str) -> str:
    """Manzil qatoridan faqat joy iborasini oladi.

    Avval butun qator qaytarilardi, natijada 'joy' ustuniga butun gap tushardi:
    "25-26-sentabr kunlari Ellikqal'a tumanida 'Sahro sadosi' IV xalqaro
    festivali o'tkaziladi." — bu joy emas, gap.
    """
    cleaned = _clean_line(line, 180)
    if not cleaned:
        return ""
    # Gap bo'lib ketgan bo'lsa — verguldan keyingi manzil qismini olamiz
    parts = [x.strip() for x in re.split(r"[,;]\s*", cleaned) if x.strip()]
    place_re = re.compile(
        r"ko['’]chasi|ko['’]cha|tumani|tumanida|shahar|shahrida|prospekt|prospektida|"
        r"bino|auditoriya|auditoriyada|saroy|saroyida|maydon|maydonida|"
        r"universitet|universiteti|kampus|kampusida|"
        r"проспект|улица|ул\.|город|дом|здание|аудитория",
        re.I,
    )
    best = ""
    for part in parts:
        m = place_re.search(part)
        if not m:
            continue
        # Gap emas, joy IBORASINI olamiz: kalit so'z atrofidagi so'zlar
        words = part.split()
        # kalit so'zning indeksini topamiz
        idx = 0
        pos = 0
        for i, w in enumerate(words):
            if place_re.search(w):
                idx = i
                break
        start = max(0, idx - 3)
        end = min(len(words), idx + 3)
        phrase = " ".join(words[start:end]).strip(" ,;:-")
        # Shovqinli boshlanishlarni kesamiz
        phrase = re.sub(
            r"^(\d{1,2}[- ]\d{1,2}[- ]?\w*\s+kunlari|\d{1,2}\s*\w+\s*kuni|"
            r"kunlari|kuni)\s+",
            "",
            phrase,
            flags=re.I,
        )
        # Gap fe'lini olib tashlaymiz ("o'tkaziladi" va h.k.)
        phrase = re.sub(
            r"\b(o['’]?tkaziladi|bo['’]?lib\s+o['’]?tadi|taklif\s+etamiz|o['’]?tkazilmoqda)\b.*$",
            "",
            phrase,
            flags=re.I,
        ).strip(" ,;:-")
        # Boshidagi ortiqcha yuklama/vaqt so'zlarini kesamiz ("da TDIU..." -> "TDIU...")
        phrase = re.sub(
            r"^(da|ta|soat|kunlari|kuni|va|hamda|orqali|\d{1,2}[:.]\d{2})\s+",
            "",
            phrase,
            flags=re.I,
        ).strip(" ,;:-")
        if phrase and len(phrase) > len(best):
            best = phrase
    if best:
        return best[:100]
    return ""


# Sarlavha bo'la olmaydigan boshlanishlar (murojaat/shovqin/qism belgilari)
_NAME_SKIP = (
    "hurmatli", "assalomu", "salom", "diqqat", "e'lon", "elon", "va nihoyat",
    "va niqoyat", "kutilgan lahza", "shoshiling", "unutmang", "do'stlar",
    "dostlar", "qism", "davom", "muhim", "yangilik", "xabar",
    "уважаемые", "здравствуйте", "внимание", "друзья",
)
_PART_RE = re.compile(r"^\(?\s*\d+\s*[- ]?\s*(qism|part|часть)\s*\)?$", re.I)


def _is_title_like(cleaned: str) -> bool:
    """Qator sarlavhaga o'xshaydimi (murojaat/shovqin emas)?"""
    if len(cleaned) < 8 or len(cleaned) > 110:
        return False
    low = cleaned.lower()
    if _PART_RE.match(cleaned):
        return False
    if any(low.startswith(skip) for skip in _NAME_SKIP):
        return False
    # Faqat katta harf + undov belgisidan ibarat shovqin ("VA NIHOYAT…")
    letters = [ch for ch in cleaned if ch.isalpha()]
    if letters and all(ch.isupper() for ch in letters) and cleaned.endswith(("!", "…", "...")):
        return False
    # Juda ko'p undov belgisi — sarlavha emas
    if cleaned.count("!") >= 2:
        return False
    return True


_DATE_CUT_RE = re.compile(
    r"\b(?:\d{1,2}\s*[:.]\s*\d{2}"                       # 10:00
    r"|\d{1,2}\s*[./-]\s*\d{1,2}"                        # 23.09
    r"|\d{1,2}\s*[-–]?\s*(?:" + _MONTHS + r")\w*"        # 23-sentabr
    r")",
    re.I,
)


def _shorten_name(line: str) -> str:
    """Uzun gapdan qisqa sarlavha yasaydi.

    Butun gap nom sifatida chiqmasligi uchun: sana/vaqt boshlanishidan oldingi
    qism olinadi, so'ng 70 belgigacha so'z chegarasida qisqartiriladi.
    """
    m = _DATE_CUT_RE.search(line)
    if m and m.start() >= 12:
        line = line[: m.start()]
    line = re.sub(r"[\s,;:–—-]+$", "", line.strip())
    if len(line) <= 72:
        return line
    cut = line[:72]
    sp = cut.rfind(" ")
    if sp > 30:
        cut = cut[:sp]
    return re.sub(r"[\s,;:–—-]+$", "", cut).strip()


def derive_name(text: str) -> str:
    """Tadbir nomini ajratadi.

    Avvalgi versiya shunchaki birinchi qatorni olardi, shuning uchun nom o'rniga
    murojaat chiqardi: 'Hurmatli TDIU talabalari!', 'VA NIHOYAT… KUTILGAN
    LAHZA YETIB KELDI!', '(1-qism)'. Endi murojaat/shovqin/qism qatorlari
    o'tkaziladi va imkon bo'lsa tadbir kalit so'zi bor qator tanlanadi.
    """
    lines = [_clean_line(l, 140) for l in text.splitlines()]
    lines = [l for l in lines if l]

    # 1) tadbir kalit so'zi bor sarlavha-o'xshash qator — eng yaxshi nom
    for l in lines[:8]:
        if _is_title_like(l) and any(k in l.lower() for k in EVENT_KEYWORDS):
            return _shorten_name(l)
    # 2) shunchaki sarlavha-o'xshash birinchi qator
    for l in lines[:8]:
        if _is_title_like(l):
            return _shorten_name(l)
    # 3) sarlavha topilmasa — birinchi ma'noli qator
    for l in lines:
        if len(l) >= 8:
            return _shorten_name(l)[:120]
    return _clean_line(text.replace("\n", " "), 120) or "Tadbir"


def derive_purpose(text: str, name: str, when_: str, place: str) -> str:
    """Maqsad/tavsif: sarlavha, vaqt va joydan boshqa birinchi ma'noli qator."""
    used = {name, when_, place}
    for line in text.splitlines():
        cleaned = _clean_line(line, 200)
        if not cleaned or cleaned in used:
            continue
        # sana/vaqt yoki manzil qatori bo'lsa — tavsif emas
        if re.fullmatch(r"[\d\s:.,/-]+", cleaned):
            continue
        return cleaned
    return ""


def extract_event(text: str, source_title: str, source_kind: str, msg) -> dict:
    """Bitta xabardan tadbir maydonlarini ajratadi (lokal evristika)."""
    name = derive_name(text)
    when_ = extract_when(text)
    place = extract_place(text)
    purpose = derive_purpose(text, name, when_, place)
    msg_date = _to_naive_utc(msg.date)
    return {
        "name": name,
        "purpose": purpose,
        "when": when_,
        "place": place,
        "source_title": source_title,
        "source_kind": source_kind,
        "msg_tg_id": int(msg.id),
        "msg_date": msg_date.isoformat() if msg_date else None,
        "text": text[:2000],
        "by_ai": False,
    }


# ---------------- AI bilan aniqlashtirish (VIP) ----------------
async def _ai_refine(events: list[dict], account_id: int) -> list[dict] | None:
    """Topilgan tadbirlarni LLM yordamida aniqlashtiradi (bitta so'rovda).

    LLM sozlanmagan yoki foydalanuvchi VIP bo'lmasa None qaytaradi —
    evristik natija o'z kuchida qoladi.
    """
    if not events:
        return None
    try:
        from ..lotus import is_vip, lotus  # noqa: PLC0415
    except Exception:  # noqa: BLE001
        return None
    if not lotus.llm_enabled:
        return None
    if not await is_vip(account_id):
        return None

    # Har bir tadbir matnini qisqartirib, bitta so'rovga joylaymiz
    batch = []
    for i, ev in enumerate(events[:15]):
        snippet = (ev["text"] or "")[:500]
        batch.append(f"[{i}] {snippet}")
    prompt = (
        "Quyida Telegram kanallaridan topilgan e'lonlar bor. Har biridan tadbir ma'lumotini "
        "ajrat. Javobni FAQAT JSON massiv ko'rinishida qaytar (boshqa hech narsa yozma). "
        "Har bir element: {\"i\": raqam, \"name\": \"tadbir nomi\", \"purpose\": \"maqsadi yoki qisqa tavsif\", "
        "\"when\": \"sana va vaqt\", \"place\": \"o'tkaziladigan joy\"}. "
        "Ma'lumot bo'lmasa bo'sh satr qoldir.\n\n" + "\n\n".join(batch)
    )
    # Groq bepul tarifi vaqti-vaqti bilan 429 (Too Many Requests) qaytaradi.
    # Avval bitta urinishda jim None qaytarilardi — natijada AI aniqlashtirish
    # ishlamasdi va foydalanuvchi qo'pol evristik nomlarni ko'rardi.
    # Endi qisqa kutish bilan bir necha marta urinamiz.
    out = None
    for attempt in range(3):
        out = await lotus._llm(
            [
                {"role": "system", "content": "Sen matnlardan tadbir ma'lumotini ajratuvchi yordamchisan. Faqat JSON qaytar."},
                {"role": "user", "content": prompt},
            ]
        )
        if out:
            break
        if attempt < 2:
            await asyncio.sleep(6 * (attempt + 1))
    if not out:
        log.info("AI aniqlashtirish ishlamadi (LLM javob bermadi) — evristik natija qoldi")
        return None
    try:
        import json  # noqa: PLC0415

        # JSON massivini matn ichidan ajratib olamiz (model qo'shimcha yozishi mumkin)
        start = out.find("[")
        end = out.rfind("]")
        if start == -1 or end == -1:
            return None
        data = json.loads(out[start : end + 1])
        by_idx = {int(item.get("i", -1)): item for item in data if isinstance(item, dict)}
    except Exception as e:  # noqa: BLE001
        log.warning("AI event JSON'ni o'qib bo'lmadi: %s", e)
        return None

    refined = []
    for i, ev in enumerate(events):
        item = by_idx.get(i)
        if item:
            refined.append(
                {
                    **ev,
                    "name": (item.get("name") or ev["name"]).strip()[:255],
                    "purpose": (item.get("purpose") or ev["purpose"]).strip(),
                    "when": (item.get("when") or ev["when"]).strip()[:255],
                    "place": (item.get("place") or ev["place"]).strip()[:255],
                    "by_ai": True,
                }
            )
        else:
            refined.append(ev)
    return refined


# ---------------- asosiy skaner ----------------
async def scan_folder(
    account_id: int,
    folder_id: int,
    days: int = DEFAULT_DAYS,
    extra_keywords: str = "",
) -> dict:
    """Papkadagi kanal/guruhlardan so'nggi `days` kunlik tadbirlarni topadi."""
    client = await _require_client(account_id)
    days = max(1, min(int(days or DEFAULT_DAYS), 30))
    keywords = _norm_keywords(extra_keywords)

    try:
        res = await asyncio.wait_for(client(functions.messages.GetDialogFiltersRequest()), timeout=20)
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"Papkalarni o'qib bo'lmadi: {e}") from e

    folder = next(
        (
            f
            for f in _iter_filters(res)
            if f is not None
            and not isinstance(f, DialogFilterDefault)
            and int(getattr(f, "id", -1)) == int(folder_id)
        ),
        None,
    )
    if folder is None:
        raise ValueError("Tanlangan papka topilmadi")

    all_peers = list(getattr(folder, "include_peers", []) or [])
    all_peers += list(getattr(folder, "pinned_peers", []) or [])
    peers = [p for p in all_peers if not isinstance(p, (InputPeerUser, PeerUser))]
    if not peers:
        return {
            "events": [],
            "scanned": 0,
            "folder_title": _folder_title(getattr(folder, "title", "")),
            "days": days,
        }

    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    events: list[dict] = []
    seen: set[tuple[int, int]] = set()  # (kanal_id, xabar_id) — dublikatni oldini oladi
    content_seen: set[str] = set()  # mazmun bo'yicha dublikat (bir xil tadbir)
    scanned = 0

    for p in peers[:MAX_CHANNELS]:
        try:
            ent = await asyncio.wait_for(client.get_entity(p), timeout=15)
        except Exception:  # noqa: BLE001
            continue
        kind = kind_of(ent)
        if kind not in ("channel", "group"):
            continue
        title = getattr(ent, "title", "") or "Kanal"
        ent_id = int(getattr(ent, "id", 0))
        scanned += 1
        try:
            async for msg in client.iter_messages(ent, limit=MAX_PER_CHANNEL):
                md = _to_naive_utc(msg.date)
                if md and md < cutoff:
                    break  # eng yangidan eskiga — kesish sanasiga yetdik

                # Servis xabarlar (qo'shildi/chiqdi...) — tadbir emas
                if getattr(msg, "action", None) is not None:
                    continue
                # Yo'nalishni aniq ajratamiz:
                #  - GURUHda o'zimiz yuborgan (out) xabarlar tadbir e'loni emas —
                #    ularni tashlab yuboramiz (chiqarib yuborilgan = bizniki).
                #  - KANALda postlar kanal nomidan bo'ladi (admin sifatida biz yozgan
                #    bo'lsak ham) — ularni qoldiramiz.
                if kind == "group" and getattr(msg, "out", False):
                    continue

                text = (msg.message or "").strip()
                if not text:
                    continue
                if not _matches_event(text.lower(), keywords):
                    continue
                key = (ent_id, int(msg.id))
                if key in seen:
                    continue
                seen.add(key)
                # Mazmun bo'yicha dublikat: bir xil tadbir bir nechta kanalda
                # e'lon qilinadi ("(1-qism)"/"(2-qism)" kabi bo'laklar ham).
                ev_probe = extract_event(text, title, kind, msg)
                sig = _dedup_sig(ev_probe.get("name", ""), ev_probe.get("when", ""), title)
                if sig in content_seen:
                    continue
                content_seen.add(sig)
                ev = extract_event(text, title, kind, msg)
                ev["dialog_tg_id"] = ent_id
                events.append(ev)
        except Exception as e:  # noqa: BLE001
            # Xato turi ham yoziladi — aks holda dasturlash xatosi (masalan
            # TypeError) oddiy tarmoq xatosi bilan bir xil ko'rinib, butun
            # skaner jim ishlamay qolgani bilinmay qoladi.
            log.warning("Kanal %s xabarlarini o'qishda xato: %s: %s", title, type(e).__name__, e)
            continue

    # Xronologik tartib: yaqinlashib kelayotgan (yangi) tadbirlar tepada
    events.sort(key=lambda e: e.get("msg_date") or "", reverse=True)

    # AI bilan aniqlashtirish (imkoni bo'lsa) — bepul evristik natijani yaxshilaydi
    refined = await _ai_refine(events, account_id)
    if refined:
        events = refined

    return {
        "events": events,
        "scanned": scanned,
        "folder_title": _folder_title(getattr(folder, "title", "")),
        "days": days,
    }


async def persist_events(
    account_id: int,
    events: list[dict],
    folder_title: str = "",
    days: int = DEFAULT_DAYS,
    folder_id: int | None = None,
    extra_keywords: str | None = None,
) -> None:
    """Topilgan tadbirlarni DB'ga saqlaydi (eski natijalarni almashtiradi).

    Ilova va bot /events buyrug'i bir xil so'nggi natijani ko'rishi uchun.
    Config ham shu yerda yangilanadi (bir marta yoziladi — aralashmaydi).
    """
    from datetime import datetime as _dt
    from datetime import timezone as _tz

    from sqlalchemy import delete, select

    from ..db import EventFolderConfig, EventItem, SessionLocal, utcnow

    def _parse(s: str | None):
        if not s:
            return None
        try:
            dt = _dt.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=_tz.utc)
            return dt
        except Exception:  # noqa: BLE001
            return None

    async with SessionLocal() as db:
        await db.execute(delete(EventItem).where(EventItem.account_id == account_id))
        for ev in events:
            db.add(
                EventItem(
                    account_id=account_id,
                    dialog_tg_id=int(ev.get("dialog_tg_id", 0)),
                    source_title=ev.get("source_title", ""),
                    source_kind=ev.get("source_kind", "channel"),
                    msg_tg_id=int(ev.get("msg_tg_id", 0)),
                    msg_date=_parse(ev.get("msg_date")),
                    name=ev.get("name", "")[:255],
                    purpose=ev.get("purpose", ""),
                    when_=ev.get("when", "")[:255],
                    place=ev.get("place", "")[:255],
                    text=ev.get("text", "")[:2000],
                    by_ai=bool(ev.get("by_ai", False)),
                )
            )
        config = (
            await db.execute(
                select(EventFolderConfig).where(EventFolderConfig.account_id == account_id)
            )
        ).scalar_one_or_none()
        if config is None:
            config = EventFolderConfig(account_id=account_id, days=days, folder_title=folder_title)
            db.add(config)
        else:
            config.days = days
            config.folder_title = folder_title or config.folder_title
        if folder_id is not None:
            config.folder_id = folder_id
        if extra_keywords is not None:
            config.extra_keywords = extra_keywords
        config.last_scan_at = utcnow()
        await db.commit()
