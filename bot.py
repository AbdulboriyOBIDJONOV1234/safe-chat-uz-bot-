"""
SafeChat - kiberfiribgarlikdan himoyalovchi Telegram bot (MVP)

Funksiyalar:
  1. Xavf turini tanlash (belgilari + nima qilish kerak)
  2. Checklist ("Bu firibgarlikmi?" tekshiruvi)
  3. Mini-test (5 ta savol)
  4. Umumiy tavsiyalar
  5. Shubhali holat haqida xabar berish

Ishga tushirish:
  export BOT_TOKEN="BotFather bergan token"
  export ADMIN_ID="sizning Telegram ID raqamingiz"   # ixtiyoriy
  python bot.py
"""

import json
import logging
import os
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO
)
log = logging.getLogger("safechat")

BOT_TOKEN = os.getenv("BOT_TOKEN", "8583804982:AAHny27DL_mKJtK4g0N76lMZpODMbG4VDCI")
ADMIN_ID = os.getenv("ADMIN_ID", "8104665298")
REPORTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports.jsonl")


# ---------------------------------------------T-------------------------
# MA'LUMOTLAR (matnlarni Sabina shu yerda tahrirlashi mumkin)
# ----------------------------------------------------------------------

THREATS = {
    "call": {
        "title": "📞 Soxta qo'ng'iroq",
        "signs": [
            "O'zini bank, militsiya, kredit yoki davlat xodimi deb tanishtiradi",
            "Shoshiltiradi: «hozir qilmasangiz pulingiz yo'qoladi»",
            "Karta raqami, CVV yoki SMS kodni so'raydi",
            "Sizni «xavfsiz hisob»ga pul o'tkazishga undaydi",
        ],
        "actions": [
            "Qo'ng'iroqni darhol tugating",
            "Hech qanday kod yoki karta ma'lumotini aytmang",
            "Bankka o'zingiz rasmiy raqam orqali qo'ng'iroq qilib tekshiring",
            "Raqamni bloklang va xabar bering",
        ],
        "checklist": [
            "Qo'ng'iroq qilgan odam sizga notanishmi?",
            "U sizni shoshiltiryaptimi yoki qo'rqityaptimi?",
            "U karta ma'lumoti yoki SMS kod so'rayaptimi?",
            "U pulni boshqa hisobga o'tkazishni so'rayaptimi?",
        ],
    },
    "phishing": {
        "title": "🎣 Phishing (soxta havola)",
        "signs": [
            "Xabarda g'alati yoki qisqartirilgan havola bor",
            "Havola rasmiy saytga o'xshaydi, lekin manzili boshqacha (masalan, bank0.uz)",
            "«Yutuq yutdingiz», «akkauntingiz bloklanadi» kabi va'dalar yoki qo'rqitish",
            "Login, parol yoki karta ma'lumotini kiritishni so'raydi",
        ],
        "actions": [
            "Havolani bosmang",
            "Agar bosgan bo'lsangiz, hech narsa kiritmang va sahifani yoping",
            "Parol kiritgan bo'lsangiz, darhol o'zgartiring va 2 bosqichli himoyani yoqing",
            "Xabarni yuborgan akkauntni bloklang va shikoyat qiling",
        ],
        "checklist": [
            "Xabarda havola (link) bormi?",
            "Havola manzili rasmiy saytdan farq qiladimi?",
            "Sizga yutuq, mukofot yoki pul va'da qilinyaptimi?",
            "Login, parol yoki karta ma'lumoti so'ralyaptimi?",
        ],
    },
    "file": {
        "title": "📎 Zararli fayl",
        "signs": [
            "Notanish odam kutilmagan fayl yuboradi (.apk, .exe, .zip, .rar)",
            "«Hujjat», «rasm» yoki «chek» deb yuborilgan, lekin kengaytmasi g'alati",
            "Faylni ochish uchun «o'rnatish» yoki ruxsat berish so'raladi",
            "Do'stingiz akkauntidan kelgan, lekin uslubi g'alati xabar bilan",
        ],
        "actions": [
            "Faylni ochmang va o'rnatmang",
            "Do'stingizdan kelgan bo'lsa, boshqa yo'l bilan (qo'ng'iroq) so'rab tasdiqlang",
            "Telefoningizda Play Protect yoki antivirusni ishga tushiring",
            "Fayl yuborgan akkauntni bloklang va shikoyat qiling",
        ],
        "checklist": [
            "Fayl notanish odamdan yoki kutilmaganda keldimi?",
            "Fayl turi .apk, .exe, .zip yoki .rar ga o'xshaydimi?",
            "Fayl «o'rnatish» yoki qo'shimcha ruxsat so'rayaptimi?",
            "Xabar uslubi jo'natuvchining odatiy uslubiga o'xshamayaptimi?",
        ],
    },
    "code": {
        "title": "🔑 Tasdiqlash kodini so'rash",
        "signs": [
            "«Adashib kodni sizga yubordim, qaytarib bering» deydi",
            "Telegram yoki bankdan kelgan SMS kodni so'raydi",
            "Do'stingiz nomidan «pul kerak» yoki «ovoz bering» deb yozadi",
            "Kodni tezda aytishni talab qiladi",
        ],
        "actions": [
            "Tasdiqlash kodini HECH KIMGA bermang, hatto tanish odamga ham",
            "Telegramda: Sozlamalar → Qurilmalar bo'limida begona qurilmalarni o'chiring",
            "Ikki bosqichli tekshiruv (parol) ni yoqing",
            "Suhbatni to'xtating va akkauntni bloklang",
        ],
        "checklist": [
            "Kimdir sizdan SMS yoki Telegram kodini so'rayaptimi?",
            "U «adashib yubordim» yoki shunga o'xshash bahona qilyaptimi?",
            "Xabarni tanishingiz yozgan, lekin uslubi g'alatimi?",
            "Kodni tezroq aytishni talab qilyaptimi?",
        ],
    },
}

