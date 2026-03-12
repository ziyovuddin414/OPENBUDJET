import os
import json
import time
import random
import hashlib
import requests
from flask import Flask, request

app = Flask(__name__)

# =====================================================
#  SOZLAMALAR
# =====================================================
BOT_TOKEN     = os.environ.get('BOT_TOKEN', '8655547711:AAFoeHk11cb068H1T6fMXz7wcQwwsDgPk2M')
ADMIN_ID      = int(os.environ.get('ADMIN_ID', '782269942'))
PROJECT_ID    = 53
SITE_LINK     = "https://openbudget.uz/boards/initiatives/initiative/53/011e4061-f791-4534-9c05-83b3f25b0da5"
VOTE_BONUS    = 30000
REFERAL_BONUS = 20000
MIN_WITHDRAW  = 60000

API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# =====================================================
#  VERCEL KV STORAGE (fayllar o'rniga)
# =====================================================
KV_URL     = os.environ.get('KV_REST_API_URL', '')
KV_TOKEN   = os.environ.get('KV_REST_API_TOKEN', '')

def kv_get(key):
    if not KV_URL:
        return None
    try:
        r = requests.get(f"{KV_URL}/get/{key}", headers={"Authorization": f"Bearer {KV_TOKEN}"}, timeout=5)
        data = r.json()
        if data.get('result'):
            return json.loads(data['result'])
    except:
        pass
    return None

def kv_set(key, value):
    if not KV_URL:
        return
    try:
        requests.post(f"{KV_URL}/set/{key}", headers={"Authorization": f"Bearer {KV_TOKEN}", "Content-Type": "application/json"}, json={"value": json.dumps(value)}, timeout=5)
    except:
        pass

def kv_delete(key):
    if not KV_URL:
        return
    try:
        requests.get(f"{KV_URL}/del/{key}", headers={"Authorization": f"Bearer {KV_TOKEN}"}, timeout=5)
    except:
        pass

# =====================================================
#  TELEGRAM
# =====================================================
def tg(method, data=None, files=None):
    try:
        r = requests.post(f"{API}/{method}", data=data, files=files, timeout=30)
        return r.json()
    except:
        return {}

def send(chat_id, text, keyboard=None, inline=None):
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if keyboard:
        data["reply_markup"] = json.dumps({"keyboard": keyboard, "resize_keyboard": True})
    if inline:
        data["reply_markup"] = json.dumps({"inline_keyboard": inline})
    return tg("sendMessage", data)

def answer_cb(cb_id, text=""):
    tg("answerCallbackQuery", {"callback_query_id": cb_id, "text": text, "show_alert": bool(text)})

# =====================================================
#  MA'LUMOTLAR (Vercel KV)
# =====================================================
def get_user(chat_id):
    return kv_get(f"user:{chat_id}") or {}

def save_user(chat_id, data):
    old = get_user(chat_id)
    old.update(data)
    kv_set(f"user:{chat_id}", old)

def get_field(chat_id, key, default=""):
    return get_user(chat_id).get(key, default)

def set_field(chat_id, key, val):
    save_user(chat_id, {key: val})

def get_balance(chat_id):
    return int(get_field(chat_id, "balance", 0))

def add_balance(chat_id, amount):
    set_field(chat_id, "balance", get_balance(chat_id) + amount)

def money(amount):
    return f"{amount:,} so'm".replace(",", " ")

def phone_voted(phone):
    return kv_get(f"vote:{hashlib.md5(phone.encode()).hexdigest()}") is not None

def save_vote(chat_id, phone):
    h = hashlib.md5(phone.encode()).hexdigest()
    if kv_get(f"vote:{h}"):
        return False
    kv_set(f"vote:{h}", {"chat_id": chat_id, "phone": phone, "time": int(time.time())})
    add_balance(chat_id, VOTE_BONUS)
    # Referal bonus
    ref = get_field(chat_id, "ref_by")
    if ref and str(ref) != str(chat_id) and not get_field(chat_id, "ref_done"):
        add_balance(ref, REFERAL_BONUS)
        set_field(chat_id, "ref_done", 1)
        try:
            send(ref, f"🎉 Referalingiz ovoz berdi!\n💰 <b>+{money(REFERAL_BONUS)}</b> hisobingizga qo'shildi!")
        except:
            pass
    return True

def has_request(chat_id):
    return kv_get(f"req:{chat_id}") is not None

def save_request(chat_id, card):
    if has_request(chat_id):
        return False
    kv_set(f"req:{chat_id}", {"chat_id": chat_id, "card": card, "amount": get_balance(chat_id), "time": int(time.time())})
    return True

