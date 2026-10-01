"""
SafeChat - kiberfiribgarlikdan himoyalovchi Telegram bot

Funksiyalar:
  1. Xavf turini tanlash (belgilari + nima qilish kerak)
  2. Checklist ("Bu firibgarlikmi?" tekshiruvi)
  3. Havolani tekshirish (havolani ochmasdan, belgilar bo'yicha)
  4. Real misollar (firibgarlik xabarlariga namunalar)
  5. Mini-test (5 ta savol)
  6. Umumiy tavsiyalar
  7. Shubhali holat haqida xabar berish (spamdan himoya bilan)
  8. Ikki til: o'zbekcha va ruscha (/lang)
  9. /stats - faqat admin uchun statistika

Ishga tushirish:
  export BOT_TOKEN="BotFather bergan token"
  export ADMIN_ID="sizning Telegram ID raqamingiz"   # ixtiyoriy, /stats uchun kerak
  python bot.py
"""

import html
import ipaddress
import json
import logging
import os
import re
import time
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlparse

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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = os.getenv("ADMIN_ID", "")
REPORTS_FILE = os.getenv("REPORTS_FILE", os.path.join(BASE_DIR, "reports.jsonl"))
DATA_FILE = os.getenv("DATA_FILE", os.path.join(BASE_DIR, "data.json"))

DEFAULT_LANG = "uz"
LANGS = ("uz", "ru")

# Spamdan himoya sozlamalari
REPORT_LIMIT, REPORT_WINDOW = 3, 3600      # 1 soatda 3 ta xabar
LINK_LIMIT, LINK_WINDOW = 20, 3600         # 1 soatda 20 ta tekshiruv
REPORT_MAX_LEN = 1000                      # xabar uzunligi (belgi)


# ----------------------------------------------------------------------
# MATNLAR: UI (tugmalar va xabarlar)
# ----------------------------------------------------------------------

