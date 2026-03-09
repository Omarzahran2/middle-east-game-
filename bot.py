"""
🗺️ لعبة الشرق الأوسط الجيوسياسية - النسخة المتقدمة
"""

import logging, random, string, json, os, io, time, asyncio
from PIL import Image, ImageDraw
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, CallbackQueryHandler, filters

BOT_TOKEN       = os.environ.get("BOT_TOKEN", "")
ADMIN_ID        = int(os.environ.get("ADMIN_ID", "0"))
DATA_FILE       = "game_data.json"
MAP_FILE        = "map_base.png"
FLAGS_DIR       = "flags"
os.makedirs(FLAGS_DIR, exist_ok=True)

# ==================== نظام الوقت ====================
GAME_MINUTE     = 3          # 1 دقيقة لعبة = 3 ثواني حقيقية... لا
# 1 ساعة لعبة = 3 دقائق حقيقية = 180 ثانية
HOUR_REAL       = 180        # ثانية حقيقية = ساعة لعبة
DAY_REAL        = HOUR_REAL * 24
WEEK_REAL       = DAY_REAL * 7   # 21 دقيقة = 1260 ثانية

TAX_COOLDOWN    = HOUR_REAL * 5  # كل 5 ساعات لعبة = 15 دقيقة حقيقية
DISASTER_EVERY  = WEEK_REAL      # كارثة كل أسبوع لعبة = 21 دقيقة حقيقية
SHIP_MIN        = HOUR_REAL * 2  # أقل وقت شحن = 2 ساعة لعبة = 6 دقائق
SHIP_MAX        = HOUR_REAL * 6  # أقصى وقت شحن = 6 ساعات لعبة = 18 دقيقة

FLAG_SIZE_MAIN  = 200
FLAG_SIZE_SMALL = 100

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

# ==================== إحداثيات الدول ====================
REGION_COORDS = {
    "مصر":       [(378,  1077)],
    "تركيا":     [(532,  407),  (192,  306)],
    "إيران":     [(1267, 642)],
    "الأردن":    [(662,  906)],
    "قطر":       [(1331, 1187)],
    "الإمارات":  [(1482, 1288)],
    "عُمان":     [(1610, 1509), (1549, 1149)],
    "فلسطين":    [(594,  844)],
    "الكويت":    [(1130, 948)],
    "العراق":    [(957,  749)],
    "السعودية":  [(1080, 1246)],
    "اليمن":     [(1206, 1703)],
    "لبنان":     [(614,  692)],
    "سوريا":     [(726,  618)],
    "البحرين":   [(1010, 1080)],
    "ليبيا":     [(150,  700)],
    "السودان":   [(350,  1300)],
    "إسرائيل":  [(580,  870)],
}
AVAILABLE_REGIONS = list(REGION_COORDS.keys())

# ==================== المضائق ====================
STRAITS = {
    "هرمز": {
        "emoji": "⚓",
        "controller": ["عُمان", "إيران"],   # الدول اللي تتحكم فيه
        "affects": ["السعودية", "الكويت", "العراق", "قطر", "الإمارات", "البحرين"],  # الدول المتأثرة
        "blocked": False,
        "blocked_by": None,
    },
    "باب المندب": {
        "emoji": "🚢",
        "controller": ["اليمن"],
        "affects": ["مصر", "السودان", "الأردن"],
        "blocked": False,
        "blocked_by": None,
    },
}

# ==================== الموارد ====================
# الموارد الأساسية لكل منطقة
REGION_RESOURCES = {
    "السعودية":  ["نفط", "غاز"],
    "الكويت":    ["نفط", "غاز"],
    "العراق":    ["نفط", "غاز"],
    "قطر":       ["غاز", "نفط"],
    "ليبيا":     ["نفط"],
    "إيران":     ["نفط", "غاز", "صلب"],
    "الإمارات":  ["ذهب", "غاز"],
    "البحرين":   ["ذهب"],
    "مصر":       ["قمح", "أرز", "فول"],
    "سوريا":     ["قمح", "زيتون"],
    "السودان":   ["قمح", "ذهب"],
    "اليمن":     ["بن", "فول"],
    "تركيا":     ["قمح", "بطاطس", "صلب"],
    "الأردن":    ["بطاطس", "زيتون"],
    "فلسطين":    ["زيتون", "فول"],
    "لبنان":     ["زيتون", "ذهب"],
    "إسرائيل":  ["صلب", "قمح"],
    "عُمان":     ["نفط", "غاز"],
}

# ==================== المنشآت الصناعية ====================
# (نفط، غاز، صلب، ذهب) — تكلفة ثابتة
RESOURCE_FACILITIES = {
    "نفط":  {"name": "🛢️ مصفى نفط",   "base_cost": 2000, "produces": "نفط",  "amount": 3, "emoji": "🛢️"},
    "غاز":  {"name": "⛽ محطة غاز",    "base_cost": 1800, "produces": "غاز",  "amount": 3, "emoji": "⛽"},
    "صلب":  {"name": "⚙️ مصنع صلب",   "base_cost": 2500, "produces": "صلب",  "amount": 2, "emoji": "⚙️"},
    "ذهب":  {"name": "🏦 بنك مركزي",   "base_cost": 3000, "produces": "ذهب",  "amount": 2, "emoji": "🏦"},
}

# ==================== المزارع الزراعية ====================
# (محاصيل) — تكلفة ديناميكية حسب السوق
FARM_CROPS = {
    "قمح":    {"name": "🌾 حقل قمح",       "base_cost": 400,  "amount": 5, "emoji": "🌾"},
    "أرز":    {"name": "🍚 حقل أرز",       "base_cost": 350,  "amount": 5, "emoji": "🍚"},
    "فول":    {"name": "🫘 حقل فول",       "base_cost": 300,  "amount": 6, "emoji": "🫘"},
    "بن":     {"name": "☕ مزرعة بن",      "base_cost": 450,  "amount": 4, "emoji": "☕"},
    "بطاطس":  {"name": "🥔 حقل بطاطس",    "base_cost": 250,  "amount": 7, "emoji": "🥔"},
    "زيتون":  {"name": "🫒 بستان زيتون",   "base_cost": 350,  "amount": 5, "emoji": "🫒"},
}