def approve_request(chat_id):
    req = kv_get(f"req:{chat_id}")
    if not req:
        return False
    set_field(chat_id, "balance", 0)
    kv_delete(f"req:{chat_id}")
    send(chat_id, f"✅ <b>To'lov amalga oshirildi!</b>\n\n💰 <b>{money(req['amount'])}</b> kartangizga o'tkazildi!")
    return True

def reject_request(chat_id):
    kv_delete(f"req:{chat_id}")
    send(chat_id, "❌ <b>Chiqarish so'rovingiz rad etildi.</b>")
    return True

# =====================================================
#  OPENBUDGET API
# =====================================================
UZ_IPS = ["46.227.123.", "37.110.212.", "46.255.69.", "62.209.128."]

def opb_api(endpoint, data):
    ip = random.choice(UZ_IPS) + str(random.randint(2, 253))
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
        "Referer": SITE_LINK,
        "X-Forwarded-For": ip,
        "X-Real-IP": ip,
        "Origin": "https://openbudget.uz",
        "Accept": "application/json",
    }
    try:
        r = requests.post(f"https://admin.openbudget.uz/api/v1/{endpoint}", data=data, headers=headers, verify=False, timeout=30)
        return r.status_code, r.json() if r.text else {}
    except Exception as e:
        return 0, {"error": str(e)}

# =====================================================
#  MENYULAR
# =====================================================
def main_menu(chat_id, msg=""):
    is_admin = str(chat_id) == str(ADMIN_ID)
    if is_admin:
        keyboard = [
            ["📊 Statistika", "👥 Foydalanuvchilar"],
            ["📋 Ovozlar ro'yxati", "💸 Chiqarish so'rovlari"],
            ["📢 Xabar yuborish", "🔗 Link ko'rish"],
        ]
        if not msg:
            msg = "🏠 <b>Admin panel</b>\nAmal tanlang:"
    else:
        keyboard = [
            [{"text": "📲 Telefon yuborish", "request_contact": True}],
            ["💰 Hisobim", "🔗 Referal havola"],
            ["💳 Pul chiqarish", "ℹ️ Yordam"],
        ]
        if not msg:
            msg = (f"👋 <b>Salom!</b> Open Budget ovoz berish botiga xush kelibsiz!\n\n"
                   f"📱 Telefon raqamingizni yuboring va ovoz bering.\n\n"
                   f"💰 Har bir ovoz: <b>{money(VOTE_BONUS)}</b>\n"
                   f"👥 Referal bonus: <b>{money(REFERAL_BONUS)}</b>")
    send(chat_id, msg, keyboard=keyboard)