UI: dict[str, dict[str, str]] = {
    "uz": {
        "welcome": (
            "🛡 <b>SafeChat</b> ga xush kelibsiz!\n\n"
            "Men Telegramdagi firibgarlikdan (soxta qo'ng'iroq, phishing, zararli fayl, "
            "kod so'rash) himoyalanishga yordam beraman.\n\n"
            "⚠️ Menga hech qachon parol, karta raqami yoki tasdiqlash kodini yubormang!\n\n"
            "Nima qilamiz?"
        ),
        "btn_threats": "🔍 Xavf turini tanlash",
        "btn_checklist": "✅ Checklist: bu firibgarlikmi?",
        "btn_link": "🔗 Havolani tekshirish",
        "btn_examples": "📚 Real misollar",
        "btn_quiz": "📝 Mini-test",
        "btn_tips": "💡 Tavsiyalar",
        "btn_report": "🚨 Shubhali holat haqida xabar berish",
        "btn_lang": "🌐 Til / Язык",
        "btn_menu": "⬅️ Bosh menyu",
        "btn_back": "⬅️ Orqaga",
        "btn_check_this": "✅ Shu bo'yicha tekshirish",
        "btn_report_short": "🚨 Xabar berish",
        "btn_retry": "🔁 Qayta topshirish",
        "btn_next_q": "➡️ Keyingi savol",
        "btn_result": "🏁 Natijani ko'rish",
        "btn_prev": "⬅️ Oldingi",
        "btn_next": "Keyingi ➡️",
        "threats_pick": "🔍 Qaysi xavf turi haqida bilmoqchisiz?",
        "cl_pick": "✅ Qaysi holat bo'yicha tekshiramiz?",
        "signs_h": "Belgilari:",
        "actions_h": "Nima qilish kerak:",
        "recommend_h": "Tavsiya:",
        "question_n": "Savol {i}/{n}",
        "yes": "Ha",
        "no": "Yo'q",
        "session_over": "Sessiya tugagan. Qaytadan boshlang.",
        "verdict_low": "🟢 <b>Xavf past.</b> Baribir ehtiyot bo'ling va ma'lumot bermang.",
        "verdict_mid": "🟡 <b>Xavf o'rtacha.</b> Shubhali holat. Davom etmang va yaqinlaringiz bilan maslahatlashing.",
        "verdict_high": "🔴 <b>Xavf yuqori!</b> Bu firibgarlikka o'xshaydi. Muloqotni to'xtating.",
        "yes_count": "(«Ha» javoblar: {yes}/{total})",
        "quiz_q": "📝 Savol {i}/{n}",
        "right": "✅ To'g'ri!",
        "wrong": "❌ Noto'g'ri. To'g'ri javob: {ans}",
        "quiz_result": "🏁 <b>Natija: {s}/{n}</b>",
        "quiz_top": "🏆 Ajoyib! Siz firibgarlarga osonlikcha aldanmaysiz.",
        "quiz_good": "👍 Yaxshi, lekin tavsiyalarni yana bir bor ko'rib chiqing.",
        "quiz_low": "⚠️ Ehtiyot bo'ling! Tavsiyalar bo'limini o'qib chiqing.",
        "tips": (
            "💡 <b>Umumiy tavsiyalar</b>\n\n"
            "1. Kod, parol, CVV va karta ma'lumotini hech kimga bermang.\n"
            "2. Notanish havola va fayllarni ochmang.\n"
            "3. Shoshiltirayotgan odamga ishonmang. Firibgarlar doim shoshiltiradi.\n"
            "4. Telegramda ikki bosqichli tekshiruvni yoqing.\n"
            "5. Shubhali bo'lsa, tanishingizga boshqa yo'l bilan (qo'ng'iroq) tasdiqlating.\n"
            "6. Firibgarni bloklang va Telegramga shikoyat qiling.\n"
            "7. Yaqinlaringizga, ayniqsa keksalarga bu qoidalarni aytib qo'ying."
        ),
        "report_prompt": (
            "🚨 <b>Shubhali holat haqida xabar berish</b>\n\n"
            "Nima bo'lganini qisqacha yozib yuboring (kim, qanday xabar yoki havola yubordi).\n\n"
            "⚠️ Parol, karta raqami va tasdiqlash kodini YOZMANG.\n"
            "Bekor qilish uchun /cancel"
        ),
        "report_thanks": (
            "✅ Rahmat! Xabaringiz qabul qilindi.\n"
            "Iltimos, firibgar akkauntni bloklab, Telegramga shikoyat qiling."
        ),
        "report_limit": "⏳ Siz juda ko'p xabar yubordingiz. Iltimos, bir ozdan keyin urinib ko'ring.",
        "report_long": "✂️ Xabar juda uzun (eng ko'pi {n} belgi). Iltimos, qisqaroq yozing.",
        "cancelled": "Bekor qilindi.",
        "use_menu": "Menyudan foydalaning 👇",
        "help": (
            "Buyruqlar:\n/start - bosh menyu\n/lang - tilni tanlash\n"
            "/help - yordam\n/cancel - amalni bekor qilish"
        ),
        "lang_pick": "🌐 Tilni tanlang / Выберите язык",
        "lang_set": "✅ Til o'zgartirildi: O'zbekcha",
        "link_prompt": (
            "🔗 <b>Havolani tekshirish</b>\n\n"
            "Shubhali havolani shu yerga yuboring. Men uni <b>ochmayman</b>, faqat manzilidagi "
            "xavf belgilarini tekshiraman.\n\nBekor qilish uchun /cancel"
        ),
        "link_none": "Xabarda havola topilmadi. Havolani to'liq yuboring (masalan: example.com/abc).",
        "link_limit": "⏳ Juda ko'p tekshiruv so'radingiz. Bir ozdan keyin urinib ko'ring.",
        "link_head": "🔗 <b>Havola tekshiruvi</b>",
        "link_domain": "Domen:",
        "link_found": "Topilgan belgilar:",
        "link_low": "🟢 <b>Aniq xavf belgilari topilmadi.</b>",
        "link_mid": "🟡 <b>Shubhali.</b> Havolani ochishdan oldin yaxshilab o'ylab ko'ring.",
        "link_high": "🔴 <b>Xavfli ko'rinadi!</b> Havolani ochmang.",
        "link_note": (
            "ℹ️ Bu tekshiruv faqat manzilga qaraydi. «Xavf yo'q» degani to'liq xavfsizlikni "
            "kafolatlamaydi. Shubhangiz bo'lsa, havolani ochmang."
        ),
        "btn_check_another": "🔗 Yana tekshirish",
        "f_http": "Havola himoyalanmagan (https emas)",
        "f_short": "Qisqartirilgan havola. Haqiqiy manzil yashirilgan",
        "f_ip": "Manzil domen emas, IP raqam",
        "f_at": "Manzilda «@» belgisi bor (aldamchi usul)",
        "f_puny": "Domen g'alati (xn-- belgilar), boshqa harflar bilan yozilgan bo'lishi mumkin",
        "f_subs": "Domen juda ko'p bo'limli (subdomen)",
        "f_brand": "Mashhur nomga o'xshaydi ({brand}), lekin rasmiy sayt emas",
        "f_tld": "Firibgarlar ko'p ishlatadigan domen oxiri",
        "f_words": "Aldov so'zlari bor (yutuq, bonus, tekin, tasdiqlash va h.k.)",
        "f_hyphens": "Domenda ko'p chiziqcha («-») bor",
        "f_digits": "Harflar o'rniga raqam ishlatilgan (masalan: 0, 1)",
        "examples_head": "📚 <b>Real misollar</b> ({i}/{n})",
        "examples_why": "Nima uchun firibgarlik:",
        "stats_head": "📊 <b>Statistika</b>",
        "no_access": "Bu buyruq faqat admin uchun.",
    },
    "ru": {
        "welcome": (
            "🛡 Добро пожаловать в <b>SafeChat</b>!\n\n"
            "Я помогаю защититься от мошенничества в Telegram (поддельные звонки, фишинг, "
            "вредоносные файлы, выманивание кодов).\n\n"
            "⚠️ Никогда не присылайте мне пароли, номера карт и коды подтверждения!\n\n"
            "Что будем делать?"
        ),
        "btn_threats": "🔍 Выбрать вид угрозы",
        "btn_checklist": "✅ Чек-лист: это мошенничество?",
        "btn_link": "🔗 Проверить ссылку",
        "btn_examples": "📚 Реальные примеры",
        "btn_quiz": "📝 Мини-тест",
        "btn_tips": "💡 Советы",
        "btn_report": "🚨 Сообщить о подозрительном случае",
        "btn_lang": "🌐 Til / Язык",
        "btn_menu": "⬅️ Главное меню",
        "btn_back": "⬅️ Назад",
        "btn_check_this": "✅ Проверить по этому виду",
        "btn_report_short": "🚨 Сообщить",
        "btn_retry": "🔁 Пройти заново",
        "btn_next_q": "➡️ Следующий вопрос",
        "btn_result": "🏁 Посмотреть результат",
        "btn_prev": "⬅️ Предыдущий",
        "btn_next": "Следующий ➡️",
        "threats_pick": "🔍 О какой угрозе хотите узнать?",
        "cl_pick": "✅ По какому случаю проверяем?",
        "signs_h": "Признаки:",
        "actions_h": "Что делать:",
        "recommend_h": "Рекомендация:",
        "question_n": "Вопрос {i}/{n}",
        "yes": "Да",
        "no": "Нет",
        "session_over": "Сессия завершена. Начните заново.",
        "verdict_low": "🟢 <b>Риск низкий.</b> Всё равно будьте осторожны и не передавайте данные.",
        "verdict_mid": "🟡 <b>Риск средний.</b> Ситуация подозрительная. Не продолжайте и посоветуйтесь с близкими.",
        "verdict_high": "🔴 <b>Риск высокий!</b> Это похоже на мошенничество. Прекратите общение.",
        "yes_count": "(Ответов «Да»: {yes}/{total})",
        "quiz_q": "📝 Вопрос {i}/{n}",
        "right": "✅ Верно!",
        "wrong": "❌ Неверно. Правильный ответ: {ans}",
        "quiz_result": "🏁 <b>Результат: {s}/{n}</b>",
        "quiz_top": "🏆 Отлично! Мошенникам вас не обмануть.",
        "quiz_good": "👍 Хорошо, но перечитайте советы ещё раз.",
        "quiz_low": "⚠️ Будьте осторожны! Прочитайте раздел с советами.",
        "tips": (
            "💡 <b>Общие советы</b>\n\n"
            "1. Никому не сообщайте коды, пароли, CVV и данные карты.\n"
            "2. Не открывайте незнакомые ссылки и файлы.\n"
            "3. Не доверяйте тому, кто торопит. Мошенники всегда торопят.\n"
            "4. Включите двухэтапную проверку в Telegram.\n"
            "5. Если сомневаетесь, подтвердите у знакомого другим способом (звонком).\n"
            "6. Заблокируйте мошенника и пожалуйтесь в Telegram.\n"
            "7. Расскажите эти правила близким, особенно пожилым."
        ),
        "report_prompt": (
            "🚨 <b>Сообщить о подозрительном случае</b>\n\n"
            "Кратко опишите, что произошло (кто и какое сообщение или ссылку прислал).\n\n"
            "⚠️ НЕ пишите пароли, номера карт и коды подтверждения.\n"
            "Для отмены: /cancel"
        ),
        "report_thanks": (
            "✅ Спасибо! Ваше сообщение принято.\n"
            "Пожалуйста, заблокируйте аккаунт мошенника и пожалуйтесь в Telegram."
        ),
        "report_limit": "⏳ Вы отправили слишком много сообщений. Попробуйте чуть позже.",
        "report_long": "✂️ Сообщение слишком длинное (максимум {n} символов). Напишите короче.",
        "cancelled": "Отменено.",
        "use_menu": "Пользуйтесь меню 👇",
        "help": (
            "Команды:\n/start - главное меню\n/lang - выбор языка\n"
            "/help - помощь\n/cancel - отмена действия"
        ),
        "lang_pick": "🌐 Tilni tanlang / Выберите язык",
        "lang_set": "✅ Язык изменён: Русский",
        "link_prompt": (
            "🔗 <b>Проверка ссылки</b>\n\n"
            "Пришлите сюда подозрительную ссылку. Я её <b>не открываю</b>, а только проверяю "
            "признаки опасности в самом адресе.\n\nДля отмены: /cancel"
        ),
        "link_none": "Ссылка в сообщении не найдена. Пришлите её полностью (например: example.com/abc).",
        "link_limit": "⏳ Слишком много проверок. Попробуйте чуть позже.",
        "link_head": "🔗 <b>Проверка ссылки</b>",
        "link_domain": "Домен:",
        "link_found": "Найденные признаки:",
        "link_low": "🟢 <b>Явных признаков опасности не найдено.</b>",
        "link_mid": "🟡 <b>Подозрительно.</b> Хорошо подумайте, прежде чем открывать ссылку.",
        "link_high": "🔴 <b>Выглядит опасно!</b> Не открывайте ссылку.",
        "link_note": (
            "ℹ️ Проверка смотрит только на адрес. «Опасности нет» не гарантирует полной "
            "безопасности. Если сомневаетесь, не открывайте ссылку."
        ),
        "btn_check_another": "🔗 Проверить ещё",
        "f_http": "Ссылка не защищена (не https)",
        "f_short": "Сокращённая ссылка. Настоящий адрес скрыт",
        "f_ip": "Вместо домена указан IP-адрес",
        "f_at": "В адресе есть знак «@» (обманный приём)",
        "f_puny": "Странный домен (символы xn--), возможна подмена букв",
        "f_subs": "У домена слишком много уровней (поддоменов)",
        "f_brand": "Похоже на известное название ({brand}), но это не официальный сайт",
        "f_tld": "Окончание домена, которое часто используют мошенники",
        "f_words": "Есть приманки (выигрыш, бонус, бесплатно, подтверждение и т.п.)",
        "f_hyphens": "В домене много дефисов («-»)",
        "f_digits": "Вместо букв использованы цифры (например: 0, 1)",
        "examples_head": "📚 <b>Реальные примеры</b> ({i}/{n})",
        "examples_why": "Почему это мошенничество:",
        "stats_head": "📊 <b>Статистика</b>",
        "no_access": "Эта команда только для администратора.",
    },
}