# الموارد الزراعية المفضلة لكل منطقة (بتظهر أول في القائمة)
REGION_PREFERRED_CROPS = {
    "مصر":      ["قمح", "أرز", "فول"],
    "سوريا":    ["قمح", "زيتون"],
    "السودان":  ["قمح", "فول"],
    "اليمن":    ["بن", "فول"],
    "تركيا":    ["قمح", "بطاطس"],
    "الأردن":   ["بطاطس", "زيتون"],
    "فلسطين":   ["زيتون", "فول"],
    "لبنان":    ["زيتون", "بن"],
    "إسرائيل": ["قمح", "بطاطس"],
}

ALL_CROPS = list(FARM_CROPS.keys())

def get_farm_cost(data, crop):
    """تكلفة الحقل = base_cost × معامل الطلب في السوق"""
    base   = FARM_CROPS[crop]["base_cost"]
    market = data.get("market", [])
    supply = sum(o["qty"] for o in market if o.get("resource") == crop)
    # لو العرض قليل → الطلب عالي → الحقل أغلى (الكل عايز يزرعه)
    if supply == 0:    factor = 1.5
    elif supply < 5:   factor = 1.25
    elif supply < 15:  factor = 1.0
    elif supply < 30:  factor = 0.85
    else:              factor = 0.7
    return max(150, int(base * factor))

# الأسعار الأساسية (بتتغير حسب العرض والطلب)
BASE_PRICES = {
    "نفط":    800,
    "غاز":    600,
    "صلب":    500,
    "ذهب":    1000,
    "بن":     350,
    "زيتون":  300,
    "أرز":    250,
    "قمح":    200,
    "فول":    180,
    "بطاطس":  150,
}

# ==================== الكوارث ====================
DISASTERS = [
    {"name": "زلزال مدمر",     "emoji": "🌍", "effect": "army",      "loss": (0.2, 0.4), "msg": "ضرب زلزال مدمر! خسرت جزء من جيشك!"},
    {"name": "فيضانات",        "emoji": "🌊", "effect": "facilities","loss": (1, 2),     "msg": "فيضانات دمرت بعض منشآتك!"},
    {"name": "جفاف شديد",      "emoji": "☀️", "effect": "resources", "loss": (0.3, 0.5), "msg": "جفاف أتلف مخزون موارد دولتك!"},
    {"name": "وباء",           "emoji": "🦠", "effect": "army",      "loss": (0.1, 0.3), "msg": "وباء اجتاح جيشك!"},
    {"name": "حريق مصانع",     "emoji": "🔥", "effect": "facilities","loss": (1, 1),     "msg": "حريق دمر إحدى منشآتك!"},
    {"name": "انهيار اقتصادي", "emoji": "📉", "effect": "gold",      "loss": (0.1, 0.2), "msg": "انهيار اقتصادي! خسرت جزء من ذهبك!"},
]

# ==================== نظام المستويات ====================
LEVELS = [
    {"level": 1, "name": "قرية",          "xp": 0,     "emoji": "🏘️"},
    {"level": 2, "name": "مدينة ناشئة",   "xp": 500,   "emoji": "🏙️"},
    {"level": 3, "name": "إمارة",         "xp": 1500,  "emoji": "🏰"},
    {"level": 4, "name": "مملكة",         "xp": 3000,  "emoji": "👑"},
    {"level": 5, "name": "إمبراطورية",    "xp": 6000,  "emoji": "🌟"},
    {"level": 6, "name": "قوة عظمى",      "xp": 12000, "emoji": "⚡"},
    {"level": 7, "name": "حضارة متقدمة", "xp": 25000, "emoji": "🚀"},
]

def get_level(xp):
    cur = LEVELS[0]
    for l in LEVELS:
        if xp >= l["xp"]: cur = l
        else: break
    return cur

def get_next_level(xp):
    for l in LEVELS:
        if xp < l["xp"]: return l
    return None

def add_xp(data, user_id, amount):
    old = data["players"][str(user_id)].get("xp", 0)
    new = old + amount
    data["players"][str(user_id)]["xp"] = new
    return get_level(new)["level"] > get_level(old)["level"], get_level(new)

# ==================== حساب الأسعار الديناميكية ====================
def get_current_price(data, resource):
    base  = BASE_PRICES.get(resource, 200)
    market= data.get("market", [])
    # كمية المعروض من هذا المورد في السوق
    supply = sum(o["qty"] for o in market if o.get("resource") == resource)
    # كلما زاد العرض، انخفض السعر (وبالعكس)
    if supply == 0:
        factor = 1.3   # ندرة → سعر أعلى
    elif supply < 5:
        factor = 1.1
    elif supply < 15:
        factor = 1.0
    elif supply < 30:
        factor = 0.85
    else:
        factor = 0.7   # فائض → سعر أقل
    return max(50, int(base * factor))

# ==================== تحميل/حفظ ====================
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
            if "market" not in d:        d["market"] = []
            if "shipments" not in d:     d["shipments"] = []
            if "straits" not in d:       d["straits"] = {k: {"blocked": False, "blocked_by": None} for k in STRAITS}
            if "last_disaster" not in d: d["last_disaster"] = 0
            return d
    return {"players": {}, "pending_codes": {}, "unclaimed_lands": {},
            "market": [], "shipments": [], "last_disaster": 0,
            "straits": {k: {"blocked": False, "blocked_by": None} for k in STRAITS}}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def generate_code():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

def get_player(data, user_id):
    return data["players"].get(str(user_id))

def is_admin(user_id):
    return user_id == ADMIN_ID

def find_player_by_code(data, code):
    for uid, p in data["players"].items():
        if p.get("player_code") == code.upper():
            return uid, p
    return None, None

def get_strait_status(data):
    """يرجع حالة المضائق"""
    result = {}
    for name, info in STRAITS.items():
        saved = data["straits"].get(name, {})
        result[name] = {**info, "blocked": saved.get("blocked", False), "blocked_by": saved.get("blocked_by")}
    return result

def is_shipment_blocked(data, seller_region, buyer_region):
    """يتحقق لو الشحنة هتتأخر بسبب مضيق مغلق"""
    straits = get_strait_status(data)
    for name, s in straits.items():
        if s["blocked"]:
            if seller_region in s["affects"] or buyer_region in s["affects"]:
                return True, name
    return False, None

def calc_ship_time(seller_region, buyer_region):
    """يحسب وقت الشحن بالثواني (بيرجع وقت حقيقي)"""
    base = random.randint(int(SHIP_MIN), int(SHIP_MAX))
    return base