# =====================================================
#  BOT LOGIKASI
# =====================================================
def handle(update):
    # Callback
    if "callback_query" in update:
        cb = update["callback_query"]
        chat_id = cb["message"]["chat"]["id"]
        data = cb.get("data", "")
        cb_id = cb["id"]

        if str(chat_id) == str(ADMIN_ID):
            if data.startswith("pay_"):
                approve_request(data[4:])
                answer_cb(cb_id, "✅ To'landi!")
            elif data.startswith("reject_"):
                reject_request(data[7:])
                answer_cb(cb_id, "❌ Rad etildi!")
        return

    msg = update.get("message", {})
    if not msg:
        return

    chat_id = msg["chat"]["id"]
    text = msg.get("text", "").strip()
    contact = msg.get("contact")
    is_admin = str(chat_id) == str(ADMIN_ID)

    # Foydalanuvchini saqlash
    save_user(chat_id, {
        "chat_id": chat_id,
        "first_name": msg["chat"].get("first_name", ""),
        "last_name": msg["chat"].get("last_name", ""),
        "username": msg["chat"].get("username", ""),
    })

    state = get_field(chat_id, "state")

    # /start
    if text.startswith("/start"):
        args = text.split(maxsplit=1)
        if len(args) > 1 and args[1].startswith("ref"):
            ref_id = args[1][3:]
            if str(ref_id) != str(chat_id) and not get_field(chat_id, "ref_by"):
                set_field(chat_id, "ref_by", ref_id)
        set_field(chat_id, "state", "")
        main_menu(chat_id)
        return

    if text in ["❌ Bekor qilish", "🔙 Orqaga"]:
        set_field(chat_id, "state", "")
        main_menu(chat_id)
        return

    # OTP state
    if state == "otp":
        otp = "".join(filter(str.isdigit, text))
        if len(otp) >= 4:
            phone = get_field(chat_id, "tmp_phone")
            token = get_field(chat_id, "tmp_token")
            code, resp = opb_api("user/temp/vote/", {"phone": phone, "token": token, "otp": otp, "application": PROJECT_ID})
            if code == 200:
                set_field(chat_id, "state", "")
                save_vote(chat_id, phone)
                bal = get_balance(chat_id)
                name = get_field(chat_id, "first_name")
                send(ADMIN_ID, f"🗳 <b>Yangi ovoz!</b>\n👤 {name}\n📞 {phone}\n🕐 {time.strftime('%d.%m.Y %H:%M')}")
                main_menu(chat_id, f"🎉 <b>Ovoz qabul qilindi!</b>\n\n💰 <b>+{money(VOTE_BONUS)}</b> hisobingizga tushdi!\n💳 Balans: <b>{money(bal)}</b>")
            elif resp.get("detail") == "Invalid code":
                send(chat_id, "❌ Kod xato! Qaytadan kiriting:")
            else:
                set_field(chat_id, "state", "")
                main_menu(chat_id, "⚠️ Xatolik. Qaytadan urinib ko'ring.")
        else:
            send(chat_id, "⚠️ SMS kodini kiriting (4-6 raqam):")
        return

    # Captcha state
    if state == "captcha":
        ans = "".join(filter(str.isdigit, text))
        if len(ans) >= 2:
            phone = get_field(chat_id, "tmp_phone")
            code, resp = opb_api("user/validate_phone/", {"phone": phone, "application": PROJECT_ID, "captcha": ans})
            if code == 200 and resp.get("token"):
                set_field(chat_id, "state", "otp")
                set_field(chat_id, "tmp_token", resp["token"])
                send(chat_id, "✅ SMS yuborildi!\n\nKodni kiriting:", keyboard=[["❌ Bekor qilish"]])
            else:
                send(chat_id, "❌ Captcha xato. Qaytadan:")
        else:
            send(chat_id, "⚠️ Captchadagi raqamlarni kiriting:")
        return

    # Card state
    if state == "card":
        card = text.replace(" ", "")
        if len(card) >= 9:
            bal = get_balance(chat_id)
            if save_request(chat_id, card):
                set_field(chat_id, "state", "")
                name = get_field(chat_id, "first_name")
                inline = [[
                    {"text": "✅ To'lash", "callback_data": f"pay_{chat_id}"},
                    {"text": "❌ Rad etish", "callback_data": f"reject_{chat_id}"}
                ]]
                send(ADMIN_ID, f"💸 <b>Chiqarish so'rovi!</b>\n👤 {name}\n💰 <b>{money(bal)}</b>\n💳 <code>{card}</code>", inline=inline)
                main_menu(chat_id, "✅ So'rovingiz yuborildi! 🙏")
            else:
                main_menu(chat_id, "⏳ Oldingi so'rovingiz ko'rib chiqilmoqda.")
        else:
            send(chat_id, "⚠️ To'liq karta raqamini kiriting:")
        return

    # Broadcast state
    if state == "broadcast" and is_admin:
        if len(text) > 2:
            set_field(chat_id, "state", "")
            main_menu(chat_id, "✅ Xabar yuborildi!")
        else:
            send(chat_id, "⚠️ Xabar qisqa:")
        return

    # Kontakt
    if contact:
        phone = contact.get("phone_number", "")
        if not phone.startswith("+"):
            phone = "+" + phone
        phone_clean = phone.replace("+", "")

        if not phone_clean.startswith("998") or len(phone_clean) != 12:
            send(chat_id, "⚠️ Faqat O'zbekiston raqamlari (+998...) qabul qilinadi.")
            return

        if phone_voted(phone_clean):
            send(chat_id, f"⚠️ Bu raqam allaqachon ovoz bergan!")
            return

        send(chat_id, f"⏳ SMS yuborilmoqda...")
        code, resp = opb_api("user/validate_phone/", {"phone": phone_clean, "application": PROJECT_ID})

        if code == 200 and resp.get("token"):
            set_field(chat_id, "state", "otp")
            set_field(chat_id, "tmp_phone", phone_clean)
            set_field(chat_id, "tmp_token", resp["token"])
            send(chat_id, "📨 <b>SMS yuborildi!</b>\n\nKodni kiriting:", keyboard=[["❌ Bekor qilish"]])
        elif resp.get("captcha_url") or resp.get("captcha") or resp.get("image"):
            cap_url = resp.get("captcha_url") or resp.get("captcha") or resp.get("image")
            set_field(chat_id, "state", "captcha")
            set_field(chat_id, "tmp_phone", phone_clean)
            try:
                img = requests.get(cap_url, timeout=10, verify=False)
                files = {"photo": ("captcha.png", img.content, "image/png")}
                data_send = {"chat_id": chat_id, "caption": "🔒 Captcha raqamlarini kiriting:", "parse_mode": "HTML"}
                tg("sendPhoto", data_send, files)
            except:
                send(chat_id, f"🔒 Captcha: {cap_url}\n\nRaqamlarni kiriting:")
        elif resp.get("detail") == "This number was used to vote":
            send(chat_id, "⚠️ Bu raqam allaqachon ovoz bergan!")
        else:
            send(chat_id, "⚠️ Serverda xatolik. Keyinroq urinib ko'ring.")
        return

    # Tugmalar
    if text == "💰 Hisobim":
        bal = get_balance(chat_id)
        send(chat_id, f"💰 <b>Hisobim</b>\n────────────────\n💳 Balans: <b>{money(bal)}</b>\n────────────────\n💸 Minimal chiqarish: <b>{money(MIN_WITHDRAW)}</b>")
        return

    if text == "🔗 Referal havola":
        bot_info = tg("getMe")
        username = bot_info.get("result", {}).get("username", "")
        link = f"https://t.me/{username}?start=ref{chat_id}"
        send(chat_id, f"🔗 <b>Referal havolangiz:</b>\n<code>{link}</code>\n\n💰 Har referal: <b>{money(REFERAL_BONUS)}</b>")
        return

    if text == "💳 Pul chiqarish":
        bal = get_balance(chat_id)
        if has_request(chat_id):
            send(chat_id, "⏳ So'rovingiz ko'rib chiqilmoqda.")
            return
        if bal < MIN_WITHDRAW:
            send(chat_id, f"❌ Balans yetarli emas.\n💳 Balans: <b>{money(bal)}</b>\n💸 Kerak: <b>{money(MIN_WITHDRAW)}</b>")
            return
        set_field(chat_id, "state", "card")
        send(chat_id, f"💳 Summa: <b>{money(bal)}</b>\n\nKarta raqamingizni kiriting:", keyboard=[["❌ Bekor qilish"]])
        return

    if text == "ℹ️ Yordam":
        send(chat_id, f"ℹ️ <b>Bot haqida</b>\n\n✅ Har ovoz: <b>{money(VOTE_BONUS)}</b>\n👥 Referal: <b>{money(REFERAL_BONUS)}</b>\n💸 Minimal: <b>{money(MIN_WITHDRAW)}</b>")
        return

    # Admin tugmalar
    if is_admin:
        if text == "📊 Statistika":
            send(chat_id, "📊 <b>Statistika</b>\n\nBot ishlayapti! ✅")
            return
        if text == "🔗 Link ko'rish":
            send(chat_id, f"🔗 <code>{SITE_LINK}</code>")
            return
        if text == "📢 Xabar yuborish":
            set_field(chat_id, "state", "broadcast")
            send(chat_id, "📢 Xabarni kiriting:", keyboard=[["🔙 Orqaga"]])
            return

    # Telefon matn orqali
    clean = "".join(c for c in text if c.isdigit())
    if len(clean) == 9:
        clean = "998" + clean
    if len(clean) == 12 and clean.startswith("998"):
        if phone_voted(clean):
            send(chat_id, "⚠️ Bu raqam allaqachon ovoz bergan!")
            return
        send(chat_id, "⏳ SMS yuborilmoqda...")
        code, resp = opb_api("user/validate_phone/", {"phone": clean, "application": PROJECT_ID})
        if code == 200 and resp.get("token"):
            set_field(chat_id, "state", "otp")
            set_field(chat_id, "tmp_phone", clean)
            set_field(chat_id, "tmp_token", resp["token"])
            send(chat_id, "📨 <b>SMS yuborildi!</b>\n\nKodni kiriting:", keyboard=[["❌ Bekor qilish"]])
        else:
            send(chat_id, "⚠️ Xatolik. Keyinroq urinib ko'ring.")
        return

    main_menu(chat_id)

# =====================================================
#  FLASK ROUTES
# =====================================================
@app.route("/", methods=["GET"])
def index():
    return "Bot ishlayapti! ✅"

@app.route("/api/webhook", methods=["POST"])
def webhook():
    try:
        update = request.get_json()
        if update:
            handle(update)
    except Exception as e:
        print(f"Error: {e}")
    return "OK", 200

@app.route("/setup", methods=["GET"])
def setup():
    host = request.host
    url = f"https://{host}/api/webhook"
    r = requests.get(f"{API}/setWebhook?url={url}")
    return f"Webhook ulandi: {url}<br>{r.text}"