# ----------------------------------------------------------------------
# MATNLAR: xavf turlari (Sabina shu yerda tahrirlashi mumkin)
# ----------------------------------------------------------------------

THREATS: dict[str, dict[str, dict[str, Any]]] = {
    "call": {
        "uz": {
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
        "ru": {
            "title": "📞 Поддельный звонок",
            "signs": [
                "Представляется сотрудником банка, полиции или госоргана",
                "Торопит: «если не сделаете сейчас, потеряете деньги»",
                "Просит номер карты, CVV или SMS-код",
                "Убеждает перевести деньги на «безопасный счёт»",
            ],
            "actions": [
                "Сразу завершите разговор",
                "Никому не называйте коды и данные карты",
                "Перезвоните в банк сами по официальному номеру",
                "Заблокируйте номер и сообщите о нём",
            ],
            "checklist": [
                "Звонит незнакомый вам человек?",
                "Вас торопят или пугают?",
                "Просят данные карты или SMS-код?",
                "Просят перевести деньги на другой счёт?",
            ],
        },
    },
    "phishing": {
        "uz": {
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
        "ru": {
            "title": "🎣 Фишинг (поддельная ссылка)",
            "signs": [
                "В сообщении странная или сокращённая ссылка",
                "Ссылка похожа на официальный сайт, но адрес другой (например, bank0.uz)",
                "Обещания вроде «вы выиграли» или угрозы «аккаунт будет заблокирован»",
                "Просят ввести логин, пароль или данные карты",
            ],
            "actions": [
                "Не нажимайте на ссылку",
                "Если нажали, ничего не вводите и закройте страницу",
                "Если ввели пароль, срочно смените его и включите двухэтапную защиту",
                "Заблокируйте отправителя и пожалуйтесь на него",
            ],
            "checklist": [
                "В сообщении есть ссылка?",
                "Адрес ссылки отличается от официального сайта?",
                "Вам обещают выигрыш, приз или деньги?",
                "Просят логин, пароль или данные карты?",
            ],
        },
    },
    "file": {
        "uz": {
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
        "ru": {
            "title": "📎 Вредоносный файл",
            "signs": [
                "Незнакомец неожиданно присылает файл (.apk, .exe, .zip, .rar)",
                "Файл назван «документ», «фото» или «чек», но расширение странное",
                "Для открытия файла просят «установить» или дать разрешения",
                "Файл пришёл от друга, но сообщение написано необычно",
            ],
            "actions": [
                "Не открывайте и не устанавливайте файл",
                "Если файл от друга, подтвердите другим способом (звонком)",
                "Запустите Play Protect или антивирус на телефоне",
                "Заблокируйте отправителя и пожалуйтесь на него",
            ],
            "checklist": [
                "Файл пришёл от незнакомого или неожиданно?",
                "Тип файла похож на .apk, .exe, .zip или .rar?",
                "Файл просит «установить» или дополнительные разрешения?",
                "Стиль сообщения не похож на обычный стиль отправителя?",
            ],
        },
    },
    "code": {
        "uz": {
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
        "ru": {
            "title": "🔑 Выманивание кода подтверждения",
            "signs": [
                "Говорит: «я ошибочно отправил вам код, верните»",
                "Просит SMS-код от Telegram или банка",
                "Пишет от имени друга: «нужны деньги» или «проголосуй за меня»",
                "Требует назвать код как можно быстрее",
            ],
            "actions": [
                "НИКОМУ не называйте код подтверждения, даже знакомым",
                "В Telegram: Настройки → Устройства, завершите сеансы чужих устройств",
                "Включите двухэтапную проверку (пароль)",
                "Прекратите разговор и заблокируйте аккаунт",
            ],
            "checklist": [
                "Кто-то просит у вас SMS-код или код Telegram?",
                "Он ссылается на «ошибочно отправил» или похожую причину?",
                "Сообщение от знакомого, но написано необычно?",
                "Требует назвать код побыстрее?",
            ],
        },
    },
}


# ----------------------------------------------------------------------
# MATNLAR: mini-test
# ----------------------------------------------------------------------

QUIZ: list[dict[str, Any]] = [
    {
        "correct": 1,
        "uz": {
            "q": "Notanish odam «adashib kod yubordim, qaytaring» dedi. Nima qilasiz?",
            "options": ["Kodni yuboraman", "Kodni bermayman va bloklayman", "Faqat yarmini aytaman"],
            "why": "Tasdiqlash kodi akkauntingiz kaliti. Uni hech kimga bermang.",
        },
        "ru": {
            "q": "Незнакомец написал: «я ошибочно отправил код, верните». Что вы сделаете?",
            "options": ["Отправлю код", "Не дам код и заблокирую", "Назову только половину"],
            "why": "Код подтверждения это ключ от вашего аккаунта. Никому его не давайте.",
        },
    },
    {
        "correct": 2,
        "uz": {
            "q": "Xabarda «Yutuq yutdingiz! Havolani bosing» yozilgan. Nima qilasiz?",
            "options": ["Havolani bosaman", "Do'stlarimga yuboraman", "Bosmayman, xabarni o'chirib shikoyat qilaman"],
            "why": "Bunday xabarlar odatda phishing. Havolani bosmang.",
        },
        "ru": {
            "q": "В сообщении написано: «Вы выиграли! Нажмите на ссылку». Что вы сделаете?",
            "options": ["Нажму на ссылку", "Перешлю друзьям", "Не нажму, удалю и пожалуюсь"],
            "why": "Такие сообщения обычно фишинг. Не нажимайте на ссылку.",
        },
    },
    {
        "correct": 1,
        "uz": {
            "q": "Qaysi fayl turi ko'proq xavfli?",
            "options": [".jpg rasm", ".apk o'rnatish fayli", ".txt matn fayli"],
            "why": ".apk faylni notanish odamdan o'rnatish qurilmangizni zararlashi mumkin.",
        },
        "ru": {
            "q": "Какой тип файла опаснее всего?",
            "options": ["Фото .jpg", "Установочный файл .apk", "Текстовый файл .txt"],
            "why": "Установка .apk от незнакомца может заразить ваше устройство.",
        },
    },
    {
        "correct": 1,
        "uz": {
            "q": "«Bank xodimi» qo'ng'iroq qilib CVV kodni so'radi. To'g'ri harakat?",
            "options": ["Aytaman, chunki bank xodimi", "Qo'ng'iroqni tugatib, bankka o'zim qo'ng'iroq qilaman", "Karta raqamini faqat aytaman"],
            "why": "Haqiqiy bank xodimi hech qachon CVV yoki SMS kodni so'ramaydi.",
        },
        "ru": {
            "q": "«Сотрудник банка» позвонил и попросил CVV-код. Как поступить?",
            "options": ["Назову, ведь он из банка", "Завершу звонок и сам позвоню в банк", "Назову только номер карты"],
            "why": "Настоящий сотрудник банка никогда не спрашивает CVV или SMS-код.",
        },
    },
    {
        "correct": 1,
        "uz": {
            "q": "Akkauntni himoyalashning eng yaxshi usuli qaysi?",
            "options": ["Bir xil parolni hamma joyda ishlatish", "Ikki bosqichli tekshiruvni yoqish", "Parolni do'stga aytib qo'yish"],
            "why": "Ikki bosqichli tekshiruv parol o'g'irlansa ham akkauntni saqlaydi.",
        },
        "ru": {
            "q": "Какой способ лучше всего защищает аккаунт?",
            "options": ["Один пароль везде", "Включить двухэтапную проверку", "Сказать пароль другу"],
            "why": "Двухэтапная проверка защитит аккаунт, даже если пароль украдут.",
        },
    },
]


# ----------------------------------------------------------------------
# MATNLAR: real misollar (barcha ismlar va raqamlar to'qima)
# ----------------------------------------------------------------------

EXAMPLES: dict[str, list[dict[str, Any]]] = {
    "uz": [
        {
            "title": "Soxta bank qo'ng'irog'i",
            "text": "«Assalomu alaykum, men bank xavfsizlik xodimiman. Kartangizdan shubhali o'tkazma bo'ldi. Pulingizni saqlab qolish uchun SMS kodni ayting.»",
            "why": ["Bank xodimi hech qachon SMS kodni so'ramaydi", "Qo'rqitib shoshiltiradi", "Maqsad: kod orqali kartadan pul yechish"],
        },
        {
            "title": "«Do'stingiz» nomidan xabar",
            "text": "«Salom, kartamga pul tushmay qoldi, 200 ming qarz bera olasanmi? Qaytarib beraman. Mana karta raqami...»",
            "why": ["Do'stingizning akkaunti buzilgan bo'lishi mumkin", "Pul so'rash va shoshiltirish belgisi", "Do'stingizga qo'ng'iroq qilib tasdiqlang"],
        },
        {
            "title": "Yutuq haqida xabar",
            "text": "«Tabriklaymiz! Siz 5 000 000 so'm yutdingiz. Olish uchun havolani bosing: payme-bonus.xyz»",
            "why": ["Qatnashmagan o'yinda yutuq bo'lmaydi", "Rasmiy bo'lmagan domen (.xyz)", "Havolada karta ma'lumoti so'raladi"],
        },
        {
            "title": "Zararli .apk fayl",
            "text": "«To'y rasmlari 😍 Mana ko'ring!» (fayl: rasmlar.apk)",
            "why": ["Rasm .apk bo'lmaydi, bu o'rnatish fayli", "Notanish yoki g'alati uslubdagi jo'natuvchi", "O'rnatilsa, telefonni nazorat qilib olishi mumkin"],
        },
        {
            "title": "«Adashib kod yubordim»",
            "text": "«Salom, adashib sizning raqamingizga kod yuboribman, tezroq aytib yuboring, juda kerak.»",
            "why": ["Bu sizning akkauntingizga kirish kodi", "Shoshiltirish va iltimos qilish usuli", "Kodni bersangiz, akkaunt egallab olinadi"],
        },
    ],
    "ru": [
        {
            "title": "Поддельный звонок из банка",
            "text": "«Здравствуйте, я сотрудник службы безопасности банка. С вашей карты прошла подозрительная операция. Чтобы сохранить деньги, назовите SMS-код.»",
            "why": ["Сотрудник банка никогда не просит SMS-код", "Пугает и торопит", "Цель: снять деньги с карты с помощью кода"],
        },
        {
            "title": "Сообщение от «друга»",
            "text": "«Привет, у меня не пришли деньги на карту, можешь одолжить 200 тысяч? Верну. Вот номер карты...»",
            "why": ["Аккаунт друга мог быть взломан", "Просьба о деньгах и спешка это признак обмана", "Позвоните другу и подтвердите"],
        },
        {
            "title": "Сообщение о выигрыше",
            "text": "«Поздравляем! Вы выиграли 5 000 000 сум. Чтобы получить, нажмите на ссылку: payme-bonus.xyz»",
            "why": ["В розыгрыше, где вы не участвовали, выигрыша не бывает", "Неофициальный домен (.xyz)", "На ссылке просят данные карты"],
        },
        {
            "title": "Вредоносный .apk файл",
            "text": "«Фото со свадьбы 😍 Смотри!» (файл: foto.apk)",
            "why": ["Фото не бывает .apk, это установочный файл", "Незнакомый отправитель или необычный стиль", "После установки телефоном могут управлять"],
        },
        {
            "title": "«Ошибочно отправил код»",
            "text": "«Привет, я по ошибке отправил код на твой номер, скорее назови его, очень нужно.»",
            "why": ["Это код для входа в ваш аккаунт", "Приём: спешка и просьба", "Если назовёте код, аккаунт захватят"],
        },
    ],
}


# ----------------------------------------------------------------------
# MA'LUMOTLAR OMBORI (foydalanuvchi tili va statistika)
# Faqat Telegram ID, til va sanalar saqlanadi. Ism, telefon saqlanmaydi.
# ----------------------------------------------------------------------

DATA: dict[str, Any] = {"users": {}, "counters": {}}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def load_data() -> None:
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            loaded = json.load(f)
        DATA["users"] = loaded.get("users", {})
        DATA["counters"] = loaded.get("counters", {})
    except FileNotFoundError:
        pass
    except Exception as e:
        log.warning("data.json o'qib bo'lmadi: %s", e)


def save_data() -> None:
    tmp = DATA_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(DATA, f, ensure_ascii=False)
        os.replace(tmp, DATA_FILE)
    except Exception as e:
        log.warning("data.json yozib bo'lmadi: %s", e)


def is_known_user(user_id: int) -> bool:
    return str(user_id) in DATA["users"]


def touch_user(user_id: int) -> None:
    uid = str(user_id)
    if uid not in DATA["users"]:
        DATA["users"][uid] = {"lang": DEFAULT_LANG, "first": now_iso(), "last": now_iso()}
        save_data()
    else:
        DATA["users"][uid]["last"] = now_iso()


def get_lang(user_id: int) -> str:
    return DATA["users"].get(str(user_id), {}).get("lang", DEFAULT_LANG)


def set_lang(user_id: int, lang: str) -> None:
    touch_user(user_id)
    DATA["users"][str(user_id)]["lang"] = lang
    save_data()


def bump(counter: str) -> None:
    DATA["counters"][counter] = DATA["counters"].get(counter, 0) + 1
    save_data()


# ----------------------------------------------------------------------
# SPAMDAN HIMOYA
# ----------------------------------------------------------------------

_hits: dict[tuple[int, str], list[float]] = {}


def rate_ok(user_id: int, key: str, limit: int, window: int) -> bool:
    """True qaytarsa, ruxsat bor. Oynada limitdan ko'p bo'lsa, False."""
    now = time.time()
    recent = [t for t in _hits.get((user_id, key), []) if now - t < window]
    if len(recent) >= limit:
        _hits[(user_id, key)] = recent
        return False
    recent.append(now)
    _hits[(user_id, key)] = recent
    return True


# ----------------------------------------------------------------------
# HAVOLANI TEKSHIRISH (havola ochilmaydi, faqat matn tahlil qilinadi)
# ----------------------------------------------------------------------

URL_RE = re.compile(
    r"(?:https?://|www\.)[^\s<>\"']+|\b[a-z0-9-]+(?:\.[a-z0-9-]+)+(?:/[^\s<>\"']*)?",
    re.IGNORECASE,
)
SHORTENERS = {
    "bit.ly", "t.ly", "tinyurl.com", "cutt.ly", "goo.gl", "is.gd", "rb.gy",
    "ow.ly", "shorturl.at", "tiny.cc", "clck.ru", "vk.cc", "u.to",
}
RISKY_TLDS = {
    "xyz", "top", "click", "tk", "ml", "ga", "cf", "gq", "icu", "buzz",
    "monster", "rest", "cyou", "sbs", "cfd",
}
SCAM_WORDS = (
    "prize", "gift", "bonus", "free", "claim", "verify", "secure", "update", "login",
    "yutuq", "sovrin", "tekin", "aksiya", "akciya", "podarok", "vyigr", "promo",
)
BRANDS: dict[str, tuple[str, ...]] = {
    "telegram": ("telegram.org", "t.me", "telegram.me", "telegram.dog"),
    "payme": ("payme.uz",),
    "uzum": ("uzum.uz", "uzum.com"),
    "uzcard": ("uzcard.uz",),
    "paynet": ("paynet.uz",),
    "humocard": ("humocard.uz",),
    "instagram": ("instagram.com",),
    "facebook": ("facebook.com",),
    "google": ("google.com",),
}
SECOND_LEVELS = {"com", "org", "net", "gov", "edu", "co"}


def registered_domain(host: str) -> str:
    labels = host.split(".")
    if len(labels) >= 3 and labels[-2] in SECOND_LEVELS and len(labels[-1]) == 2:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def find_url(text: str) -> str | None:
    m = URL_RE.search(text)
    if not m:
        return None
    return m.group(0).rstrip(".,;:!?)»\"'")


def analyze_url(raw: str) -> tuple[int, list[tuple[str, dict[str, str]]], str]:
    """(ball, topilgan belgilar [(kalit, parametrlar)], domen) qaytaradi."""
    had_scheme = bool(re.match(r"^https?://", raw, re.IGNORECASE))
    url = raw if had_scheme else "http://" + raw
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
    except ValueError:
        host = ""
    findings: list[tuple[str, dict[str, str]]] = []
    score = 0

    def add(key: str, points: int, **kw: str) -> None:
        nonlocal score
        findings.append((key, kw))
        score += points

    if had_scheme and url.lower().startswith("http://"):
        add("f_http", 1)

    is_ip = False
    try:
        ipaddress.ip_address(host)
        is_ip = True
    except ValueError:
        pass

    if is_ip:
        add("f_ip", 3)
    elif host:
        reg = registered_domain(host)
        if host in SHORTENERS or reg in SHORTENERS:
            add("f_short", 2)
        if "xn--" in host or any(ord(ch) > 127 for ch in host):
            add("f_puny", 2)
        if len(host.split(".")) >= 5:
            add("f_subs", 1)
        for brand, officials in BRANDS.items():
            if brand in host and not any(host == o or host.endswith("." + o) for o in officials):
                add("f_brand", 3, brand=brand)
                break
        if host.rsplit(".", 1)[-1] in RISKY_TLDS:
            add("f_tld", 1)
        if host.count("-") >= 2:
            add("f_hyphens", 1)
        if re.search(r"[a-z][01]([a-z]|$)", reg.split(".")[0]):
            add("f_digits", 1)

    if "@" in raw.split("?")[0].split("//")[-1].split("/")[0]:
        add("f_at", 2)
    if any(w in raw.lower() for w in SCAM_WORDS):
        add("f_words", 1)

    return score, findings, host


def link_report(raw: str, lang: str) -> str:
    score, findings, host = analyze_url(raw)
    ui = UI[lang]
    verdict = ui["link_low"] if score <= 1 else ui["link_mid"] if score <= 3 else ui["link_high"]
    shown = html.escape(raw if len(raw) <= 80 else raw[:77] + "...")
    lines = [ui["link_head"], "", f"<code>{shown}</code>"]
    if host:
        lines.append(f"{ui['link_domain']} <code>{html.escape(host)}</code>")
    lines += ["", verdict]
    if findings:
        lines += ["", f"<b>{ui['link_found']}</b>"]
        for key, kw in findings:
            lines.append("• " + ui[key].format(**kw))
    lines += ["", ui["link_note"]]
    return "\n".join(lines)


# ----------------------------------------------------------------------
# KLAVIATURALAR
# ----------------------------------------------------------------------

def main_menu(lang: str) -> InlineKeyboardMarkup:
    u = UI[lang]
    rows = [
        [InlineKeyboardButton(u["btn_threats"], callback_data="threats")],
        [InlineKeyboardButton(u["btn_checklist"], callback_data="cl_pick")],
        [InlineKeyboardButton(u["btn_link"], callback_data="link")],
        [InlineKeyboardButton(u["btn_examples"], callback_data="ex:0")],
        [InlineKeyboardButton(u["btn_quiz"], callback_data="quiz_start")],
        [InlineKeyboardButton(u["btn_tips"], callback_data="tips")],
        [InlineKeyboardButton(u["btn_report"], callback_data="report")],
        [InlineKeyboardButton(u["btn_lang"], callback_data="lang")],
    ]
    return InlineKeyboardMarkup(rows)


def back_button(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(UI[lang]["btn_menu"], callback_data="menu")]])


def threat_buttons(lang: str, prefix: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(v[lang]["title"], callback_data=f"{prefix}:{k}")]
        for k, v in THREATS.items()
    ]
    rows.append([InlineKeyboardButton(UI[lang]["btn_menu"], callback_data="menu")])
    return InlineKeyboardMarkup(rows)


def lang_buttons() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🇺🇿 O'zbekcha", callback_data="setlang:uz"),
                InlineKeyboardButton("🇷🇺 Русский", callback_data="setlang:ru"),
            ]
        ]
    )


