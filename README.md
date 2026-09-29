# SafeChat bot: ishga tushirish va serverga joylash

## 1. Token olish (5 daqiqa)
1. Telegramda **@BotFather** ga kiring, `/newbot` yozing.
2. Bot nomi va username bering (username `bot` bilan tugashi kerak, masalan `safechat_uz_bot`).
3. BotFather bergan **tokenni** saqlab qo'ying. Uni hech kimga bermang va GitHubga yuklamang.
4. (Ixtiyoriy) Xabarlar sizga kelishi uchun **@userinfobot** dan o'z ID raqamingizni oling.

## 2. Kompyuteringizda sinash
```bash
cd safechat_bot
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
export BOT_TOKEN="TOKEN_SHU_YERDA"      # Windows: set BOT_TOKEN=TOKEN
export ADMIN_ID="123456789"             # ixtiyoriy
python bot.py
```
Telegramda botingizga `/start` yozing. Menyu chiqsa, hammasi ishlayapti.

## 3. Serverga joylash (Ubuntu VPS)

**a) Serverga kirish va tayyorlash**
```bash
ssh root@SERVER_IP
apt update && apt install -y python3 python3-venv python3-pip
```

**b) Fayllarni yuklash** (o'z kompyuteringizdan)
```bash
scp -r safechat_bot root@SERVER_IP:/opt/
```

**c) Server ichida o'rnatish**
```bash
cd /opt/safechat_bot
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp .env.example .env
nano .env        # BOT_TOKEN va ADMIN_ID ni yozing, Ctrl+O, Enter, Ctrl+X
chmod 600 .env
```

**d) Doimiy ishlashi uchun systemd xizmati**
```bash
nano /etc/systemd/system/safechat.service
```
Ichiga yozing:
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
Keyin:
```bash
systemctl daemon-reload
systemctl enable --now safechat
systemctl status safechat        # "active (running)" chiqishi kerak
journalctl -u safechat -f        # jonli loglar
```

Endi server o'chib-yonsa ham, bot o'zi qayta ishga tushadi.

## 4. Foydali buyruqlar
| Nima | Buyruq |
|---|---|
| Botni qayta ishga tushirish | `systemctl restart safechat` |
| Botni to'xtatish | `systemctl stop safechat` |
| Kelgan xabarlarni ko'rish | `cat /opt/safechat_bot/reports.jsonl` |
| Kodni yangilagach | `scp bot.py root@SERVER_IP:/opt/safechat_bot/` va `systemctl restart safechat` |

## 5. Muammo bo'lsa
- **Bot javob bermayapti:** `journalctl -u safechat -n 50` ni ko'ring. Odatda token noto'g'ri yozilgan bo'ladi.
- **`BOT_TOKEN topilmadi`:** `.env` faylda token yozilganini tekshiring.
- **Admin xabar olmayapti:** admin avval botga `/start` yozgan bo'lishi kerak.

## Fayllar
- `bot.py`: butun bot kodi. Matnlar (xavf turlari, checklist, test) tepadagi `THREATS` va `QUIZ` ichida, Sabina shu yerda tahrirlaydi.
- `requirements.txt`: kutubxonalar.
- `.env.example`: token shabloni.
- `reports.jsonl`: foydalanuvchilar yuborgan xabarlar (bot o'zi yaratadi).