# ==================== الخريطة ====================
def generate_map(players, data):
    img  = Image.open(MAP_FILE).convert("RGBA")
    draw = ImageDraw.Draw(img)
    straits = get_strait_status(data)

    for uid, p in players.items():
        region    = p.get("region")
        cname     = p.get("country_name", region)
        flag_path = os.path.join(FLAGS_DIR, f"{region}.png")
        if region not in REGION_COORDS: continue
        for i, (cx, cy) in enumerate(REGION_COORDS[region]):
            size = FLAG_SIZE_MAIN if i == 0 else FLAG_SIZE_SMALL
            if os.path.exists(flag_path):
                flag = Image.open(flag_path).convert("RGBA")
                flag = flag.resize((size, int(size*0.6)), Image.LANCZOS)
                fw, fh = flag.size; fx, fy = cx-fw//2, cy-fh//2
                img.paste(flag, (fx, fy), flag)
                draw.rectangle([fx-3,fy-3,fx+fw+3,fy+fh+3], outline="white", width=4)
                if i == 0:
                    lvl   = get_level(p.get("xp", 0))
                    draw.text((cx, fy+fh+6), f"{lvl['emoji']} {cname}", fill="black", anchor="mt")
            else:
                r = 30 if i == 0 else 15
                draw.ellipse([cx-r,cy-r,cx+r,cy+r], fill="#e74c3c", outline="white", width=3)
                if i == 0:
                    draw.text((cx, cy+r+6), cname, fill="black", anchor="mt")

    # رسم المضائق
    strait_positions = {"هرمز": (1400, 1050), "باب المندب": (1100, 1550)}
    for name, pos in strait_positions.items():
        s   = straits.get(name, {})
        col = "red" if s.get("blocked") else "cyan"
        cx, cy = pos
        draw.ellipse([cx-20,cy-20,cx+20,cy+20], fill=col, outline="white", width=3)
        draw.text((cx, cy+25), f"{'🔴' if s.get('blocked') else '🟢'}{name}", fill="white", anchor="mt")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

# ==================== كوارث تلقائية ====================
async def disaster_loop(app):
    """تشغيل كوارث تلقائية كل أسبوع لعبة = 21 دقيقة"""
    await asyncio.sleep(DISASTER_EVERY)
    while True:
        try:
            data = load_data()
            if data["players"]:
                # اختيار دولة عشوائية
                uid  = random.choice(list(data["players"].keys()))
                p    = data["players"][uid]
                d    = random.choice(DISASTERS)
                loss = 0

                if d["effect"] == "army":
                    pct  = random.uniform(*d["loss"])
                    loss = max(10, int(p["army"] * pct))
                    data["players"][uid]["army"] = max(0, p["army"] - loss)
                elif d["effect"] == "gold":
                    pct  = random.uniform(*d["loss"])
                    loss = max(50, int(p["gold"] * pct))
                    data["players"][uid]["gold"] = max(0, p["gold"] - loss)
                elif d["effect"] == "facilities":
                    facs = p.get("facilities", {})
                    if facs:
                        res  = random.choice(list(facs.keys()))
                        loss = random.randint(1, min(2, facs[res]))
                        data["players"][uid]["facilities"][res] = max(0, facs[res] - loss)
                        if data["players"][uid]["facilities"][res] == 0:
                            del data["players"][uid]["facilities"][res]
                elif d["effect"] == "resources":
                    inv = p.get("inventory", {})
                    if inv:
                        res = random.choice(list(inv.keys()))
                        pct = random.uniform(*d["loss"])
                        loss = max(1, int(inv[res] * pct))
                        data["players"][uid]["inventory"][res] = max(0, inv[res] - loss)

                data["last_disaster"] = time.time()
                save_data(data)

                try:
                    await app.bot.send_message(
                        chat_id=int(uid),
                        text=f"{d['emoji']} *كارثة طبيعية ضربت {p['country_name']}!*\n\n{d['msg']}\n💔 الخسارة: {loss}",
                        parse_mode="Markdown"
                    )
                except: pass

        except Exception as e:
            logging.error(f"Disaster loop error: {e}")

        await asyncio.sleep(DISASTER_EVERY)

# ==================== شحنات ====================
async def shipment_loop(app):
    """يتحقق من الشحنات الواصلة كل دقيقة"""
    while True:
        await asyncio.sleep(60)
        try:
            data     = load_data()
            now      = time.time()
            arrived  = [s for s in data["shipments"] if s["arrive_at"] <= now]
            pending  = [s for s in data["shipments"] if s["arrive_at"] > now]

            for s in arrived:
                buyer_uid = s["buyer_uid"]
                if buyer_uid in data["players"]:
                    inv = data["players"][buyer_uid].get("inventory", {})
                    inv[s["resource"]] = inv.get(s["resource"], 0) + s["qty"]
                    data["players"][buyer_uid]["inventory"] = inv
                    try:
                        await app.bot.send_message(
                            chat_id=int(buyer_uid),
                            text=f"📦 *وصلت شحنتك!*\n\n{s['qty']} وحدة من *{s['resource']}* وصلت من {s['seller']}! ✅",
                            parse_mode="Markdown"
                        )
                    except: pass

            data["shipments"] = pending
            save_data(data)
        except Exception as e:
            logging.error(f"Shipment loop error: {e}")