async def edit(query: Any, text: str, markup: InlineKeyboardMarkup) -> None:
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
    msg, user = update.message, update.effective_user
    if msg is None or user is None or context.user_data is None:
        return
    context.user_data.clear()
    new_user = not is_known_user(user.id)
    touch_user(user.id)
    if new_user:
        bump("starts")
        await msg.reply_text(UI[DEFAULT_LANG]["lang_pick"], reply_markup=lang_buttons())
        return
    lang = get_lang(user.id)
    await msg.reply_text(UI[lang]["welcome"], reply_markup=main_menu(lang), parse_mode=ParseMode.HTML)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg, user = update.message, update.effective_user
    if msg is None or user is None:
        return
    await msg.reply_text(UI[get_lang(user.id)]["help"])


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg, user = update.message, update.effective_user
    if msg is None or user is None or context.user_data is None:
        return
    context.user_data.clear()
    lang = get_lang(user.id)
    await msg.reply_text(UI[lang]["cancelled"], reply_markup=main_menu(lang))


async def lang_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if msg is None:
        return
    await msg.reply_text(UI[DEFAULT_LANG]["lang_pick"], reply_markup=lang_buttons())


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg, user = update.message, update.effective_user
    if msg is None or user is None:
        return
    lang = get_lang(user.id)
    if not ADMIN_ID or str(user.id) != ADMIN_ID:
        await msg.reply_text(UI[lang]["no_access"])
        return
    users = DATA["users"]
    day_ago = (datetime.now() - timedelta(days=1)).isoformat(timespec="seconds")
    active = sum(1 for u in users.values() if u.get("last", "") >= day_ago)
    uz = sum(1 for u in users.values() if u.get("lang") == "uz")
    ru = sum(1 for u in users.values() if u.get("lang") == "ru")
    c = DATA["counters"]
    text = (
        f"{UI[lang]['stats_head']}\n\n"
        f"👥 Foydalanuvchilar / Users: {len(users)}\n"
        f"🟢 24 soat ichida faol / Active 24h: {active}\n"
        f"🌐 uz: {uz} | ru: {ru}\n\n"
        f"✅ Checklist: {c.get('checklists', 0)}\n"
        f"📝 Mini-test: {c.get('quizzes', 0)}\n"
        f"🔗 Havola tekshiruvi / Link checks: {c.get('link_checks', 0)}\n"
        f"🚨 Xabarlar / Reports: {c.get('reports', 0)}"
    )
    await msg.reply_text(text, parse_mode=ParseMode.HTML)