QUIZ = [
    {
        "q": "Notanish odam «adashib kod yubordim, qaytaring» dedi. Nima qilasiz?",
        "options": ["Kodni yuboraman", "Kodni bermayman va bloklayman", "Faqat yarmini aytaman"],
        "correct": 1,
        "why": "Tasdiqlash kodi akkauntingiz kaliti. Uni hech kimga bermang.",
    },
    {
        "q": "Xabarda «Yutuq yutdingiz! Havolani bosing» yozilgan. Nima qilasiz?",
        "options": ["Havolani bosaman", "Do'stlarimga yuboraman", "Bosmayman, xabarni o'chirib shikoyat qilaman"],
        "correct": 2,
        "why": "Bunday xabarlar odatda phishing. Havolani bosmang.",
    },
    {
        "q": "Qaysi fayl turi ko'proq xavfli?",
        "options": [".jpg rasm", ".apk o'rnatish fayli", ".txt matn fayli"],
        "correct": 1,
        "why": ".apk faylni notanish odamdan o'rnatish qurilmangizni zararlashi mumkin.",
    },
    {
        "q": "«Bank xodimi» qo'ng'iroq qilib CVV kodni so'radi. To'g'ri harakat?",
        "options": ["Aytaman, chunki bank xodimi", "Qo'ng'iroqni tugatib, bankka o'zim qo'ng'iroq qilaman", "Karta raqamini faqat aytaman"],
        "correct": 1,
        "why": "Haqiqiy bank xodimi hech qachon CVV yoki SMS kodni so'ramaydi.",
    },
    {
        "q": "Akkauntni himoyalashning eng yaxshi usuli qaysi?",
        "options": ["Bir xil parolni hamma joyda ishlatish", "Ikki bosqichli tekshiruvni yoqish", "Parolni do'stga aytib qo'yish"],
        "correct": 1,
        "why": "Ikki bosqichli tekshiruv parol o'g'irlansa ham akkauntni saqlaydi.",
    },
]

GENERAL_TIPS = (
    "💡 <b>Umumiy tavsiyalar</b>\n\n"
    "1. Kod, parol, CVV va karta ma'lumotini hech kimga bermang.\n"
    "2. Notanish havola va fayllarni ochmang.\n"
    "3. Shoshiltirayotgan odamga ishonmang. Firibgarlar doim shoshiltiradi.\n"
    "4. Telegramda ikki bosqichli tekshiruvni yoqing.\n"
    "5. Shubhali bo'lsa, tanishingizga boshqa yo'l bilan (qo'ng'iroq) tasdiqlating.\n"
    "6. Firibgarni bloklang va Telegramga shikoyat qiling.\n"
    "7. Yaqinlaringizga, ayniqsa keksalarga bu qoidalarni aytib qo'ying."
)


# ----------------------------------------------------------------------
# KLAVIATURALAR
# ----------------------------------------------------------------------

def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔍 Xavf turini tanlash", callback_data="threats")],
            [InlineKeyboardButton("✅ Checklist: bu firibgarlikmi?", callback_data="cl_pick")],
            [InlineKeyboardButton("📝 Mini-test", callback_data="quiz_start")],
            [InlineKeyboardButton("💡 Tavsiyalar", callback_data="tips")],
            [InlineKeyboardButton("🚨 Shubhali holat haqida xabar berish", callback_data="report")],
        ]
    )


def back_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Bosh menyu", callback_data="menu")]])


