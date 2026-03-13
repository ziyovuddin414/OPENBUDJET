import os, json, time, hashlib, random, requests
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN     = '8655547711:AAFoeHk11cb068H1T6fMXz7wcQwwsDgPk2M'
ADMIN_ID      = '782269942'
CHANNEL_ID    = '@openbudjet_pays'
PROJECT_ID    = '53'
SITE_LINK     = 'https://openbudget.uz/boards/initiatives/initiative/53/011e4061-f791-4534-9c05-83b3f25b0da5'
VOTE_BONUS    = 30000
REFERAL_BONUS = 20000
MIN_WITHDRAW  = 60000
API           = f'https://api.telegram.org/bot{BOT_TOKEN}'

# ===================== STORAGE =====================
STORE = {}

def store_get(key):
    return STORE.get(key)

def store_set(key, val):
    STORE[key] = val

def store_del(key):
    STORE.pop(key, None)

# ===================== TELEGRAM =====================
def tg(method, **kwargs):
    try:
        r = requests.post(f'{API}/{method}', json=kwargs, timeout=15)
        return r.json()
    except:
        return {}

def send(chat_id, text, keyboard=None, inline=None):
    data = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML', 'disable_web_page_preview': True}
    if keyboard:
        data['reply_markup'] = json.dumps({'keyboard': keyboard, 'resize_keyboard': True})
    if inline:
        data['reply_markup'] = json.dumps({'inline_keyboard': inline})
    return tg('sendMessage', **data)

def answer_cb(cb_id, text='', alert=False):
    tg('answerCallbackQuery', callback_query_id=cb_id, text=text, show_alert=alert)

# ===================== USER DATA =====================
def get_user(cid):
    return store_get(f'u:{cid}') or {}

def save_user(cid, data):
    u = get_user(cid)
    u.update(data)
    store_set(f'u:{cid}', u)

def get_field(cid, key, default=''):
    return get_user(cid).get(key, default)

def set_field(cid, key, val):
    save_user(cid, {key: val})

def get_balance(cid):
    return int(get_field(cid, 'balance', 0))

def add_balance(cid, amount):
    set_field(cid, 'balance', get_balance(cid) + amount)

def money(n):
    return f"{n:,} so'm".replace(',', ' ')

def phone_voted(phone):
    return store_get(f'v:{hashlib.md5(phone.encode()).hexdigest()}') is not None

def save_vote(cid, phone):
    h = hashlib.md5(phone.encode()).hexdigest()
    if store_get(f'v:{h}'):
        return False
    store_set(f'v:{h}', {'chat_id': cid, 'phone': phone, 'time': int(time.time())})
    add_balance(cid, VOTE_BONUS)
    ref = get_field(cid, 'ref_by')
    if ref and str(ref) != str(cid) and not get_field(cid, 'ref_done'):
        add_balance(ref, REFERAL_BONUS)
        set_field(cid, 'ref_done', 1)
        try:
            send(ref, f'🎉 Referalingiz ovoz berdi!\n💰 +{money(REFERAL_BONUS)} hisobingizga qo\'shildi!')
        except:
            pass
    return True

def has_request(cid):
    return store_get(f'r:{cid}') is not None

def save_request(cid, card):
    if has_request(cid):
        return False
    store_set(f'r:{cid}', {'chat_id': cid, 'card': card, 'amount': get_balance(cid), 'time': int(time.time())})
    return True

def approve_request(cid):
    req = store_get(f'r:{cid}')
    if not req:
        return False
    set_field(cid, 'balance', 0)
    store_del(f'r:{cid}')
    send(cid, f'✅ <b>To\'lov amalga oshirildi!</b>\n\n💰 <b>{money(req["amount"])}</b> kartangizga o\'tkazildi!')
    return True

def reject_request(cid):
    store_del(f'r:{cid}')
    send(cid, '❌ <b>Chiqarish so\'rovingiz rad etildi.</b>')
    return True