# ----------------------------------------------------------------------
# TUGMALAR (callback)
# ----------------------------------------------------------------------

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query, user = update.callback_query, update.effective_user
    if query is None or user is None or context.user_data is None:
        return
    await query.answer()
    data = query.data or ""
    ud = context.user_data
    touch_user(user.id)

    # --- Til tanlash ---
    if data == "lang":
        await edit(query, UI[DEFAULT_LANG]["lang_pick"], lang_buttons())
        return
    if data.startswith("setlang:"):
        new_lang = data.split(":")[1]
        if new_lang not in LANGS:
            return
        set_lang(user.id, new_lang)
        ud.clear()
        await edit(query, UI[new_lang]["welcome"], main_menu(new_lang))
        return

    lang = get_lang(user.id)
    ui = UI[lang]

    # --- Bosh menyu ---
    if data == "menu":
        ud.clear()
        await edit(query, ui["welcome"], main_menu(lang))

    # --- 1. Xavf turini tanlash ---
    elif data == "threats":
        await edit(query, ui["threats_pick"], threat_buttons(lang, "t"))

    elif data.startswith("t:"):
        key = data.split(":")[1]
        t = THREATS[key][lang]
        text = f"<b>{t['title']}</b>\n\n<b>{ui['signs_h']}</b>\n"
        text += "\n".join(f"• {s}" for s in t["signs"])
        text += f"\n\n<b>{ui['actions_h']}</b>\n"
        text += "\n".join(f"✔️ {a}" for a in t["actions"])
        markup = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(ui["btn_check_this"], callback_data=f"cl_start:{key}")],
                [InlineKeyboardButton(ui["btn_back"], callback_data="threats")],
            ]
        )
        await edit(query, text, markup)

    # --- 2. Checklist ---
    elif data == "cl_pick":
        await edit(query, ui["cl_pick"], threat_buttons(lang, "cl_start"))

    elif data.startswith("cl_start:"):
        key = data.split(":")[1]
        ud["cl"] = {"key": key, "i": 0, "yes": 0}
        await ask_checklist(query, ud["cl"], lang)

    elif data.startswith("cl_ans:"):
        state = ud.get("cl")
        if not state:
            await edit(query, ui["session_over"], main_menu(lang))
            return
        if data.endswith(":1"):
            state["yes"] += 1
        state["i"] += 1
        await ask_checklist(query, state, lang)

    # --- 3. Havolani tekshirish ---
    elif data == "link":
        ud.clear()
        ud["awaiting_link"] = True
        await edit(query, ui["link_prompt"], back_button(lang))

    # --- 4. Real misollar ---
    elif data.startswith("ex:"):
        items = EXAMPLES[lang]
        i = max(0, min(int(data.split(":")[1]), len(items) - 1))
        ex = items[i]
        text = f"{ui['examples_head'].format(i=i + 1, n=len(items))}\n\n<b>{ex['title']}</b>\n\n"
        text += f"<i>{ex['text']}</i>\n\n<b>{ui['examples_why']}</b>\n"
        text += "\n".join(f"• {w}" for w in ex["why"])
        nav = []
        if i > 0:
            nav.append(InlineKeyboardButton(ui["btn_prev"], callback_data=f"ex:{i - 1}"))
        if i < len(items) - 1:
            nav.append(InlineKeyboardButton(ui["btn_next"], callback_data=f"ex:{i + 1}"))
        rows = ([nav] if nav else []) + [[InlineKeyboardButton(ui["btn_menu"], callback_data="menu")]]
        await edit(query, text, InlineKeyboardMarkup(rows))

    # --- 5. Mini-test ---
    elif data == "quiz_start":
        ud["quiz"] = {"i": 0, "score": 0}
        await ask_quiz(query, ud["quiz"], lang)

    elif data.startswith("qa:"):
        state = ud.get("quiz")
        if not state or state["i"] >= len(QUIZ):
            await edit(query, ui["session_over"], main_menu(lang))
            return
        choice = int(data.split(":")[1])
        item = QUIZ[state["i"]]
        q = item[lang]
        if choice == item["correct"]:
            state["score"] += 1
            result = ui["right"]
        else:
            result = ui["wrong"].format(ans=q["options"][item["correct"]])
        state["i"] += 1
        last = state["i"] >= len(QUIZ)
        markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton(ui["btn_result"] if last else ui["btn_next_q"], callback_data="quiz_next")]]
        )
        await edit(query, f"{result}\n\n💬 {q['why']}", markup)

    elif data == "quiz_next":
        state = ud.get("quiz")
        if not state:
            await edit(query, ui["session_over"], main_menu(lang))
            return
        await ask_quiz(query, state, lang)

    # --- 6. Tavsiyalar ---
    elif data == "tips":
        await edit(query, ui["tips"], back_button(lang))

    # --- 7. Xabar berish ---
    elif data == "report":
        ud.clear()
        ud["awaiting_report"] = True
        await edit(query, ui["report_prompt"], back_button(lang))