# ==================== معالج الرسائل ====================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text:
        text = update.message.text.strip()
    elif update.message.caption:
        text = update.message.caption.strip()
    else:
        text = ""

    user_id   = update.effective_user.id
    user_name = update.effective_user.first_name
    data      = load_data()

    # ======= أدمن: إنشاء دولة مع علم =======
    if is_admin(user_id) and update.message.photo and text.startswith("دولة "):
        parts = text.split()
        if len(parts) < 4:
            await update.message.reply_text("❌ الصيغة:\n`دولة [المنطقة] [اسم] [الكود]`", parse_mode="Markdown"); return
        code = parts[-1].upper(); region = parts[1]; country_name = " ".join(parts[2:-1])
        if code not in data["pending_codes"]:
            await update.message.reply_text(f"❌ الكود `{code}` مش موجود.", parse_mode="Markdown"); return
        if region not in AVAILABLE_REGIONS:
            await update.message.reply_text(f"⚠️ '{region}' مش في القائمة."); return
        for uid, p in data["players"].items():
            if p["region"] == region:
                await update.message.reply_text(f"❌ '{region}' محجوزة."); return
        photo = update.message.photo[-1]
        ff    = await context.bot.get_file(photo.file_id)
        await ff.download_to_drive(os.path.join(FLAGS_DIR, f"{region}.png"))
        player_id   = data["pending_codes"].pop(code)
        player_code = generate_code()
        res         = REGION_RESOURCES.get(region, [])
        data["players"][str(player_id)] = {
            "country_name": country_name, "region": region,
            "gold": 1000, "army": 100, "factories": 1, "farms": 1,
            "territories": 1, "allies": [], "at_war": [],
            "last_tax": 0, "player_code": player_code, "xp": 0,
            "facilities": {}, "inventory": {},
        }
        save_data(data)
        res_txt = "، ".join(res) if res else "لا يوجد"
        await update.message.reply_text(
            f"✅ تم!\n🏳️ *{country_name}* ← {region}\n"
            f"🔑 كود اللاعب: `{player_code}`\n"
            f"🌍 موارد المنطقة: {res_txt}",
            parse_mode="Markdown")
        try:
            await context.bot.send_message(chat_id=player_id,
                text=f"🎉 دولتك اتفعّلت!\n🏳️ *{country_name}* ← {region}\n"
                     f"🌍 موارد منطقتك: {res_txt}\n\nاكتب *مساعدة*", parse_mode="Markdown")
        except: pass
        return

    # ======= انشاء دولة =======
    if text == "انشاء دولة":
        player = get_player(data, user_id)
        if player:
            await update.message.reply_text(f"⚠️ عندك دولة: *{player['country_name']}*", parse_mode="Markdown"); return
        existing = next((c for c, uid in data["pending_codes"].items() if uid == user_id), None)
        if existing:
            await update.message.reply_text(f"⏳ كودك: `{existing}`", parse_mode="Markdown"); return
        code = generate_code()
        while code in data["pending_codes"]: code = generate_code()
        data["pending_codes"][code] = user_id; save_data(data)
        await update.message.reply_text(f"🎮 أهلاً {user_name}!\nكودك:\n```\n{code}\n```\nابعته للأدمن.", parse_mode="Markdown")
        return

    # ======= كودي =======
    if text in ["كودي", "الكود"]:
        player = get_player(data, user_id)
        if not player:
            await update.message.reply_text("❌ مش مسجل."); return
        await update.message.reply_text(f"🔑 كودك:\n```\n{player.get('player_code','')}```", parse_mode="Markdown")
        return

    # ======= حالة دولتي =======
    if text in ["حالة دولتي", "دولتي", "وضعي"]:
        player = get_player(data, user_id)
        if not player:
            await update.message.reply_text("❌ مش مسجل."); return
        p   = player
        xp  = p.get("xp", 0)
        lvl = get_level(xp)
        nxt = get_next_level(xp)
        nxt_txt = f"{nxt['xp']-xp:,} XP للمستوى القادم" if nxt else "🏆 أعلى مستوى!"
        left = TAX_COOLDOWN - (time.time() - p.get("last_tax", 0))
        tax  = "✅ جاهزة" if left <= 0 else f"⏳ {int(left//60)}:{int(left%60):02d}"

        # المنشآت
        facs = p.get("facilities", {})
        fac_txt = "\n".join(f"  {RESOURCE_FACILITIES[r]['emoji']} {RESOURCE_FACILITIES[r]['name']}: {c}" for r, c in facs.items()) if facs else "  لا يوجد"

        # المخزون
        inv     = p.get("inventory", {})
        inv_txt = " | ".join(f"{r}: {q}" for r, q in inv.items()) if inv else "فارغ"

        res      = REGION_RESOURCES.get(p["region"], [])
        crops_p  = p.get("crops", {})
        crops_txt = "\n".join(f"  {FARM_CROPS[c]['emoji']} {FARM_CROPS[c]['name']}: {n}" for c, n in crops_p.items()) if crops_p else "  لا يوجد"
        await update.message.reply_text(
            f"{lvl['emoji']} *{p['country_name']}* — Lv.{lvl['level']}: {lvl['name']}\n"
            f"⭐ {xp:,} XP | {nxt_txt}\n\n"
            f"🗺️ المنطقة: {p['region']}\n"
            f"🌍 الموارد الطبيعية: {', '.join(res)}\n\n"
            f"💰 ذهب: {p['gold']:,}\n⚔️ جيش: {p['army']:,}\n"
            f"🗺️ أراضي: {p['territories']}\n\n"
            f"🏭 المنشآت الصناعية:\n{fac_txt}\n\n"
            f"🌾 المزارع:\n{crops_txt}\n\n"
            f"📦 المخزون: {inv_txt}\n\n"
            f"💵 جمع الضرائب: {tax}\n"
            f"🤝 تحالفات: {', '.join(p['allies']) if p['allies'] else 'لا يوجد'}", parse_mode="Markdown")
        return

    # ======= بناء منشأة صناعية =======
    if text in ["بناء منشأة", "بناء منشأه", "انشئ منشأة"]:
        player = get_player(data, user_id)
        if not player:
            await update.message.reply_text("❌ مش مسجل."); return
        region    = player["region"]
        res_avail = [r for r in REGION_RESOURCES.get(region, []) if r in RESOURCE_FACILITIES]
        if not res_avail:
            await update.message.reply_text(
                f"❌ منطقتك ({region}) ما عندهاش موارد صناعية.\nجرب *بناء مزرعة* بدلاً من ذلك.", parse_mode="Markdown"); return
        keyboard = []
        for r in res_avail:
            f = RESOURCE_FACILITIES[r]
            keyboard.append([InlineKeyboardButton(
                f"{f['emoji']} {f['name']} — {f['base_cost']:,} ذهب | +{f['amount']} {r}/دورة",
                callback_data=f"build_{r}"
            )])
        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="cancel")])
        await update.message.reply_text(
            f"🏗️ *اختار المنشأة الصناعية:*\n\n"
            f"الموارد الصناعية في {region}: {', '.join(res_avail)}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown")
        return

    # ======= بناء مزرعة =======
    if text in ["بناء مزرعة", "ابني مزرعة", "انشئ مزرعة"]:
        player = get_player(data, user_id)
        if not player:
            await update.message.reply_text("❌ مش مسجل."); return
        region    = player["region"]
        preferred = REGION_PREFERRED_CROPS.get(region, [])
        sorted_crops = preferred + [c for c in ALL_CROPS if c not in preferred]
        keyboard = []
        row = []
        for crop in sorted_crops:
            fc   = FARM_CROPS[crop]
            cost = get_farm_cost(data, crop)
            star = "⭐" if crop in preferred else ""
            btn  = InlineKeyboardButton(
                f"{fc['emoji']}{star} {crop} — {cost:,}ذ | +{fc['amount']}/دورة",
                callback_data=f"farm_{crop}"
            )
            row.append(btn)
            if len(row) == 2:
                keyboard.append(row); row = []
        if row: keyboard.append(row)
        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="cancel")])
        pref_txt = f"⭐ مناسب لمنطقتك: {', '.join(preferred)}" if preferred else "يمكنك زراعة أي محصول"
        await update.message.reply_text(
            f"🌾 *اختار المحصول:*\n\n"
            f"{pref_txt}\n\n"
            f"💡 السعر بيتغير حسب العرض والطلب\n"
            f"⭐ = محصول طبيعي لمنطقتك (إنتاج أعلى بـ 50%)",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown")
        return

    # ======= جمع الضرائب =======
    if text in ["جمع الضرائب", "اجمع الضرائب", "جمع موارد"]:
        player = get_player(data, user_id)
        if not player:
            await update.message.reply_text("❌ مش مسجل."); return
        now  = time.time()
        left = TAX_COOLDOWN - (now - player.get("last_tax", 0))
        if left > 0:
            await update.message.reply_text(f"⏳ استنى *{int(left//60)}:{int(left%60):02d}* دقيقة!", parse_mode="Markdown"); return

        # الدخل الأساسي
        income    = player["territories"]*50 + 200
        xp_gained = 50 + player["territories"]*10
        inv       = player.get("inventory", {})
        prod_txt  = ""
        farm_txt  = ""

        # إنتاج المنشآت الصناعية
        facs = player.get("facilities", {})
        for res, count in facs.items():
            if res in RESOURCE_FACILITIES:
                f   = RESOURCE_FACILITIES[res]
                qty = f["amount"] * count
                inv[res] = inv.get(res, 0) + qty
                prod_txt += f"\n  {f['emoji']} +{qty} {res}"

        # إنتاج المزارع الزراعية
        crops_inv    = player.get("crops", {})
        crops_amount = player.get("crops_amount", {})
        for crop, count in crops_inv.items():
            if crop in FARM_CROPS:
                fc  = FARM_CROPS[crop]
                # استخدم الكمية المحسوبة (مع بونص المنطقة لو موجود)
                amt_per = crops_amount.get(crop, fc["amount"])
                qty     = amt_per * count
                inv[crop] = inv.get(crop, 0) + qty
                farm_txt += f"\n  {fc['emoji']} +{qty} {crop}"

        data["players"][str(user_id)]["gold"]     += income
        data["players"][str(user_id)]["last_tax"]  = now
        data["players"][str(user_id)]["inventory"] = inv
        leveled_up, new_lvl = add_xp(data, user_id, xp_gained)
        save_data(data)

        msg = (f"💰 *تم جمع الموارد!*\n\n"
               f"🗺️ أراضي: +{player['territories']*50:,}\n"
               f"👑 أساسي: +200\n"
               f"✅ ذهب: +{income:,} | رصيد: {player['gold']+income:,}\n")
        if prod_txt:
            msg += f"\n🏭 *إنتاج المنشآت:*{prod_txt}"
        if farm_txt:
            msg += f"\n🌾 *إنتاج المزارع:*{farm_txt}"
        if not prod_txt and not farm_txt:
            msg += f"\n💡 ابنِ *منشآت* أو *مزارع* لإنتاج الموارد!"
        msg += f"\n\n⭐ XP: +{xp_gained}\n⏳ القادم بعد 15 دقيقة"
        if leveled_up:
            msg += f"\n\n🎉 *ترقية!* {new_lvl['name']} {new_lvl['emoji']}"
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    # ======= السوق =======
    if text in ["السوق", "سوق", "العروض"]:
        market = data.get("market", [])
        if not market:
            await update.message.reply_text(
                "🏪 *السوق فاضي.*\n\nلإضافة عرض:\n`عرض [مورد] [الكمية] [السعر]`\nمثال: `عرض نفط 5 750`",
                parse_mode="Markdown"); return
        msg = "🏪 *السوق التجاري:*\n\n"
        # تجميع حسب المورد
        by_resource = {}
        for o in market:
            r = o.get("resource", "؟")
            if r not in by_resource: by_resource[r] = []
            by_resource[r].append(o)
        for r, offers in by_resource.items():
            cur_price = get_current_price(data, r)
            msg += f"*{r}* — السعر الحالي: {cur_price:,} ذهب/وحدة\n"
            for o in offers[:3]:
                msg += f"  • `{o['id']}` — {o['qty']} وحدة من {o['seller']} بـ {o['price']:,}\n"
            msg += "\n"
        msg += "للشراء: `شراء [كود العرض]`"
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    # ======= عرض مورد للبيع =======
    if text.startswith("عرض "):
        player = get_player(data, user_id)
        if not player:
            await update.message.reply_text("❌ مش مسجل."); return
        parts = text.split()
        if len(parts) != 4:
            await update.message.reply_text("❌ الصيغة:\n`عرض [مورد] [الكمية] [السعر]`\nمثال: `عرض نفط 5 750`", parse_mode="Markdown"); return
        resource = parts[1]; qty = parts[2]; price = parts[3]
        try:
            qty = int(qty); price = int(price)
            if qty <= 0 or price <= 0: raise ValueError
        except:
            await update.message.reply_text("❌ الكمية والسعر لازم أرقام موجبة."); return
        inv = player.get("inventory", {})
        if inv.get(resource, 0) < qty:
            await update.message.reply_text(f"❌ مخزونك من {resource}: {inv.get(resource,0)} فقط."); return
        cur_price = get_current_price(data, resource)
        data["players"][str(user_id)]["inventory"][resource] -= qty
        if data["players"][str(user_id)]["inventory"][resource] == 0:
            del data["players"][str(user_id)]["inventory"][resource]
        offer_id = generate_code()
        data["market"].append({"id": offer_id, "seller_uid": str(user_id), "seller": player["country_name"],
                                "resource": resource, "qty": qty, "price": price})
        save_data(data)
        await update.message.reply_text(
            f"🏪 تم عرض *{qty} {resource}* بسعر *{price:,}* ذهب!\n"
            f"📊 السعر السوقي الحالي: {cur_price:,}\n"
            f"كود العرض: `{offer_id}`", parse_mode="Markdown")
        return

    # ======= شراء من السوق =======
    if text.startswith("شراء "):
        player = get_player(data, user_id)
        if not player:
            await update.message.reply_text("❌ مش مسجل."); return
        offer_id = text.replace("شراء","").strip().upper()
        market   = data.get("market", [])
        offer    = next((o for o in market if o["id"] == offer_id), None)
        if not offer:
            await update.message.reply_text(f"❌ مش لاقي عرض `{offer_id}`."); return
        if offer["seller_uid"] == str(user_id):
            await update.message.reply_text("❌ مينفعش تشتري عرضك!"); return
        if player["gold"] < offer["price"]:
            await update.message.reply_text(f"❌ محتاج {offer['price']:,}. عندك {player['gold']:,}."); return

        # حساب وقت الشحن
        seller_p    = data["players"].get(offer["seller_uid"], {})
        seller_reg  = seller_p.get("region", "")
        buyer_reg   = player["region"]
        ship_time   = calc_ship_time(seller_reg, buyer_reg)
        blocked, strait_name = is_shipment_blocked(data, seller_reg, buyer_reg)
        if blocked:
            ship_time = int(ship_time * 2)  # تأخير ضعف في حالة إغلاق المضيق

        data["players"][str(user_id)]["gold"] -= offer["price"]
        if offer["seller_uid"] in data["players"]:
            data["players"][offer["seller_uid"]]["gold"] += offer["price"]
        data["market"] = [o for o in market if o["id"] != offer_id]

        # إضافة شحنة
        arrive_at = time.time() + ship_time
        data["shipments"].append({
            "buyer_uid": str(user_id), "seller": offer["seller"],
            "resource": offer["resource"], "qty": offer["qty"],
            "arrive_at": arrive_at
        })
        save_data(data)

        mins = int(ship_time // 60)
        block_txt = f"\n⚠️ *تأخير بسبب إغلاق مضيق {strait_name}!*" if blocked else ""
        await update.message.reply_text(
            f"✅ اشتريت *{offer['qty']} {offer['resource']}* من *{offer['seller']}*!\n"
            f"💰 دفعت: {offer['price']:,} ذهب\n"
            f"🚢 الشحنة في الطريق...\n"
            f"⏱️ وصول بعد ~{mins} دقيقة{block_txt}",
            parse_mode="Markdown")
        try:
            await context.bot.send_message(chat_id=int(offer["seller_uid"]),
                text=f"💰 *{player['country_name']}* اشترى {offer['qty']} {offer['resource']}!\nاستلمت {offer['price']:,} ذهب.", parse_mode="Markdown")
        except: pass
        return

    # ======= إغلاق/فتح مضيق =======
    if text.startswith("أغلق مضيق ") or text.startswith("افتح مضيق "):
        player = get_player(data, user_id)
        if not player:
            await update.message.reply_text("❌ مش مسجل."); return
        action      = "أغلق" if text.startswith("أغلق") else "افتح"
        strait_name = text.replace("أغلق مضيق","").replace("افتح مضيق","").strip()
        if strait_name not in STRAITS:
            await update.message.reply_text(f"❌ المضائق المتاحة: {', '.join(STRAITS.keys())}"); return
        controllers = STRAITS[strait_name]["controller"]
        if player["region"] not in controllers:
            await update.message.reply_text(f"❌ دولتك مش متحكمة في مضيق {strait_name}.\nالمتحكمون: {', '.join(controllers)}"); return

        if action == "أغلق":
            data["straits"][strait_name] = {"blocked": True, "blocked_by": player["country_name"]}
            save_data(data)
            await update.message.reply_text(f"🔴 تم إغلاق مضيق *{strait_name}*!\nكل الشحنات المارة هتتأخر ضعف الوقت!", parse_mode="Markdown")
        else:
            data["straits"][strait_name] = {"blocked": False, "blocked_by": None}
            save_data(data)
            await update.message.reply_text(f"🟢 تم فتح مضيق *{strait_name}*!", parse_mode="Markdown")
        return

    # ======= حالة المضائق =======
    if text in ["المضائق", "حالة المضائق"]:
        straits = get_strait_status(data)
        msg = "⚓ *حالة المضائق:*\n\n"
        for name, s in straits.items():
            status = f"🔴 مغلق بواسطة {s['blocked_by']}" if s.get("blocked") else "🟢 مفتوح"
            msg += f"*{name}*: {status}\nالمتأثرون: {', '.join(s['affects'])}\n\n"
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    # ======= تجنيد =======
    if text.startswith("تجنيد "):
        player = get_player(data, user_id)
        if not player:
            await update.message.reply_text("❌ مش مسجل."); return
        try:
            amount = int(text.replace("تجنيد","").strip())
            if amount <= 0: raise ValueError
            cost = amount * 10
            if player["gold"] < cost:
                await update.message.reply_text(f"❌ يكلف {cost:,}. عندك {player['gold']:,}."); return
            data["players"][str(user_id)]["gold"] -= cost
            data["players"][str(user_id)]["army"] += amount
            leveled_up, new_lvl = add_xp(data, user_id, amount//10)
            save_data(data)
            msg = f"⚔️ تم تجنيد {amount:,}!\nالجيش: {player['army']+amount:,} | الذهب: {player['gold']-cost:,}"
            if leveled_up: msg += f"\n🎉 *ترقية!* {new_lvl['name']} {new_lvl['emoji']}"
            await update.message.reply_text(msg, parse_mode="Markdown")
        except: await update.message.reply_text("❌ مثال: تجنيد 100")
        return

    # ======= هجوم =======
    if text.startswith("هجوم على "):
        player = get_player(data, user_id)
        if not player:
            await update.message.reply_text("❌ مش مسجل."); return
        target_name = text.replace("هجوم على","").strip()
        target_player, target_uid = None, None
        for uid, p in data["players"].items():
            if p["country_name"] == target_name or p["region"] == target_name:
                target_player, target_uid = p, uid; break
        if not target_player:
            await update.message.reply_text(f"❌ مش لاقي '{target_name}'."); return
        if target_uid == str(user_id):
            await update.message.reply_text("❌ مينفعش تهاجم نفسك!"); return
        if target_player["country_name"] in player.get("allies", []):
            await update.message.reply_text(f"❌ {target_player['country_name']} حليفك!"); return
        att  = player["army"] * random.uniform(0.7, 1.3)
        deff = target_player["army"] * random.uniform(0.7, 1.3)
        if att > deff:
            loot = min(target_player["gold"]//3, 500)
            la, ld = random.randint(10,50), random.randint(50,150)
            data["players"][str(user_id)]["gold"]        += loot
            data["players"][str(user_id)]["territories"] += 1
            data["players"][str(user_id)]["army"]         = max(0, player["army"]-la)
            data["players"][target_uid]["gold"]           -= loot
            data["players"][target_uid]["territories"]    = max(1, target_player["territories"]-1)
            data["players"][target_uid]["army"]           = max(0, target_player["army"]-ld)
            leveled_up, new_lvl = add_xp(data, user_id, 200)
            save_data(data)
            msg = f"⚔️ *انتصار!*\n🏆 هزمت {target_player['country_name']}\n💰 غنيمة: {loot:,}\n💀 خسائرك: {la} | العدو: {ld}\n⭐+200 XP"
            if leveled_up: msg += f"\n🎉 *ترقية!* {new_lvl['name']} {new_lvl['emoji']}"
            await update.message.reply_text(msg, parse_mode="Markdown")
            try: await context.bot.send_message(chat_id=int(target_uid), text=f"⚠️ *{player['country_name']} هاجمك!*\nخسرت {loot:,} ذهب | خسائر: {ld}", parse_mode="Markdown")
            except: pass
        else:
            la, ld = random.randint(50,200), random.randint(10,50)
            data["players"][str(user_id)]["army"] = max(0, player["army"]-la)
            data["players"][target_uid]["army"]   = max(0, target_player["army"]-ld)
            save_data(data)
            await update.message.reply_text(f"⚔️ *هزيمة!*\n❌ انهزمت أمام {target_player['country_name']}\n💀 خسائرك: {la} | العدو: {ld}", parse_mode="Markdown")
        return

    # ======= تحالف =======
    if text.startswith("تحالف مع "):
        player = get_player(data, user_id)
        if not player:
            await update.message.reply_text("❌ مش مسجل."); return
        target_name = text.replace("تحالف مع","").strip()
        for uid, p in data["players"].items():
            if p["country_name"] == target_name or p["region"] == target_name:
                if p["country_name"] in player.get("allies",[]): await update.message.reply_text("✅ حليف بالفعل."); return
                data["players"][str(user_id)]["allies"].append(p["country_name"])
                data["players"][uid]["allies"].append(player["country_name"]); save_data(data)
                await update.message.reply_text(f"🤝 تم التحالف مع *{p['country_name']}*!", parse_mode="Markdown")
                try: await context.bot.send_message(chat_id=int(uid), text=f"🤝 *{player['country_name']}* أعلن التحالف معك!", parse_mode="Markdown")
                except: pass
                return
        await update.message.reply_text(f"❌ مش لاقي '{target_name}'."); return

    # ======= تحويل ذهب =======
    if text.startswith("تحويل "):
        player = get_player(data, user_id)
        if not player:
            await update.message.reply_text("❌ مش مسجل."); return
        parts = text.split()
        if len(parts) != 3:
            await update.message.reply_text("❌ الصيغة:\n`تحويل [المبلغ] [كود اللاعب]`", parse_mode="Markdown"); return
        try: amount = int(parts[1]); assert amount > 0
        except: await update.message.reply_text("❌ المبلغ لازم رقم موجب."); return
        if player["gold"] < amount:
            await update.message.reply_text(f"❌ عندك {player['gold']:,} بس."); return
        target_uid, target_player = find_player_by_code(data, parts[2])
        if not target_player:
            await update.message.reply_text(f"❌ مش لاقي لاعب."); return
        if target_uid == str(user_id):
            await update.message.reply_text("❌ مينفعش تحول لنفسك!"); return
        data["players"][str(user_id)]["gold"] -= amount
        data["players"][target_uid]["gold"]   += amount; save_data(data)
        await update.message.reply_text(f"💸 تم تحويل *{amount:,}* لـ *{target_player['country_name']}*!", parse_mode="Markdown")
        try: await context.bot.send_message(chat_id=int(target_uid), text=f"💰 استلمت *{amount:,}* من *{player['country_name']}*!", parse_mode="Markdown")
        except: pass
        return

    # ======= المتصدرين =======
    if text in ["المتصدرين", "الترتيب"]:
        if not data["players"]:
            await update.message.reply_text("🏆 لا يوجد لاعبين بعد."); return
        sorted_p = sorted(data["players"].items(), key=lambda x: x[1].get("xp",0), reverse=True)
        msg = "🏆 *المتصدرين:*\n\n"
        medals = ["🥇","🥈","🥉"]
        for i, (uid, p) in enumerate(sorted_p[:10]):
            medal = medals[i] if i < 3 else f"{i+1}."
            lvl   = get_level(p.get("xp",0))
            msg  += f"{medal} {lvl['emoji']} *{p['country_name']}* Lv.{lvl['level']} | ⭐{p.get('xp',0):,}\n"
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    # ======= قائمة الدول =======
    if text in ["قائمة الدول", "الدول"]:
        if not data["players"]:
            await update.message.reply_text("🗺️ لا يوجد دول."); return
        msg = "🗺️ *الدول:*\n\n"
        for uid, p in sorted(data["players"].items(), key=lambda x: x[1].get("xp",0), reverse=True):
            lvl = get_level(p.get("xp",0))
            msg += f"{lvl['emoji']} *{p['country_name']}* ({p['region']}) Lv.{lvl['level']} | 💰{p['gold']:,} | ⚔️{p['army']:,}\n"
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    # ======= خريطة =======
    if text in ["خريطة", "الخريطة"]:
        if not data["players"]:
            await update.message.reply_text("🗺️ لا يوجد دول."); return
        await update.message.reply_text("🗺️ جاري التوليد...")
        try:
            buf = generate_map(data["players"], data)
            cap = "🗺️ *خريطة الشرق الأوسط*\n\n"
            for p in data["players"].values():
                lvl = get_level(p.get("xp",0))
                cap += f"{lvl['emoji']} *{p['country_name']}* ← {p['region']}\n"
            await update.message.reply_photo(photo=buf, caption=cap, parse_mode="Markdown")
        except Exception as e: await update.message.reply_text(f"❌ خطأ: {e}")
        return

    # ======= مساعدة =======
    if text in ["مساعدة", "اوامر", "help"]:
        await update.message.reply_text(
            "📖 *أوامر اللعبة:*\n\n"
            "🔹 *انضمام:*\n• `انشاء دولة` | `كودي`\n\n"
            "🔹 *معلومات:*\n• `حالة دولتي` | `قائمة الدول` | `خريطة` | `المتصدرين`\n\n"
            "🔹 *اقتصاد:*\n• `جمع الضرائب` — كل 15 دقيقة\n"
            "• `بناء منشأة` — منشآت إنتاج الموارد\n"
            "• `تحويل 500 [كود]`\n\n"
            "🔹 *جيش:*\n• `تجنيد 100` | `هجوم على [اسم]`\n\n"
            "🔹 *دبلوماسية:*\n• `تحالف مع [اسم]`\n\n"
            "🔹 *السوق:*\n• `السوق` | `عرض نفط 5 750` | `شراء [كود]`\n\n"
            "🔹 *المضائق:*\n• `المضائق` | `أغلق مضيق هرمز` | `افتح مضيق هرمز`",
            parse_mode="Markdown")
        return

    # ======= أوامر الأدمن =======
    if is_admin(user_id):
        if text.startswith("دولة "):
            parts = text.split()
            if len(parts) < 4:
                await update.message.reply_text("❌ الصيغة:\n`دولة [المنطقة] [اسم] [الكود]`", parse_mode="Markdown"); return
            code = parts[-1].upper(); region = parts[1]; country_name = " ".join(parts[2:-1])
            if code not in data["pending_codes"]:
                await update.message.reply_text(f"❌ الكود `{code}` مش موجود.", parse_mode="Markdown"); return
            if region not in AVAILABLE_REGIONS:
                await update.message.reply_text(f"⚠️ '{region}' مش في القائمة."); return
            for uid, p in data["players"].items():
                if p["region"] == region:
                    await update.message.reply_text(f"❌ '{region}' محجوزة."); return
            player_id = data["pending_codes"].pop(code); player_code = generate_code()
            data["players"][str(player_id)] = {
                "country_name": country_name, "region": region, "gold": 1000, "army": 100,
                "factories": 1, "farms": 1, "territories": 1, "allies": [], "at_war": [],
                "last_tax": 0, "player_code": player_code, "xp": 0, "facilities": {}, "inventory": {}
            }
            save_data(data)
            await update.message.reply_text(f"✅ تم!\n🏳️ *{country_name}* ← {region}\n🔑 `{player_code}`", parse_mode="Markdown")
            try: await context.bot.send_message(chat_id=player_id, text=f"🎉 دولتك اتفعّلت!\n🏳️ *{country_name}*\nاكتب *مساعدة*", parse_mode="Markdown")
            except: pass
            return
        if text.startswith("حذف دولة "):
            cname = text.replace("حذف دولة","").strip()
            for uid, p in list(data["players"].items()):
                if p["country_name"] == cname:
                    del data["players"][uid]; save_data(data)
                    await update.message.reply_text(f"✅ تم حذف {cname}."); return
            await update.message.reply_text(f"❌ مش لاقي '{cname}'."); return
        if text in ["الطلبات"]:
            if not data["pending_codes"]:
                await update.message.reply_text("✅ مفيش طلبات."); return
            msg = "📋 *الطلبات:*\n\n" + "\n".join(f"• `{c}` — ID: `{uid}`" for c,uid in data["pending_codes"].items())
            await update.message.reply_text(msg, parse_mode="Markdown"); return

# ======= Callback للأزرار =======
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data    = load_data()
    player  = get_player(data, user_id)

    if query.data == "cancel":
        await query.edit_message_text("❌ تم الإلغاء."); return

    # بناء منشأة صناعية
    if query.data.startswith("build_"):
        resource = query.data.replace("build_","")
        if not player:
            await query.edit_message_text("❌ مش مسجل."); return
        if resource not in RESOURCE_FACILITIES:
            await query.edit_message_text("❌ مورد غير معروف."); return
        f    = RESOURCE_FACILITIES[resource]
        cost = f["base_cost"]
        if player["gold"] < cost:
            await query.edit_message_text(f"❌ محتاج {cost:,} ذهب. عندك {player['gold']:,}."); return
        data["players"][str(user_id)]["gold"] -= cost
        facs = data["players"][str(user_id)].get("facilities", {})
        facs[resource] = facs.get(resource, 0) + 1
        data["players"][str(user_id)]["facilities"] = facs
        leveled_up, new_lvl = add_xp(data, user_id, 120)
        save_data(data)
        msg = (f"🏭 تم بناء *{f['name']}*!\n"
               f"📦 ستنتج *{f['amount']} {resource}* عند كل جمع ضرائب\n"
               f"💰 الذهب المتبقي: {player['gold']-cost:,}\n⭐+120 XP")
        if leveled_up: msg += f"\n🎉 *ترقية!* {new_lvl['name']} {new_lvl['emoji']}"
        await query.edit_message_text(msg, parse_mode="Markdown")

    # زراعة محصول
    elif query.data.startswith("farm_"):
        crop = query.data.replace("farm_","")
        if not player:
            await query.edit_message_text("❌ مش مسجل."); return
        if crop not in FARM_CROPS:
            await query.edit_message_text("❌ محصول غير معروف."); return
        fc      = FARM_CROPS[crop]
        cost    = get_farm_cost(data, crop)
        if player["gold"] < cost:
            await query.edit_message_text(f"❌ محتاج {cost:,} ذهب. عندك {player['gold']:,}."); return

        # المحاصيل الطبيعية للمنطقة تنتج أكتر بـ 50%
        region    = player["region"]
        preferred = REGION_PREFERRED_CROPS.get(region, [])
        amount    = fc["amount"]
        bonus_txt = ""
        if crop in preferred:
            amount    = int(amount * 1.5)
            bonus_txt = " (+50% بونص منطقتك ⭐)"

        data["players"][str(user_id)]["gold"] -= cost
        crops_inv = data["players"][str(user_id)].get("crops", {})
        crops_inv[crop] = crops_inv.get(crop, 0) + 1
        data["players"][str(user_id)]["crops"] = crops_inv
        # حفظ كمية الإنتاج الفعلية
        if "crops_amount" not in data["players"][str(user_id)]:
            data["players"][str(user_id)]["crops_amount"] = {}
        data["players"][str(user_id)]["crops_amount"][crop] = amount

        leveled_up, new_lvl = add_xp(data, user_id, 70)
        save_data(data)
        msg = (f"🌾 تم زراعة *{fc['name']}*!{bonus_txt}\n"
               f"📦 ستنتج *{amount} {crop}* عند كل جمع ضرائب\n"
               f"💰 الذهب المتبقي: {player['gold']-cost:,}\n⭐+70 XP")
        if leveled_up: msg += f"\n🎉 *ترقية!* {new_lvl['name']} {new_lvl['emoji']}"
        await query.edit_message_text(msg, parse_mode="Markdown")

# ======= /start =======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌍 *أهلاً بك في لعبة الشرق الأوسط!*\n\nللبدء: *انشاء دولة*\nللمساعدة: *مساعدة*",
        parse_mode="Markdown")

# ======= تشغيل =======
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_message))

    loop = asyncio.get_event_loop()
    loop.create_task(disaster_loop(app))
    loop.create_task(shipment_loop(app))

    print("✅ البوت شغال!")
    app.run_polling()

if __name__ == "__main__":
    main()