def get_votes_count():
    return sum(1 for k in STORE if k.startswith('v:'))

def get_users_count():
    return sum(1 for k in STORE if k.startswith('u:'))

# ===================== OPB API =====================
UZ_IPS = ['46.227.123.', '37.110.212.', '46.255.69.', '62.209.128.', '37.110.214.', '31.135.209.']

def opb_api(endpoint, data):
    ip = random.choice(UZ_IPS) + str(random.randint(2, 253))
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/105.0.0.0 Safari/537.36',
        'Referer': SITE_LINK,
        'REMOTE_ADDR': ip,
        'HTTP_X_FORWARDED_FOR': ip,
        'HTTP_X_REAL_IP': ip,
        'X-Forwarded-For': ip,
        'X-Real-IP': ip,
        'Origin': 'https://openbudget.uz',
        'Accept': 'application/json',
    }
    try:
        r = requests.post(
            f'https://admin.openbudget.uz/api/v1/{endpoint}',
            data=data,
            headers=headers,
            verify=False,
            timeout=30
        )
        return r.status_code, r.json() if r.text else {}
    except Exception as e:
        return 0, {'error': str(e)}

# ===================== MENUS =====================
def main_menu(cid, msg=''):
    is_admin = str(cid) == ADMIN_ID
    if is_admin:
        kb = [
            ['📊 Statistika', '👥 Foydalanuvchilar'],
            ['🗣 Ovozlar', '🏦 Murojaatlar'],
            ['📢 Xabar yuborish', '🔗 Link'],
        ]
        if not msg:
            msg = '🏠 <b>Admin panel</b>\nAmal tanlang:'
    else:
        kb = [
            [{'text': '📲 Telefon yuborish', 'request_contact': True}],
            ['💰 Hisobim', '🔗 Referal havola'],
            ['💳 Pul chiqarish', 'ℹ️ Yordam'],
        ]
        if not msg:
            msg = (
                f'👋 <b>Salom!</b> Open Budget ovoz berish botiga xush kelibsiz!\n\n'
                f'📱 Telefon raqamingizni yuboring va ovoz bering.\n\n'
                f'💰 Har bir ovoz: <b>{money(VOTE_BONUS)}</b>\n'
                f'👥 Referal bonus: <b>{money(REFERAL_BONUS)}</b>'
            )
    send(cid, msg, keyboard=kb)