async def ask_checklist(query: Any, state: dict, lang: str) -> None:
    ui = UI[lang]
    t = THREATS[state["key"]][lang]
    qs = t["checklist"]
    if state["i"] < len(qs):
        markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(ui["yes"], callback_data="cl_ans:1"),
                    InlineKeyboardButton(ui["no"], callback_data="cl_ans:0"),
                ]
            ]
        )
        head = ui["question_n"].format(i=state["i"] + 1, n=len(qs))
        await edit(query, f"<b>{t['title']}</b>\n{head}\n\n{qs[state['i']]}", markup)
        return

    yes, total = state["yes"], len(qs)
    if state.get("counted") is None:
        state["counted"] = True
        bump("checklists")
    if yes <= 1:
        verdict = ui["verdict_low"]
    elif yes == 2:
        verdict = ui["verdict_mid"]
    else:
        verdict = ui["verdict_high"]
    text = f"{verdict}\n\n{ui['yes_count'].format(yes=yes, total=total)}\n\n<b>{ui['recommend_h']}</b>\n"
    text += "\n".join(f"✔️ {a}" for a in t["actions"])
    markup = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(ui["btn_report_short"], callback_data="report")],
            [InlineKeyboardButton(ui["btn_menu"], callback_data="menu")],
        ]
    )
    await edit(query, text, markup)


