# SafeChat: kiberfiribgarlikdan himoyalovchi Telegram bot

Telegramdagi soxta qo'ng'iroq, phishing, zararli fayl va tasdiqlash kodini so'rash holatlaridan himoyalanishga yordam beradi. O'zbekcha va ruscha ishlaydi.

## Imkoniyatlar
- Xavf turini tanlash (belgilari va nima qilish kerak)
- Checklist: "Bu firibgarlikmi?"
- Havolani tekshirish (havola ochilmaydi, faqat manzil tahlil qilinadi)
- Real misollar
- Mini-test
- Tavsiyalar
- Shubhali holat haqida xabar berish (spamdan himoya bilan)
- Ikki til: `/lang`
- `/stats`: statistika (faqat admin)

## Buyruqlar
| Buyruq | Vazifasi |
|---|---|
| `/start` | Bosh menyu (birinchi marta tilni so'raydi) |
| `/lang` | Tilni o'zgartirish |
| `/help` | Yordam |
| `/cancel` | Amalni bekor qilish |
| `/stats` | Statistika (faqat `ADMIN_ID` egasi uchun) |

## 1. Token olish
1. Telegramda **@BotFather** ga kiring, `/newbot` yozing.
2. Nom va username bering (username `bot` bilan tugashi kerak).
3. Bergan **tokenni** maxfiy saqlang. GitHub'ga yoki chatga yubormang.
4. Admin ID olish uchun **@userinfobot** ga `/start` yozing (`/stats` va xabarlar shu ID ga keladi).

## 2. Kompyuterda sinash
```bash
cd safechat_bot
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
BOT_TOKEN="TOKEN" ADMIN_ID="123456789" python bot.py
```

## 3. Serverga joylash (Ubuntu VPS)
```bash
apt update && apt install -y python3 python3-venv python3-pip git
cd /opt
git clone https://github.com/AbdulboriyOBIDJONOV1234/safe-chat-uz-bot-.git safechat_bot
cd safechat_bot
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp .env.example .env
nano .env        # BOT_TOKEN va ADMIN_ID ni yozing (qo'shtirnoqsiz)
chmod 600 .env
```

Doimiy ishlashi uchun `/etc/systemd/system/safechat.service` fayli:
```ini
[Unit]
Description=SafeChat Telegram bot
After=network.target

[Service]
WorkingDirectory=/opt/safechat_bot
EnvironmentFile=/opt/safechat_bot/.env
ExecStart=/opt/safechat_bot/venv/bin/python bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
```bash
systemctl daemon-reload
systemctl enable --now safechat
systemctl status safechat        # active (running)
journalctl -u safechat -f        # jonli loglar
```

## 4. Yangilash (kod o'zgargandan keyin)
Kompyuterda:
```bash
git add .
git commit -m "yangilanish"
git push
```
Serverda:
```bash
cd /opt/safechat_bot && git pull && systemctl restart safechat
```

## 5. Foydali
| Nima | Buyruq |
|---|---|
| Botni qayta ishga tushirish | `systemctl restart safechat` |
| Kelgan xabarlarni ko'rish | `cat /opt/safechat_bot/reports.jsonl` |
| Loglar | `journalctl -u safechat -n 50` |

## Spamdan himoya
- Xabar berish: bir foydalanuvchiga soatiga 3 ta, uzunligi 1000 belgigacha
- Havola tekshiruvi: soatiga 20 ta
Sozlamalar `bot.py` tepasida (`REPORT_LIMIT`, `LINK_LIMIT`).

## Maxfiylik
Faqat Telegram ID, til va faollik sanasi saqlanadi (`data.json`). Ism va telefon saqlanmaydi. Havolalar hech qachon ochilmaydi.

## Fayllar
- `bot.py`: butun bot kodi. Matnlar tepada: `UI` (tugma va xabarlar), `THREATS` (xavf turlari va checklist), `QUIZ` (test), `EXAMPLES` (misollar). Har biri `uz` va `ru` tilida.
- `requirements.txt`: kutubxonalar
- `.env.example`: token shabloni
- `.gitignore`: GitHub'ga yuklanmaydigan fayllar (`.env`, `data.json`, `reports.jsonl`)
- `data.json`, `reports.jsonl`: bot o'zi yaratadi