def threat_buttons(prefix: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(v["title"], callback_data=f"{prefix}:{k}")] for k, v in THREATS.items()]
    rows.append([InlineKeyboardButton("⬅️ Bosh menyu", callback_data="menu")])
    return InlineKeyboardMarkup(rows)


WELCOME = (
    "🛡 <b>SafeChat</b> ga xush kelibsiz!\n\n"
    "Men Telegramdagi firibgarlikdan (soxta qo'ng'iroq, phishing, zararli fayl, "
    "kod so'rash) himoyalanishga yordam beraman.\n\n"
    "⚠️ Menga hech qachon parol, karta raqami yoki tasdiqlash kodini yubormang!\n\n"
    "Nima qilamiz?"
)


async def edit(query, text: str, markup: InlineKeyboardMarkup) -> None:
    """Xabarni tahrirlash (bir xil matn bo'lsa xatoni e'tiborsiz qoldirish)."""
    try:
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            raise


# ----------------------------------------------------------------------
# BUYRUQLAR
# ----------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if msg is None or context.user_data is None:
        return
    context.user_data.clear()
    await msg.reply_text(WELCOME, reply_markup=main_menu(), parse_mode=ParseMode.HTML)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if msg is None:
        return
    await msg.reply_text(
        "Buyruqlar:\n/start - bosh menyu\n/help - yordam\n/cancel - amalni bekor qilish",
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if msg is None or context.user_data is None:
        return
    context.user_data.clear()
    await msg.reply_text("Bekor qilindi.", reply_markup=main_menu())


# ----------------------------------------------------------------------
# TUGMALAR (callback)
# ----------------------------------------------------------------------

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or context.user_data is None:
        return
    await query.answer()
    data = query.data or ""
    ud = context.user_data

    # --- Bosh menyu ---
    if data == "menu":
        ud.clear()
        await edit(query, WELCOME, main_menu())

    # --- 1. Xavf turini tanlash ---
    elif data == "threats":
        await edit(query, "🔍 Qaysi xavf turi haqida bilmoqchisiz?", threat_buttons("t"))

    elif data.startswith("t:"):
        t = THREATS[data.split(":")[1]]
        text = f"<b>{t['title']}</b>\n\n<b>Belgilari:</b>\n"
        text += "\n".join(f"• {s}" for s in t["signs"])
        text += "\n\n<b>Nima qilish kerak:</b>\n"
        text += "\n".join(f"✔️ {a}" for a in t["actions"])
        markup = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅ Shu bo'yicha tekshirish", callback_data=f"cl_start:{data.split(':')[1]}")],
                [InlineKeyboardButton("⬅️ Orqaga", callback_data="threats")],
            ]
        )
        await edit(query, text, markup)

    # --- 2. Checklist ---
    elif data == "cl_pick":
        await edit(query, "✅ Qaysi holat bo'yicha tekshiramiz?", threat_buttons("cl_start"))

    elif data.startswith("cl_start:"):
        key = data.split(":")[1]
        ud["cl"] = {"key": key, "i": 0, "yes": 0}
        await ask_checklist(query, ud["cl"])

    elif data.startswith("cl_ans:"):
        state = ud.get("cl")
        if not state:
            await edit(query, "Sessiya tugagan. Qaytadan boshlang.", main_menu())
            return
        if data.endswith(":1"):
            state["yes"] += 1
        state["i"] += 1
        await ask_checklist(query, state)

    # --- 3. Mini-test ---
    elif data == "quiz_start":
        ud["quiz"] = {"i": 0, "score": 0}
        await ask_quiz(query, ud["quiz"])

    elif data.startswith("qa:"):
        state = ud.get("quiz")
        if not state:
            await edit(query, "Sessiya tugagan. Qaytadan boshlang.", main_menu())
            return
        choice = int(data.split(":")[1])
        item = QUIZ[state["i"]]
        if choice == item["correct"]:
            state["score"] += 1
            result = "✅ To'g'ri!"
        else:
            result = f"❌ Noto'g'ri. To'g'ri javob: {item['options'][item['correct']]}"
        state["i"] += 1
        last = state["i"] >= len(QUIZ)
        markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🏁 Natijani ko'rish" if last else "➡️ Keyingi savol", callback_data="quiz_next")]]
        )
        await edit(query, f"{result}\n\n💬 {item['why']}", markup)

    elif data == "quiz_next":
        state = ud.get("quiz")
        if not state:
            await edit(query, "Sessiya tugagan. Qaytadan boshlang.", main_menu())
            return
        await ask_quiz(query, state)

    # --- 4. Tavsiyalar ---
    elif data == "tips":
        await edit(query, GENERAL_TIPS, back_button())

    # --- 5. Xabar berish ---
    elif data == "report":
        ud["awaiting_report"] = True
        await edit(
            query,
            "🚨 <b>Shubhali holat haqida xabar berish</b>\n\n"
            "Nima bo'lganini qisqacha yozib yuboring (kim, qanday xabar yoki havola yubordi).\n\n"
            "⚠️ Parol, karta raqami va tasdiqlash kodini YOZMANG.\n"
            "Bekor qilish uchun /cancel",
            back_button(),
        )