async def ask_quiz(query: Any, state: dict, lang: str) -> None:
    ui = UI[lang]
    if state["i"] < len(QUIZ):
        q = QUIZ[state["i"]][lang]
        rows = [
            [InlineKeyboardButton(opt, callback_data=f"qa:{idx}")]
            for idx, opt in enumerate(q["options"])
        ]
        head = ui["quiz_q"].format(i=state["i"] + 1, n=len(QUIZ))
        await edit(query, f"{head}\n\n<b>{q['q']}</b>", InlineKeyboardMarkup(rows))
        return

    score, total = state["score"], len(QUIZ)
    if state.get("counted") is None:
        state["counted"] = True
        bump("quizzes")
    if score == total:
        comment = ui["quiz_top"]
    elif score >= 3:
        comment = ui["quiz_good"]
    else:
        comment = ui["quiz_low"]
    markup = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(ui["btn_retry"], callback_data="quiz_start")],
            [InlineKeyboardButton(ui["btn_menu"], callback_data="menu")],
        ]
    )
    await edit(query, f"{ui['quiz_result'].format(s=score, n=total)}\n\n{comment}", markup)


# ----------------------------------------------------------------------
# ODDIY MATN: xabar berish va havola tekshirish
# ----------------------------------------------------------------------

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg, user = update.message, update.effective_user
    if msg is None or user is None or context.user_data is None:
        return
    ud = context.user_data
    touch_user(user.id)
    lang = get_lang(user.id)
    ui = UI[lang]
    text = (msg.text or "").strip()

    # --- Havolani tekshirish ---
    if ud.get("awaiting_link"):
        if not rate_ok(user.id, "link", LINK_LIMIT, LINK_WINDOW):
            await msg.reply_text(ui["link_limit"])
            return
        url = find_url(text)
        if url is None:
            await msg.reply_text(ui["link_none"])
            return
        bump("link_checks")
        markup = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(ui["btn_check_another"], callback_data="link")],
                [InlineKeyboardButton(ui["btn_menu"], callback_data="menu")],
            ]
        )
        ud.pop("awaiting_link", None)
        await msg.reply_text(link_report(url, lang), reply_markup=markup, parse_mode=ParseMode.HTML)
        return

    # --- Xabar berish ---
    if ud.get("awaiting_report"):
        if len(text) > REPORT_MAX_LEN:
            await msg.reply_text(ui["report_long"].format(n=REPORT_MAX_LEN))
            return
        if not text:
            return
        if not rate_ok(user.id, "report", REPORT_LIMIT, REPORT_WINDOW):
            ud.pop("awaiting_report", None)
            await msg.reply_text(ui["report_limit"], reply_markup=main_menu(lang))
            return

        record = {
            "time": now_iso(),
            "user_id": user.id,
            "username": user.username,
            "text": text,
        }
        with open(REPORTS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        bump("reports")
        log.info("Yangi xabar (report) qabul qilindi: user_id=%s", user.id)

        if ADMIN_ID:
            try:
                await context.bot.send_message(
                    chat_id=int(ADMIN_ID),
                    text=f"🚨 Yangi shubhali holat\nFoydalanuvchi: @{user.username or user.id}\n\n{text}",
                )
            except Exception as e:  # admin botni hali boshlamagan bo'lishi mumkin
                log.warning("Adminga yuborib bo'lmadi: %s", e)

        ud.pop("awaiting_report", None)
        await msg.reply_text(ui["report_thanks"], reply_markup=main_menu(lang))
        return

    await msg.reply_text(ui["use_menu"], reply_markup=main_menu(lang))


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.error("Xatolik: %s", context.error)


# ----------------------------------------------------------------------
# ISHGA TUSHIRISH
# ----------------------------------------------------------------------

def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN topilmadi. Avval: export BOT_TOKEN='...'")

    load_data()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("lang", lang_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_error_handler(on_error)

    log.info("SafeChat bot ishga tushdi...")
    app.run_polling()


if __name__ == "__main__":
    main()