# ===================== HANDLERS =====================
def handle(update):
    # Callback
    if 'callback_query' in update:
        cb = update['callback_query']
        cid = str(cb['message']['chat']['id'])
        data = cb.get('data', '')
        cb_id = cb['id']
        if cid == ADMIN_ID:
            if data.startswith('pay_'):
                approve_request(data[4:])
                answer_cb(cb_id, '✅ To\'landi!', True)
                return
            if data.startswith('reject_'):
                reject_request(data[7:])
                answer_cb(cb_id, '❌ Rad etildi!', True)
                return
        answer_cb(cb_id)
        return

    msg = update.get('message', {})
    if not msg:
        return

    cid = str(msg['chat']['id'])
    text = msg.get('text', '').strip()
    contact = msg.get('contact')
    is_admin = cid == ADMIN_ID

    save_user(cid, {
        'first_name': msg['chat'].get('first_name', ''),
        'last_name': msg['chat'].get('last_name', ''),
        'username': msg['chat'].get('username', ''),
    })

    state = get_field(cid, 'state')

    # /start
    if text.startswith('/start'):
        parts = text.split(maxsplit=1)
        if len(parts) > 1 and parts[1].startswith('ref'):
            ref_id = parts[1][3:]
            if ref_id != cid and not get_field(cid, 'ref_by'):
                set_field(cid, 'ref_by', ref_id)
        set_field(cid, 'state', '')
        main_menu(cid)
        return

    if text in ['❌ Bekor qilish', '🔙 Orqaga']:
        set_field(cid, 'state', '')
        main_menu(cid)
        return

    # OTP
    if state == 'otp':
        otp = ''.join(filter(str.isdigit, text))
        if len(otp) >= 4:
            phone = get_field(cid, 'tmp_phone')
            token = get_field(cid, 'tmp_token')
            code, resp = opb_api('user/temp/vote/', {
                'phone': phone, 'token': token, 'otp': otp, 'application': PROJECT_ID
            })
            if code == 200:
                set_field(cid, 'state', '')
                save_vote(cid, phone)
                bal = get_balance(cid)
                name = get_field(cid, 'first_name')

                # Admin ga xabar
                send(ADMIN_ID,
                    f'🗳 <b>Yangi ovoz!</b>\n'
                    f'────────────────\n'
                    f'👤 {name}\n'
                    f'📞 {phone}\n'
                    f'🕐 {time.strftime("%d.%m.%Y %H:%M")}\n'
                    f'────────────────\n'
                    f'📊 Jami: <b>{get_votes_count()} ta</b>'
                )

                # Kanalga xabar
                send(CHANNEL_ID,
                    f'✅ <b>Yangi ovoz berildi!</b>\n\n'
                    f'👤 <b>{name}</b>\n'
                    f'💰 <b>60 000 so\'m to\'lov qilindi</b>\n'
                    f'🕐 {time.strftime("%d.%m.%Y %H:%M")}\n'
                    f'📊 Jami ovozlar: <b>{get_votes_count()} ta</b>'
                )

                main_menu(cid,
                    f'🎉 <b>Ovoz qabul qilindi!</b>\n\n'
                    f'💰 <b>+{money(VOTE_BONUS)}</b> hisobingizga tushdi!\n'
                    f'💳 Balans: <b>{money(bal)}</b>\n\n'
                    f'📱 Yangi raqam bilan yana ovoz bering!'
                )
            elif resp.get('detail') == 'Invalid code':
                send(cid, '❌ Kod xato! Qaytadan kiriting:')
            else:
                detail = resp.get('detail', '')
                wait = ''
                import re
                m = re.search(r'Expected available in (\d+) seconds', detail)
                if m:
                    wait = f'\n⏰ <b>{int(int(m.group(1))/60)+1} daqiqa</b> kuting.'
                set_field(cid, 'state', '')
                main_menu(cid, f'⚠️ Xatolik.{wait}')
        else:
            send(cid, '⚠️ SMS kodini kiriting (4-6 raqam):')
        return

    # Card
    if state == 'card':
        card = text.replace(' ', '')
        if len(card) >= 9:
            bal = get_balance(cid)
            if save_request(cid, card):
                set_field(cid, 'state', '')
                name = get_field(cid, 'first_name')
                inline = [[
                    {'text': '✅ To\'lash', 'callback_data': f'pay_{cid}'},
                    {'text': '❌ Rad etish', 'callback_data': f'reject_{cid}'}
                ]]
                send(ADMIN_ID,
                    f'💸 <b>Chiqarish so\'rovi!</b>\n'
                    f'👤 {name}\n'
                    f'💰 <b>{money(bal)}</b>\n'
                    f'💳 <code>{card}</code>',
                    inline=inline
                )
                main_menu(cid, '✅ So\'rovingiz yuborildi! 🙏')
            else:
                main_menu(cid, '⏳ Oldingi so\'rovingiz ko\'rib chiqilmoqda.')
        else:
            send(cid, '⚠️ To\'liq karta raqamini kiriting:')
        return

    # Broadcast
    if state == 'broadcast' and is_admin:
        if len(text) > 2:
            sent = 0
            for k in list(STORE.keys()):
                if k.startswith('u:'):
                    uid = k[2:]
                    if uid != ADMIN_ID:
                        send(uid, text)
                        sent += 1
                        if sent % 10 == 0:
                            time.sleep(1)
            set_field(cid, 'state', '')
            main_menu(cid, f'✅ <b>{sent}</b> foydalanuvchiga yuborildi.')
        else:
            send(cid, '⚠️ Xabar qisqa:')
        return

    # Kontakt
    if contact:
        phone = contact.get('phone_number', '').replace('+', '').replace(' ', '')
        if not phone.startswith('998'):
            phone = '998' + phone
        if len(phone) != 12 or not phone.startswith('998'):
            send(cid, '⚠️ Faqat O\'zbekiston raqamlari (+998...) qabul qilinadi.')
            return
        if phone_voted(phone):
            send(cid, '⚠️ Bu raqam allaqachon ovoz bergan!')
            return
        send(cid, '⏳ SMS yuborilmoqda...')
        code, resp = opb_api('user/validate_phone/', {'phone': phone, 'application': PROJECT_ID})
        if code == 200 and resp.get('token'):
            set_field(cid, 'state', 'otp')
            set_field(cid, 'tmp_phone', phone)
            set_field(cid, 'tmp_token', resp['token'])
            send(cid, '📨 <b>SMS yuborildi!</b>\n\nKodni kiriting:', keyboard=[['❌ Bekor qilish']])
        elif resp.get('detail') == 'This number was used to vote':
            send(cid, '⚠️ Bu raqam allaqachon ovoz bergan!')
        else:
            detail = resp.get('detail', '')
            wait = ''
            import re
            m = re.search(r'Expected available in (\d+) seconds', detail)
            if m:
                wait = f'\n⏰ <b>{int(int(m.group(1))/60)+1} daqiqa</b> kuting.'
            send(cid, f'⚠️ Serverda xatolik.{wait}\nQaytadan urinib ko\'ring.')
        return

    # Tugmalar
    if text == '💰 Hisobim':
        bal = get_balance(cid)
        send(cid,
            f'💰 <b>Hisobim</b>\n'
            f'────────────────\n'
            f'💳 Balans: <b>{money(bal)}</b>\n'
            f'────────────────\n'
            f'💸 Minimal chiqarish: <b>{money(MIN_WITHDRAW)}</b>'
        )
        return

    if text == '🔗 Referal havola':
        bot_info = tg('getMe')
        username = bot_info.get('result', {}).get('username', '')
        link = f'https://t.me/{username}?start=ref{cid}'
        send(cid,
            f'🔗 <b>Referal tizimi</b>\n'
            f'────────────────\n'
            f'💰 Har referal: <b>{money(REFERAL_BONUS)}</b>\n\n'
            f'📎 Havolangiz:\n<code>{link}</code>'
        )
        return

    if text == '💳 Pul chiqarish':
        bal = get_balance(cid)
        if has_request(cid):
            send(cid, '⏳ So\'rovingiz ko\'rib chiqilmoqda.')
            return
        if bal < MIN_WITHDRAW:
            send(cid, f'❌ Balans yetarli emas!\n💳 Balans: <b>{money(bal)}</b>\n💸 Kerak: <b>{money(MIN_WITHDRAW)}</b>')
            return
        set_field(cid, 'state', 'card')
        send(cid, f'💳 Summa: <b>{money(bal)}</b>\n\nKarta raqamingizni kiriting:', keyboard=[['❌ Bekor qilish']])
        return

    if text == 'ℹ️ Yordam':
        send(cid,
            f'ℹ️ <b>Bot haqida</b>\n\n'
            f'✅ Har ovoz: <b>{money(VOTE_BONUS)}</b>\n'
            f'👥 Referal: <b>{money(REFERAL_BONUS)}</b>\n'
            f'💸 Minimal: <b>{money(MIN_WITHDRAW)}</b>'
        )
        return

    # Admin tugmalar
    if is_admin:
        if text == '📊 Statistika':
            send(cid,
                f'📊 <b>Statistika</b>\n'
                f'────────────────\n'
                f'👥 Foydalanuvchilar: <b>{get_users_count()}</b>\n'
                f'🗳 Jami ovozlar: <b>{get_votes_count()}</b>\n'
                f'🕐 {time.strftime("%d.%m.%Y %H:%M")}'
            )
            return
        if text == '👥 Foydalanuvchilar':
            users = [(k[2:], v) for k, v in STORE.items() if k.startswith('u:')]
            if not users:
                send(cid, '👥 Foydalanuvchilar yo\'q.')
                return
            msg = f'👥 <b>Foydalanuvchilar</b> ({len(users)} ta):\n────────────────\n'
            for i, (uid, u) in enumerate(users[:30], 1):
                name = u.get('first_name', '') + ' ' + u.get('last_name', '')
                msg += f'{i}. <a href="tg://user?id={uid}">{name.strip() or uid}</a>\n'
                msg += f'    💰 {money(get_balance(uid))}\n'
            send(cid, msg)
            return
        if text == '🗣 Ovozlar':
            count = get_votes_count()
            send(cid, f'🗳 Jami ovozlar: <b>{count} ta</b>')
            return
        if text == '🏦 Murojaatlar':
            reqs = [(k[2:], v) for k, v in STORE.items() if k.startswith('r:')]
            if not reqs:
                send(cid, '✅ Hozircha so\'rovlar yo\'q.')
                return
            for uid, req in reqs:
                inline = [[
                    {'text': '✅ To\'lash', 'callback_data': f'pay_{uid}'},
                    {'text': '❌ Rad etish', 'callback_data': f'reject_{uid}'}
                ]]
                name = get_field(uid, 'first_name')
                send(cid,
                    f'💸 <b>Chiqarish so\'rovi</b>\n'
                    f'👤 {name}\n'
                    f'💰 <b>{money(req["amount"])}</b>\n'
                    f'💳 <code>{req["card"]}</code>',
                    inline=inline
                )
            return
        if text == '🔗 Link':
            send(cid, f'🔗 <code>{SITE_LINK}</code>')
            return
        if text == '📢 Xabar yuborish':
            set_field(cid, 'state', 'broadcast')
            send(cid, '📢 Xabarni kiriting:', keyboard=[['🔙 Orqaga']])
            return

    # Telefon matn orqali
    import re
    clean = re.sub(r'\D', '', text)
    if len(clean) == 9:
        clean = '998' + clean
    if len(clean) == 12 and clean.startswith('998'):
        if phone_voted(clean):
            send(cid, '⚠️ Bu raqam allaqachon ovoz bergan!')
            return
        send(cid, '⏳ SMS yuborilmoqda...')
        code, resp = opb_api('user/validate_phone/', {'phone': clean, 'application': PROJECT_ID})
        if code == 200 and resp.get('token'):
            set_field(cid, 'state', 'otp')
            set_field(cid, 'tmp_phone', clean)
            set_field(cid, 'tmp_token', resp['token'])
            send(cid, '📨 <b>SMS yuborildi!</b>\n\nKodni kiriting:', keyboard=[['❌ Bekor qilish']])
        else:
            send(cid, '⚠️ Xatolik. Qaytadan urinib ko\'ring.')
        return

    main_menu(cid)

# ===================== FLASK =====================
@app.route('/', methods=['GET'])
def index():
    return 'Bot ishlayapti! ✅'

@app.route('/api/webhook', methods=['POST'])
def webhook():
    try:
        update = request.get_json(force=True)
        if update:
            handle(update)
    except Exception as e:
        print(f'Error: {e}')
    return 'OK', 200

@app.route('/setup', methods=['GET'])
def setup():
    host = request.host
    url = f'https://{host}/api/webhook'
    r = requests.get(f'{API}/setWebhook?url={url}')
    data = r.json()
    if data.get('ok'):
        return f'✅ Webhook ulandi: {url}'
    return f'❌ Xato: {data}'