async def ask_checklist(query, state: dict) -> None:
    t = THREATS[state["key"]]
    qs = t["checklist"]
    if state["i"] < len(qs):
        markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Ha", callback_data="cl_ans:1"),
                    InlineKeyboardButton("Yo'q", callback_data="cl_ans:0"),
                ]
            ]
        )
        await edit(query, f"<b>{t['title']}</b>\nSavol {state['i'] + 1}/{len(qs)}\n\n{qs[state['i']]}", markup)
        return

    yes, total = state["yes"], len(qs)
    if yes <= 1:
        verdict = "🟢 <b>Xavf past.</b> Baribir ehtiyot bo'ling va ma'lumot bermang."
    elif yes == 2:
        verdict = "🟡 <b>Xavf o'rtacha.</b> Shubhali holat. Davom etmang va yaqinlaringiz bilan maslahatlashing."
    else:
        verdict = "🔴 <b>Xavf yuqori!</b> Bu firibgarlikka o'xshaydi. Muloqotni to'xtating."
    text = f"{verdict}\n\n(«Ha» javoblar: {yes}/{total})\n\n<b>Tavsiya:</b>\n"
    text += "\n".join(f"✔️ {a}" for a in t["actions"])
    markup = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🚨 Xabar berish", callback_data="report")],
            [InlineKeyboardButton("⬅️ Bosh menyu", callback_data="menu")],
        ]
    )
    await edit(query, text, markup)


async def ask_quiz(query, state: dict) -> None:
    if state["i"] < len(QUIZ):
        item = QUIZ[state["i"]]
        rows = [
            [InlineKeyboardButton(opt, callback_data=f"qa:{idx}")]
            for idx, opt in enumerate(item["options"])
        ]
        await edit(query, f"📝 Savol {state['i'] + 1}/{len(QUIZ)}\n\n<b>{item['q']}</b>", InlineKeyboardMarkup(rows))
        return

    score, total = state["score"], len(QUIZ)
    if score == total:
        comment = "🏆 Ajoyib! Siz firibgarlarga osonlikcha aldanmaysiz."
    elif score >= 3:
        comment = "👍 Yaxshi, lekin tavsiyalarni yana bir bor ko'rib chiqing."
    else:
        comment = "⚠️ Ehtiyot bo'ling! Tavsiyalar bo'limini o'qib chiqing."
    markup = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔁 Qayta topshirish", callback_data="quiz_start")],
            [InlineKeyboardButton("⬅️ Bosh menyu", callback_data="menu")],
        ]
    )
    await edit(query, f"🏁 <b>Natija: {score}/{total}</b>\n\n{comment}", markup)


# ----------------------------------------------------------------------
# XABAR BERISH (oddiy matn)
# ----------------------------------------------------------------------

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    user = update.effective_user
    if msg is None or user is None or context.user_data is None:
        return
    if not context.user_data.get("awaiting_report"):
        await msg.reply_text("Menyudan foydalaning 👇", reply_markup=main_menu())
        return

    text = msg.text or ""
    record = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "user_id": user.id,
        "username": user.username,
        "text": text,
    }
    with open(REPORTS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    log.info("Yangi xabar (report) qabul qilindi: user_id=%s", user.id)

    if ADMIN_ID:
        try:
            await context.bot.send_message(
                chat_id=int(ADMIN_ID),
                text=f"🚨 Yangi shubhali holat\nFoydalanuvchi: @{user.username or user.id}\n\n{text}",
            )
        except Exception as e:  # admin botni hali boshlamagan bo'lishi mumkin
            log.warning("Adminga yuborib bo'lmadi: %s", e)

    context.user_data.pop("awaiting_report", None)
    await msg.reply_text(
        "✅ Rahmat! Xabaringiz qabul qilindi.\n"
        "Iltimos, firibgar akkauntni bloklab, Telegramga shikoyat qiling.",
        reply_markup=main_menu(),
    )


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.error("Xatolik: %s", context.error)


# ----------------------------------------------------------------------
# ISHGA TUSHIRISH
# ----------------------------------------------------------------------

def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN topilmadi. Avval: export BOT_TOKEN='...'")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_error_handler(on_error)

    log.info("SafeChat bot ishga tushdi...")
    app.run_polling()


if __name__ == "__main__":
    main()