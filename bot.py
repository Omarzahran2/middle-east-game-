"""
🗺️ لعبة الشرق الأوسط الجيوسياسية - النسخة 3.0
"""
import logging, random, string, json, os, io, time, asyncio
from PIL import Image, ImageDraw
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, CallbackQueryHandler, filters

BOT_TOKEN  = os.environ.get("BOT_TOKEN", "")
ADMIN_ID   = int(os.environ.get("ADMIN_ID", "0"))
DATA_FILE  = "game_data.json"
MAP_FILE   = "map_base.png"
FLAGS_DIR  = "flags"
os.makedirs(FLAGS_DIR, exist_ok=True)

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

# ==================== توقيتات ====================
HOUR_REAL      = 180        # ثانية = ساعة لعبة
WEEK_REAL      = HOUR_REAL * 24 * 7
TAX_COOLDOWN   = HOUR_REAL * 5   # 15 دقيقة
DISASTER_EVERY = WEEK_REAL       # 21 دقيقة
ATTACK_CD      = 60 * 5          # cooldown هجوم 5 دقائق
ALLY_REQ_TTL   = 60 * 30         # طلبات تحالف تنتهي بعد 30 دقيقة
MAX_MARKET_PER_PLAYER = 5        # حد أقصى عروض في السوق

FLAG_SIZE_MAIN  = 200
FLAG_SIZE_SMALL = 100

# ==================== قروض البنك الدولي ====================
LOAN_OPTIONS = [
    {"id":"small",  "name":"قرض صغير",  "amount":1000, "interest":0.20, "due_cycles":3,  "emoji":"💵"},
    {"id":"medium", "name":"قرض متوسط", "amount":3000, "interest":0.25, "due_cycles":5,  "emoji":"💴"},
    {"id":"large",  "name":"قرض كبير",  "amount":7000, "interest":0.30, "due_cycles":8,  "emoji":"💶"},
]
# due_cycles = عدد دورات الحصاد قبل السداد
# ==================== إحداثيات ====================
REGION_COORDS = {
    "مصر":      [(378,1077)],
    "تركيا":    [(532,407),(192,306)],
    "ايران":    [(1267,642)],
    "الاردن":   [(662,906)],
    "قطر":      [(1331,1187)],
    "الامارات": [(1482,1288)],
    "عمان":     [(1610,1509),(1549,1149)],
    "فلسطين":   [(594,844)],
    "الكويت":   [(1130,948)],
    "العراق":   [(957,749)],
    "السعودية": [(1080,1246)],
    "اليمن":    [(1206,1703)],
    "لبنان":    [(614,692)],
    "سوريا":    [(726,618)],
    "البحرين":  [(1010,1080)],
    "ليبيا":    [(150,700)],
    "السودان":  [(350,1300)],
    "اسرائيل":  [(580,870)],
    "مصر_شمال": [(378,900)],  # موقع السويس
}
AVAILABLE_REGIONS = [r for r in REGION_COORDS if r != "مصر_شمال"]

# ==================== المضائق ====================
STRAITS = {
    "هرمز":       {"controller":["عمان","ايران"],  "affects":["السعودية","الكويت","العراق","قطر","الامارات","البحرين"], "blocked":False,"blocked_by":None},
    "باب المندب": {"controller":["اليمن"],          "affects":["مصر","السودان","الاردن"],                               "blocked":False,"blocked_by":None},
    "السويس":     {"controller":["مصر"],            "affects":["اردن","اسرائيل","لبنان","سوريا","تركيا","ليبيا","السودان"],"blocked":False,"blocked_by":None},
}

# ==================== الموارد ====================
REGION_RESOURCES = {
    "السعودية":["نفط","غاز"], "الكويت":["نفط","غاز"], "العراق":["نفط","غاز"],
    "قطر":["غاز","نفط"],      "ليبيا":["نفط"],          "ايران":["نفط","غاز","صلب"],
    "الامارات":["ذهب","غاز"], "البحرين":["ذهب"],         "السودان":["قمح","ذهب"],
    "اسرائيل":["صلب","قمح"],  "عمان":["نفط","غاز"],
    "مصر":["قمح","ارز","فول"],
    "سوريا":["قمح","زيتون"],   "اليمن":["بن","فول"],
    "تركيا":["قمح","بطاطس","صلب"], "الاردن":["بطاطس","زيتون"],
    "فلسطين":["زيتون","فول"],  "لبنان":["زيتون","ذهب"],
}

RESOURCE_FACILITIES = {
    "نفط": {"name":"🛢️ مصفى نفط",  "base_cost":2000,"amount":3,"emoji":"🛢️"},
    "غاز": {"name":"⛽ محطة غاز",   "base_cost":1800,"amount":3,"emoji":"⛽"},
    "صلب": {"name":"⚙️ مصنع صلب",  "base_cost":2500,"amount":2,"emoji":"⚙️"},
    "ذهب": {"name":"🏦 بنك مركزي", "base_cost":3000,"amount":2,"emoji":"🏦"},
}

FARM_CROPS = {
    "قمح":   {"name":"🌾 حقل قمح",     "base_cost":400, "amount":35,"emoji":"🌾"},
    "ارز":   {"name":"🍚 حقل ارز",     "base_cost":350, "amount":30,"emoji":"🍚"},
    "فول":   {"name":"🫘 حقل فول",     "base_cost":300, "amount":20,"emoji":"🫘"},
    "بن":    {"name":"☕ مزرعة بن",    "base_cost":450, "amount":12,"emoji":"☕"},
    "بطاطس": {"name":"🥔 حقل بطاطس",  "base_cost":250, "amount":40,"emoji":"🥔"},
    "زيتون": {"name":"🫒 بستان زيتون","base_cost":350, "amount":15,"emoji":"🫒"},
}

REGION_PREFERRED_CROPS = {
    "مصر":["قمح","ارز","فول"], "سوريا":["قمح","زيتون"],
    "السودان":["قمح","فول"],    "اليمن":["بن","فول"],
    "تركيا":["قمح","بطاطس"],   "الاردن":["بطاطس","زيتون"],
    "فلسطين":["زيتون","فول"],   "لبنان":["زيتون","بن"],
    "اسرائيل":["قمح","بطاطس"],
}
ALL_CROPS = list(FARM_CROPS.keys())

# أسعار البيع التلقائي بعد الحصاد (ذهب/طن)
CROP_SELL_PRICE = {
    "قمح":5, "ارز":7, "فول":8, "بن":25, "بطاطس":3, "زيتون":18,
    "نفط":80,"غاز":60,"صلب":50,"ذهب":100,
}

# ==================== الكوارث ====================
DISASTERS = [
    {"name":"زلزال مدمر",     "emoji":"🌍","effect":"army",      "loss":(0.2,0.4),"msg":"ضرب زلزال مدمر! خسرت جزء من جيشك!"},
    {"name":"فيضانات",        "emoji":"🌊","effect":"facilities", "loss":(1,2),    "msg":"فيضانات دمرت بعض منشآتك!"},
    {"name":"جفاف شديد",      "emoji":"☀️","effect":"crops",     "loss":(0.3,0.5),"msg":"جفاف اثر على محاصيلك!"},
    {"name":"وباء",           "emoji":"🦠","effect":"army",      "loss":(0.1,0.3),"msg":"وباء اجتاح جيشك!"},
    {"name":"حريق مصانع",     "emoji":"🔥","effect":"facilities", "loss":(1,1),    "msg":"حريق دمر احدى منشآتك!"},
    {"name":"انهيار اقتصادي", "emoji":"📉","effect":"gold",      "loss":(0.1,0.2),"msg":"انهيار اقتصادي! خسرت جزء من ذهبك!"},
]

# ==================== المستويات ====================
LEVELS = [
    {"level":1,"name":"قرية",         "xp":0,    "emoji":"🏘️"},
    {"level":2,"name":"مدينة ناشئة",  "xp":500,  "emoji":"🏙️"},
    {"level":3,"name":"اماره",        "xp":1500, "emoji":"🏰"},
    {"level":4,"name":"مملكة",        "xp":3000, "emoji":"👑"},
    {"level":5,"name":"امبراطورية",   "xp":6000, "emoji":"🌟"},
    {"level":6,"name":"قوة عظمى",    "xp":12000,"emoji":"⚡"},
    {"level":7,"name":"حضارة متقدمة","xp":25000,"emoji":"🚀"},
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

def add_xp(data, uid, amount):
    old = data["players"][str(uid)].get("xp",0)
    new = old + amount
    data["players"][str(uid)]["xp"] = new
    return get_level(new)["level"] > get_level(old)["level"], get_level(new)

# ==================== السكان والاحوال ====================
def calc_population(p):
    base  = 1.0
    terr  = p.get("territories",1) * 0.3
    crops = sum(p.get("crops",{}).values()) * 0.5
    econ  = min(p.get("gold",0)/10000, 2.0)
    wars  = p.get("wars_lost",0) * 0.2
    dis   = p.get("disasters_hit",0) * 0.1
    return round(max(0.5, base+terr+crops+econ-wars-dis), 1)

def calc_food_security(p):
    crops = sum(p.get("crops",{}).values())
    pop   = calc_population(p)
    if pop == 0: return 100
    return min(100, int((crops*0.5/pop)*100))

def calc_health(p):
    return max(10, min(100,
        60 + min(20, p.get("gold",0)//500) +
        calc_food_security(p)//5 -
        p.get("wars_lost",0)*5 -
        p.get("disasters_hit",0)*3
    ))

def calc_happiness(p):
    traitor = -20 if p.get("traitor") else 0
    return max(5, min(100,
        50 + calc_food_security(p)//4 +
        min(20, p.get("gold",0)//1000) +
        len(p.get("allies",[]))*3 -
        p.get("wars_lost",0)*8 + traitor
    ))

def status_emoji(v):
    return "🟢" if v>=80 else "🟡" if v>=50 else "🟠" if v>=25 else "🔴"

def pbar(v, n=10):
    f = int((v/100)*n)
    return "█"*f + "░"*(n-f)

# ==================== تنسيق ====================
def sep(c="─", n=28): return c*n
def box_title(e, t): return f"{e} *{t}*\n{sep()}"
def progress_bar(v, mx, n=10):
    f = int((v/mx)*n) if mx>0 else 0
    return "█"*f + "░"*(n-f)

# ==================== بيانات ====================

_data_lock = asyncio.Lock()

def save_data(d):
    """حفظ آمن — atomic write + backup تلقائي"""
    # backup قبل الحفظ
    if os.path.exists(DATA_FILE):
        try:
            import shutil
            shutil.copy2(DATA_FILE, DATA_FILE + ".bak")
        except: pass
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_FILE)  # atomic — مش ممكن يتقطع في النص

def load_data():
    """تحميل مع قراءة آمنة"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
        except (json.JSONDecodeError, IOError):
            # لو الملف اتخرب، رجّع نسخة احتياطية
            backup = DATA_FILE + ".bak"
            if os.path.exists(backup):
                with open(backup, "r", encoding="utf-8") as f:
                    d = json.load(f)
            else:
                d = {}
    else:
        d = {}
    d.setdefault("players", {})
    d.setdefault("pending_codes", {})
    d.setdefault("market", [])
    d.setdefault("shipments", [])
    d.setdefault("alliance_requests", {})
    d.setdefault("dissolve_requests", {})
    d.setdefault("last_disaster", 0)
    d.setdefault("wars_enabled", True)  # الأدمن يقدر يقفل الحروب
    d.setdefault("straits", {k: {"blocked": False, "blocked_by": None} for k in STRAITS})
    return d

def generate_code():
    return "".join(random.choices(string.ascii_uppercase+string.digits, k=6))

def get_player(d, uid):
    p = d["players"].get(str(uid))
    if p:
        # تصحيح تلقائي للقيم السالبة
        for field in ["gold","army","territories","xp"]:
            if p.get(field,0) < 0:
                d["players"][str(uid)][field] = 0
    return p

def is_admin(uid):
    return uid == ADMIN_ID

def find_by_code(d, code):
    for uid, p in d["players"].items():
        if p.get("player_code") == code.upper():
            return uid, p
    return None, None

def find_by_name(d, name):
    for uid, p in d["players"].items():
        if p["country_name"] == name or p["region"] == name:
            return uid, p
    return None, None

def new_player(region, country_name, player_id):
    return {
        "country_name":country_name, "region":region,
        "gold":1000, "army":100, "territories":1,
        "allies":[], "at_war":[], "last_tax":0,
        "player_code":generate_code(), "xp":0,
        "facilities":{}, "crops":{}, "crops_amount":{},
        "infrastructure":0, "capital":"",
        "traitor":False, "wars_lost":0, "disasters_hit":0,
        "last_attack":0, "loans":[],
    }

def get_farm_cost(d, crop):
    base = FARM_CROPS[crop]["base_cost"]
    # السعر بيتغير حسب كمية المحصول عند اللاعبين
    total = sum(sum(p.get("crops",{}).values()) for p in d["players"].values())
    factor = 1.5 if total == 0 else max(0.7, 1.5 - total*0.02)
    return max(150, int(base*factor))

def get_strait_status(d):
    result = {}
    for name, info in STRAITS.items():
        saved = d["straits"].get(name, {})
        result[name] = {**info, "blocked":saved.get("blocked",False), "blocked_by":saved.get("blocked_by")}
    return result

def is_shipment_blocked(d, seller_reg, buyer_reg):
    for name, s in get_strait_status(d).items():
        if s["blocked"]:
            if seller_reg in s["affects"] or buyer_reg in s["affects"]:
                return True, name
    return False, None

def clean_old_requests(d):
    """امسح طلبات التحالف المنتهية (alliance + dissolve)"""
    now = time.time()
    d["alliance_requests"] = {
        k: v for k, v in d.get("alliance_requests", {}).items()
        if now - v.get("time", 0) < ALLY_REQ_TTL
    }
    # dissolve_requests مفيهاش time — امسح اللي عمرها +1 ساعة
    d.setdefault("dissolve_requests", {})
    # مش محتاجين نمسحهم لأنهم مرتبطين بزرار تليجرام

# ==================== الخريطة ====================
def generate_map(players, d):
    img  = Image.open(MAP_FILE).convert("RGBA")
    draw = ImageDraw.Draw(img)
    straits = get_strait_status(d)
    for uid, p in players.items():
        region    = p.get("region")
        flag_path = os.path.join(FLAGS_DIR, f"{region}.png")
        if region not in REGION_COORDS: continue
        for i, (cx,cy) in enumerate(REGION_COORDS[region]):
            size = FLAG_SIZE_MAIN if i==0 else FLAG_SIZE_SMALL
            if os.path.exists(flag_path):
                flag = Image.open(flag_path).convert("RGBA").resize((size, int(size*0.6)), Image.LANCZOS)
                fw,fh = flag.size; fx,fy = cx-fw//2, cy-fh//2
                img.paste(flag,(fx,fy),flag)
                draw.rectangle([fx-3,fy-3,fx+fw+3,fy+fh+3], outline="white", width=4)
                if i==0:
                    lvl  = get_level(p.get("xp",0))
                    name = p.get("country_name","")
                    tag  = " 🗡️" if p.get("traitor") else ""
                    draw.text((cx,fy+fh+6), f"{lvl['emoji']}{name}{tag}", fill="black", anchor="mt")
            else:
                r = 30 if i==0 else 15
                draw.ellipse([cx-r,cy-r,cx+r,cy+r], fill="#e74c3c", outline="white", width=3)
    # المضائق
    strait_pos = {"هرمز":(1400,1050),"باب المندب":(1100,1550),"السويس":(500,950)}
    for name, pos in strait_pos.items():
        s = straits.get(name,{})
        col = "red" if s.get("blocked") else "cyan"
        cx,cy = pos
        draw.ellipse([cx-20,cy-20,cx+20,cy+20], fill=col, outline="white", width=3)
        draw.text((cx,cy+25), f"{'🔴' if s.get('blocked') else '🟢'}{name}", fill="white", anchor="mt")
    buf = io.BytesIO()
    img.save(buf, format="PNG"); buf.seek(0)
    return buf

# ==================== الحصاد التلقائي ====================
async def do_harvest(app, uid, p, data):
    """ينفذ حصاد وبيع تلقائي — يشمل الأراضي حتى بدون مزارع"""
    crops_p      = p.get("crops",{})
    crops_amount = p.get("crops_amount",{})

    region    = p.get("region","")
    preferred = REGION_PREFERRED_CROPS.get(region,[])
    total_gold = 0
    total_tons = 0
    lines      = []

    for crop, count in crops_p.items():
        fc      = FARM_CROPS.get(crop, {})
        amt_per = crops_amount.get(crop, fc.get("amount",10))
        # بونص المنطقة
        if crop in preferred:
            amt_per = int(amt_per * 1.5)
        qty       = amt_per * count
        price     = CROP_SELL_PRICE.get(crop, 5)
        gold_earned = qty * price
        total_gold += gold_earned
        total_tons += qty
        lines.append(f"  {fc.get('emoji','🌾')} {qty}طن {crop} → +{gold_earned:,}ذ")

    # الانتاج الصناعي
    facs = p.get("facilities",{})
    for res, count in facs.items():
        fc       = RESOURCE_FACILITIES.get(res,{})
        qty      = fc.get("amount",2) * count
        price    = CROP_SELL_PRICE.get(res, 50)
        gold_e   = qty * price
        total_gold += gold_e
        lines.append(f"  {fc.get('emoji','🏭')} {qty} {res} → +{gold_e:,}ذ")

    # دخل الاراضي دايماً
    terr_income = p.get("territories",1)*50 + 200
    total_gold += terr_income

    # سداد القروض التلقائي
    loans     = p.get("loans",[])
    loan_msgs = []
    new_loans = []
    for loan in loans:
        loan["remaining_cycles"] = loan.get("remaining_cycles",1) - 1
        if loan["remaining_cycles"] <= 0:
            due = loan["due"]
            if data["players"][str(uid)]["gold"] + total_gold >= due:
                total_gold -= due
                loan_msgs.append(f"   🏦 سُدِّد قرض {loan['name']}: -{due:,}ذ ✅")
            else:
                # عقوبة عدم السداد
                penalty = int(due * 0.5)
                data["players"][str(uid)]["gold"] = max(0, data["players"][str(uid)]["gold"] - penalty)
                loan_msgs.append(f"   ⚠️ قرض {loan['name']} متأخر! عقوبة: -{penalty:,}ذ")
                loan["remaining_cycles"] = 2  # فرصة إضافية
                new_loans.append(loan)
        else:
            new_loans.append(loan)
    data["players"][str(uid)]["loans"] = new_loans

    data["players"][str(uid)]["gold"]    += total_gold
    data["players"][str(uid)]["last_tax"] = time.time()
    leveled_up, new_lvl = add_xp(data, uid, 50 + p.get("territories",1)*10)

    # لو مفيش إنتاج ومفيش قروض، ابعت رسالة مختصرة
    if not lines and not loan_msgs:
        msg = (
            f"💰 *دخل الأراضي التلقائي*\n{sep()}\n"
            f"🗺️ {p['territories']} منطقة: +{terr_income:,}ذ\n"
            f"💰 الرصيد: *{p['gold']+total_gold:,}*\n"
            f"⏳ القادم بعد 15 دقيقة\n"
            f"💡 ابنِ مزارع أو منشآت لزيادة الدخل!"
        )
    else:
        prod_txt = "\n".join(lines) if lines else "  (لا يوجد إنتاج)"
        loan_txt = "\n".join(loan_msgs) if loan_msgs else ""
        msg = (
            f"{box_title('💰','الحصاد التلقائي')}\n\n"
            f"📦 *الإنتاج:*\n{prod_txt}\n"
            f"  🗺️ دخل الأراضي: +{terr_income:,}ذ\n"
            f"{sep()}\n"
            f"  🌾 الكمية: ~{total_tons} طن\n"
            f"  💰 المضاف: *+{total_gold:,}*\n"
            f"  💰 الرصيد: *{p['gold']+total_gold:,}*"
        )
        if loan_txt:
            msg += f"\n{sep()}\n🏦 *القروض:*\n{loan_txt}"
    if leveled_up:
        msg += f"\n🎊 *ترقية!* {new_lvl['name']} {new_lvl['emoji']}"
    msg += f"\n{sep()}\n⏳ القادم بعد 15 دقيقة"
    try:
        await app.bot.send_message(chat_id=int(uid), text=msg, parse_mode="Markdown")
    except: pass

# ==================== loops ====================
async def disaster_loop(app):
    await asyncio.sleep(DISASTER_EVERY)
    while True:
        try:
            data = load_data()
            if data["players"]:
                # اختار دولة عشوائية من دول مختلفة عن آخر كارثة
                uids = list(data["players"].keys())
                uid  = random.choice(uids)
                p    = data["players"][uid]
                d    = random.choice(DISASTERS)
                loss = 0

                if d["effect"] == "army":
                    pct  = random.uniform(*d["loss"])
                    loss = max(10, int(p["army"]*pct))
                    data["players"][uid]["army"] = max(0, p["army"]-loss)
                elif d["effect"] == "gold":
                    pct  = random.uniform(*d["loss"])
                    loss = max(50, int(p["gold"]*pct))
                    data["players"][uid]["gold"] = max(0, p["gold"]-loss)
                elif d["effect"] == "facilities":
                    facs = p.get("facilities",{})
                    if facs:
                        res  = random.choice(list(facs.keys()))
                        loss = random.randint(1, min(2,facs[res]))
                        data["players"][uid]["facilities"][res] = max(0,facs[res]-loss)
                        if data["players"][uid]["facilities"][res]==0:
                            del data["players"][uid]["facilities"][res]
                elif d["effect"] == "crops":
                    crops = p.get("crops",{})
                    if crops:
                        res = random.choice(list(crops.keys()))
                        pct = random.uniform(*d["loss"])
                        data["players"][uid]["crops"][res] = max(0, int(crops[res]*(1-pct)))

                data["players"][uid]["disasters_hit"] = p.get("disasters_hit",0)+1
                data["last_disaster"] = time.time()
                save_data(data)
                try:
                    await app.bot.send_message(chat_id=int(uid),
                        text=f"{d['emoji']} *كارثة طبيعية!*\n{sep()}\n"
                             f"ضربت *{p['country_name']}* كارثة {d['name']}!\n"
                             f"📢 {d['msg']}\n{sep()}\n💔 الخسارة: *{loss}*",
                        parse_mode="Markdown")
                except: pass
        except Exception as e:
            logging.error(f"Disaster loop: {e}")
        await asyncio.sleep(DISASTER_EVERY)

_harvest_lock = asyncio.Lock()

async def harvest_loop(app):
    """كل دقيقة يتحقق — لو اللاعب وصل cooldown، يحصد تلقائياً
       + يمسح الشحنات القديمة (+24 ساعة)"""
    await asyncio.sleep(TAX_COOLDOWN)
    while True:
        try:
            async with _harvest_lock:
                data = load_data()
                now  = time.time()
                harvested = False

                # مسح الشحنات المنتهية الصلاحية (+24 ساعة)
                data["shipments"] = [
                    s for s in data.get("shipments", [])
                    if now - s.get("sent_at", 0) < 86400
                ]

                for uid, p in list(data["players"].items()):
                    if now - p.get("last_tax", 0) >= TAX_COOLDOWN:
                        await do_harvest(app, uid, p, data)
                        harvested = True
                if harvested:
                    save_data(data)
        except Exception as e:
            logging.error(f"Harvest loop: {e}")
        await asyncio.sleep(60)

# ==================== معالج الرسائل ====================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text:
        text = update.message.text.strip()
    elif update.message.caption:
        text = update.message.caption.strip()
    else:
        text = ""

    uid   = update.effective_user.id
    uname = update.effective_user.first_name
    data  = load_data()
    clean_old_requests(data)

    # ======= أدمن: انشاء دولة بعلم =======
    if is_admin(uid) and update.message.photo and text.startswith("دولة "):
        parts = text.split()
        if len(parts) < 4:
            await update.message.reply_text("الصيغة:\n`دولة [المنطقة] [اسم] [الكود]`", parse_mode="Markdown"); return
        code   = parts[-1].upper()
        region = parts[1]
        cname  = " ".join(parts[2:-1])
        if code not in data["pending_codes"]:
            await update.message.reply_text(f"الكود `{code}` مش موجود.", parse_mode="Markdown"); return
        if region not in AVAILABLE_REGIONS:
            await update.message.reply_text(f"'{region}' مش في القائمة."); return
        for _, p in data["players"].items():
            if p["region"] == region:
                await update.message.reply_text(f"'{region}' محجوزة."); return
        photo  = update.message.photo[-1]
        ff     = await context.bot.get_file(photo.file_id)
        await ff.download_to_drive(os.path.join(FLAGS_DIR, f"{region}.png"))
        pid    = data["pending_codes"].pop(code)
        pl     = new_player(region, cname, pid)
        res    = REGION_RESOURCES.get(region, [])
        data["players"][str(pid)] = pl
        save_data(data)
        await update.message.reply_text(
            f"✅ تم!\n🏳️ *{cname}* ← {region}\n🔑 `{pl['player_code']}`", parse_mode="Markdown")
        try:
            await context.bot.send_message(chat_id=pid,
                text=f"🎊 *تم تفعيل دولتك!*\n{sep('═')}\n"
                     f"🏳️ *{cname}* | 🗺️ {region}\n"
                     f"🌍 الموارد: {', '.join(res) if res else 'لا يوجد'}\n{sep()}\n"
                     f"💰 ذهب: 1,000 | ⚔️ جيش: 100\n📖 اكتب *مساعدة*", parse_mode="Markdown")
        except: pass
        return

    # ======= انشاء دولة =======
    if text == "انشاء دولة":
        if get_player(data, uid):
            await update.message.reply_text(f"⚠️ عندك دولة بالفعل."); return
        existing = next((c for c,v in data["pending_codes"].items() if v==uid), None)
        if existing:
            await update.message.reply_text(f"⏳ كودك: `{existing}`", parse_mode="Markdown"); return
        code = generate_code()
        while code in data["pending_codes"]: code = generate_code()
        data["pending_codes"][code] = uid; save_data(data)
        await update.message.reply_text(
            f"{box_title('🎮','طلب انشاء دولة')}\n\nاهلاً *{uname}*! ✅\n\n"
            f"🔑 كودك:\n┌─────────────┐\n│  `{code}`  │\n└─────────────┘\n\n"
            f"ابعت الكود للادمن!", parse_mode="Markdown")
        return

    # ======= كودي =======
    if text in ["كودي","الكود"]:
        p = get_player(data, uid)
        if not p: await update.message.reply_text("❌ مش مسجل."); return
        await update.message.reply_text(f"🔑 كودك:\n```\n{p['player_code']}```", parse_mode="Markdown")
        return

    # ======= حالة دولتي =======
    if text in ["حالة دولتي","دولتي","وضعي"]:
        p = get_player(data, uid)
        if not p: await update.message.reply_text("❌ مش مسجل."); return
        xp   = p.get("xp",0)
        lvl  = get_level(xp)
        nxt  = get_next_level(xp)
        nxt_txt = f"{nxt['xp']-xp:,} XP للمستوى القادم" if nxt else "🏆 اعلى مستوى!"
        left = TAX_COOLDOWN - (time.time()-p.get("last_tax",0))
        tax  = "✅ جاهزة" if left<=0 else f"⏳ {int(left//60)}:{int(left%60):02d}"
        facs = p.get("facilities",{})
        fac_txt = "\n".join(f"  {RESOURCE_FACILITIES[r]['emoji']} {RESOURCE_FACILITIES[r]['name']}: {c}" for r,c in facs.items()) or "  لا يوجد"
        crops_p = p.get("crops",{})
        crops_txt = "\n".join(f"  {FARM_CROPS[c]['emoji']} {FARM_CROPS[c]['name']}: {n} حقل" for c,n in crops_p.items()) or "  لا يوجد"
        total_tons = sum(
            FARM_CROPS.get(c,{}).get("amount",0)*n*(1.5 if c in REGION_PREFERRED_CROPS.get(p["region"],[]) else 1)
            for c,n in crops_p.items()
        )
        res     = REGION_RESOURCES.get(p["region"],[])
        capital = p.get("capital","غير محددة")
        infra   = p.get("infrastructure",0)
        traitor = " 🗡️خائن" if p.get("traitor") else ""
        xp_bar  = progress_bar(xp-lvl["xp"], (nxt["xp"]-lvl["xp"]) if nxt else 1)
        econ    = p["territories"]*50+200 + sum(RESOURCE_FACILITIES.get(r,{}).get("amount",0)*c*CROP_SELL_PRICE.get(r,0) for r,c in facs.items())
        pop     = calc_population(p)
        food    = calc_food_security(p)
        health  = calc_health(p)
        happy   = calc_happiness(p)
        # القروض النشطة
        loans_active = p.get("loans",[])
        loans_txt = ""
        for ln in loans_active:
            loans_txt += f"  🏦 {ln['name']}: يُسدَّد {ln['due']:,}ذ بعد {ln['remaining_cycles']} دورة\n"
        if not loans_txt: loans_txt = "  لا يوجد"

        allies  = ", ".join(p.get("allies",[])) or "—"
        wars    = ", ".join(p.get("at_war",[])) or "في سلام ☮️"

        msg1 = (
            f"{lvl['emoji']} *{p['country_name']}*{traitor}\n{sep('═')}\n"
            f"🏅 Lv.{lvl['level']}: *{lvl['name']}*\n"
            f"⭐ `{xp_bar}` {xp:,} XP | {nxt_txt}\n\n"
            f"📍 {p['region']} | 🏛️ {capital} | 🏗️ Lv.{infra}\n"
            f"🌍 الموارد: {', '.join(res) or '—'}\n"
            f"{sep()}\n"
            f"💰 الخزينة: *{p['gold']:,}* ذهب\n"
            f"📈 دخل تقديري: ~{econ:,}/دورة\n"
            f"⚔️ الجيش: {p['army']:,} | 🗺️ الاراضي: {p['territories']}\n"
            f"{sep()}\n"
            f"🏭 المنشآت:\n{fac_txt}\n"
            f"🌾 المزارع:\n{crops_txt}\n"
            f"   📦 ناتج: ~{int(total_tons)} طن/دورة\n"
            f"{sep()}\n"
            f"💵 الحصاد التالي: {tax}\n"
            f"🏦 *القروض:*\n{loans_txt}\n"
            f"🤝 {allies} | ⚔️ {wars}"
        )
        msg2 = (
            f"👥 *السكان والاحوال — {p['country_name']}*\n{sep('═')}\n"
            f"🧑‍🤝‍🧑 السكان: *{pop}M* نسمة\n{sep()}\n"
            f"🌾 الامن الغذائي:\n   {status_emoji(food)} `{pbar(food)}` {food}%\n"
            f"❤️ الصحة العامة:\n   {status_emoji(health)} `{pbar(health)}` {health}%\n"
            f"😊 الرضا الاجتماعي:\n   {status_emoji(happy)} `{pbar(happy)}` {happy}%"
        )
        await update.message.reply_text(msg1, parse_mode="Markdown")
        await update.message.reply_text(msg2, parse_mode="Markdown")
        return

    # ======= بناء منشاة صناعية =======
    if text in ["بناء منشاة","بناء منشأة","انشئ منشاة"]:
        p = get_player(data, uid)
        if not p: await update.message.reply_text("❌ مش مسجل."); return
        region    = p["region"]
        res_avail = [r for r in REGION_RESOURCES.get(region,[]) if r in RESOURCE_FACILITIES]
        infra     = p.get("infrastructure",0)
        AGRI = list(REGION_PREFERRED_CROPS.keys())
        if region in AGRI and not res_avail:
            unlocked = []
            if infra>=1: unlocked.append("صلب")
            if infra>=2: unlocked+=["نفط","غاز"]
            if infra>=3: unlocked.append("ذهب")
            if not unlocked:
                await update.message.reply_text(
                    f"❌ منطقتك زراعية!\nابن *بنية تحتية* اولاً:\n"
                    f"• Lv.1 (1,500ذ) ← صلب ⚙️\n• Lv.2 (2,500ذ) ← نفط/غاز\n• Lv.3 (3,500ذ) ← بنك",
                    parse_mode="Markdown"); return
            res_avail = unlocked
        if not res_avail:
            await update.message.reply_text("❌ منطقتك مش عندها موارد صناعية. جرب *بناء مزرعة*.", parse_mode="Markdown"); return
        table = "".join(f"{RESOURCE_FACILITIES[r]['emoji']} {RESOURCE_FACILITIES[r]['name']}: {RESOURCE_FACILITIES[r]['base_cost']:,}ذ → +{RESOURCE_FACILITIES[r]['amount']} {r}/دورة\n" for r in res_avail)
        kbd = [[InlineKeyboardButton(f"{RESOURCE_FACILITIES[r]['emoji']} {r.upper()} {RESOURCE_FACILITIES[r]['base_cost']}ذ", callback_data=f"build_{r}")] for r in res_avail]
        kbd.append([InlineKeyboardButton("❌ الغاء", callback_data="cancel")])
        await update.message.reply_text(
            f"🏗️ *اختار المنشاة:*\n\n{table}",
            reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")
        return

    # ======= بناء مزرعة =======
    if text in ["بناء مزرعة","ابني مزرعة","انشئ مزرعة"]:
        p = get_player(data, uid)
        if not p: await update.message.reply_text("❌ مش مسجل."); return
        region    = p["region"]
        preferred = REGION_PREFERRED_CROPS.get(region,[])
        sorted_c  = preferred + [c for c in ALL_CROPS if c not in preferred]
        table = ""
        kbd   = []
        row   = []
        for crop in sorted_c:
            fc   = FARM_CROPS[crop]
            cost = get_farm_cost(data, crop)
            star = "⭐" if crop in preferred else ""
            real_amt = int(fc["amount"]*1.5) if crop in preferred else fc["amount"]
            table += f"{fc['emoji']}{star} {crop}: {cost}ذ → {real_amt}طن/حقل/دورة\n"
            row.append(InlineKeyboardButton(f"{fc['emoji']}{star}{crop} {cost}ذ", callback_data=f"farm_{crop}"))
            if len(row)==2: kbd.append(row); row=[]
        if row: kbd.append(row)
        kbd.append([InlineKeyboardButton("❌ الغاء", callback_data="cancel")])
        pref_txt = f"⭐ مناسب لمنطقتك: {', '.join(preferred)}" if preferred else "تقدر تزرع اي محصول"
        await update.message.reply_text(
            f"🌾 *اختار المحصول:*\n\n{pref_txt}\n{sep()}\n{table}\n⭐ = انتاج اعلى 50%",
            reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")
        return

    # ======= جمع الحصاد يدوياً =======
    if text in ["جمع الضرائب","اجمع الضرائب","حصاد","جمع موارد"]:
        p = get_player(data, uid)
        if not p: await update.message.reply_text("❌ مش مسجل."); return
        left = TAX_COOLDOWN - (time.time()-p.get("last_tax",0))
        if left>0:
            await update.message.reply_text(f"⏳ استنى *{int(left//60)}:{int(left%60):02d}* دقيقة!", parse_mode="Markdown"); return
        # lock لمنع التعارض مع harvest_loop
        async with _harvest_lock:
            data2 = load_data()  # إعادة تحميل ضمان آخر نسخة
            p2    = get_player(data2, uid)
            left2 = TAX_COOLDOWN - (time.time()-p2.get("last_tax",0))
            if left2>0:
                await update.message.reply_text("⏳ تم الحصاد للتو تلقائياً!"); return
            await do_harvest(context.application, uid, p2, data2)
            save_data(data2)
        return

    # ======= بناء بنية تحتية =======
    if text in ["بناء بنية تحتية","بنية تحتية"]:
        p = get_player(data, uid)
        if not p: await update.message.reply_text("❌ مش مسجل."); return
        infra = p.get("infrastructure",0)
        cost  = 1500 + infra*1000
        if p["gold"] < cost:
            await update.message.reply_text(f"❌ محتاج {cost:,}ذ. عندك {p['gold']:,}."); return
        data["players"][str(uid)]["gold"]           -= cost
        data["players"][str(uid)]["infrastructure"]  = infra+1
        leveled_up, new_lvl = add_xp(data, uid, 150)
        save_data(data)
        benefits = {1:"تقدر تبني مصنع صلب",2:"تقدر تبني مصافي نفط/غاز",3:"تقدر تبني بنك مركزي"}
        msg = (f"🏗️ *البنية التحتية Lv.{infra+1}!*\n{sep()}\n"
               f"💰 {cost:,}ذ | ✅ {benefits.get(infra+1,'انتاج +1 لكل المنشآت')}\n⭐+150 XP")
        if leveled_up: msg += f"\n🎊 *ترقية!* {new_lvl['name']} {new_lvl['emoji']}"
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    # ======= العاصمة =======
    if text.startswith("العاصمة "):
        p = get_player(data, uid)
        if not p: await update.message.reply_text("❌ مش مسجل."); return
        capital = text.replace("العاصمة","").strip()
        if not capital: await update.message.reply_text("❌ مثال: العاصمة القاهرة"); return
        data["players"][str(uid)]["capital"] = capital; save_data(data)
        await update.message.reply_text(f"🏛️ *{capital}* عاصمة *{p['country_name']}* ✅", parse_mode="Markdown")
        return

    # ======= المضائق =======
    if text in ["المضائق","حالة المضائق"]:
        straits = get_strait_status(data)
        msg = f"{box_title('⚓','حالة المضائق')}\n\n"
        for name, s in straits.items():
            status = f"🔴 *مغلق* — {s['blocked_by']}" if s.get("blocked") else "🟢 *مفتوح*"
            msg += f"🌊 *{name}*: {status}\n   المتاثرون: {', '.join(s['affects'])}\n\n"
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    for action in ["اغلق","افتح"]:
        if text.startswith(f"{action} مضيق "):
            p = get_player(data, uid)
            if not p: await update.message.reply_text("❌ مش مسجل."); return
            sname = text.replace(f"{action} مضيق","").strip()
            if sname not in STRAITS:
                await update.message.reply_text(f"❌ المضائق: {', '.join(STRAITS.keys())}"); return
            if p["region"] not in STRAITS[sname]["controller"]:
                await update.message.reply_text(f"❌ دولتك مش متحكمة في مضيق {sname}."); return
            blocked = (action == "اغلق")
            data["straits"][sname] = {"blocked":blocked, "blocked_by":p["country_name"] if blocked else None}
            save_data(data)
            icon = "🔴" if blocked else "🟢"
            effect = "الشحنات ستتاخر ضعف الوقت!" if blocked else "حركة الشحن طبيعية."
            await update.message.reply_text(f"{icon} *مضيق {sname} {'مغلق' if blocked else 'مفتوح'}!*\n{effect}", parse_mode="Markdown")
            return

    # ======= تجنيد =======
    if text.startswith("تجنيد "):
        p = get_player(data, uid)
        if not p: await update.message.reply_text("❌ مش مسجل."); return
        try:
            amount = int(text.replace("تجنيد","").strip())
            assert amount > 0
            cost = amount*10
            if p["gold"] < cost:
                await update.message.reply_text(f"❌ يكلف {cost:,}. عندك {p['gold']:,}."); return
            data["players"][str(uid)]["gold"] -= cost
            data["players"][str(uid)]["army"] += amount
            leveled_up, new_lvl = add_xp(data, uid, amount//10)
            save_data(data)
            msg = (f"⚔️ *تجنيد ناجح!*\n{sep()}\n+{amount:,} جندي\n"
                   f"الجيش: {p['army']+amount:,} | الذهب: {p['gold']-cost:,}\n⭐+{amount//10}")
            if leveled_up: msg += f"\n🎊 *ترقية!* {new_lvl['name']}"
            await update.message.reply_text(msg, parse_mode="Markdown")
        except: await update.message.reply_text("❌ مثال: تجنيد 100")
        return

    # ======= هجوم =======
    if text.startswith("هجوم على "):
        p = get_player(data, uid)
        if not p: await update.message.reply_text("❌ مش مسجل."); return
        # هل الحروب مفتوحة؟
        if not data.get("wars_enabled", True):
            await update.message.reply_text(
                f"🕊️ *الحروب موقوفة حالياً*\n{sep()}\n"
                f"الأدمن أوقف الحروب مؤقتاً. انتظر إعادة الفتح.", parse_mode="Markdown"); return
        # cooldown الهجوم
        last_atk = p.get("last_attack",0)
        if time.time()-last_atk < ATTACK_CD:
            rem = int(ATTACK_CD-(time.time()-last_atk))
            await update.message.reply_text(f"⏳ استنى {rem//60}:{rem%60:02d} قبل الهجوم التالي!"); return
        tname = text.replace("هجوم على","").strip()
        tuid, tp = find_by_name(data, tname)
        if not tp: await update.message.reply_text(f"❌ مش لاقي '{tname}'."); return
        if tuid == str(uid): await update.message.reply_text("❌ مينفعش تهاجم نفسك!"); return
        if tp["country_name"] in p.get("allies",[]): await update.message.reply_text(f"❌ {tp['country_name']} حليفك!"); return
        att  = p["army"]*random.uniform(0.7,1.3)
        deff = tp["army"]*random.uniform(0.7,1.3)
        data["players"][str(uid)]["last_attack"] = time.time()
        if att > deff:
            loot = min(tp["gold"]//3, 1000)
            la,ld = random.randint(10,50), random.randint(50,150)
            # نقل الدولة للمنتصر لو جيش المهزوم وصل صفر
            loser_army_after = max(0, tp["army"]-ld)
            conquered = loser_army_after == 0 and tp["army"] < p["army"] // 2

            data["players"][str(uid)]["gold"]        += loot
            data["players"][str(uid)]["territories"] += 1
            data["players"][str(uid)]["army"]         = max(0, p["army"]-la)
            data["players"][tuid]["gold"]             = max(0, tp["gold"]-loot)
            data["players"][tuid]["territories"]      = max(1, tp["territories"]-1)
            data["players"][tuid]["army"]             = loser_army_after
            data["players"][tuid]["wars_lost"]        = tp.get("wars_lost",0)+1
            leveled_up, new_lvl = add_xp(data, uid, 200)

            conquest_txt = ""
            if conquered:
                # نقل علم المهزوم للمنتصر
                loser_flag = os.path.join(FLAGS_DIR, f"{tp['region']}.png")
                winner_flag = os.path.join(FLAGS_DIR, f"{p['region']}.png")
                if os.path.exists(winner_flag):
                    try:
                        import shutil
                        shutil.copy2(winner_flag, loser_flag)
                    except: pass
                # نقل الدولة — غيّر الـ owner
                data["players"][tuid]["country_name"] = f"{tp['country_name']} (محتلة)"
                data["players"][tuid]["occupied_by"]  = p["country_name"]
                data["players"][str(uid)]["territories"] += tp["territories"]
                data["players"][tuid]["territories"]  = 0
                conquest_txt = f"\n🏳️ *احتللت {tp['country_name']} بالكامل!*\nعلمك يرفرف على أراضيهم!"

            save_data(data)
            msg = (f"⚔️ *نتيجة المعركة*\n{sep('═')}\n🏆 *انتصار!*\n\n"
                   f"🗡️ {p['country_name']} vs 🛡️ {tp['country_name']}\n{sep()}\n"
                   f"💰 +{loot:,}ذ | 🗺️ أرض جديدة!\n"
                   f"💀 خسائرك: {la} | خسائر العدو: {ld}\n{sep()}\n⭐+200 XP"
                   f"{conquest_txt}")
            if leveled_up: msg += f"\n🎊 {new_lvl['name']} {new_lvl['emoji']}"
            await update.message.reply_text(msg, parse_mode="Markdown")
            try:
                defeat_msg = (f"🚨 *تنبيه حرب!*\n{sep()}\n*{p['country_name']}* هاجمك!\n"
                              f"💸 خسرت {loot:,}ذ | 💀 خسائر: {ld}\n"
                              f"⚔️ رد بـ `هجوم على {p['country_name']}`")
                if conquered:
                    defeat_msg += f"\n\n💔 *دولتك محتلة بالكامل!*\nأعد بناء جيشك واسترد أراضيك!"
                await context.bot.send_message(chat_id=int(tuid), text=defeat_msg, parse_mode="Markdown")
            except: pass
        else:
            la,ld = random.randint(50,200), random.randint(10,50)
            # تحقق: لو الجيش 0 لا تبعت خسارة 0
            if p["army"] == 0:
                await update.message.reply_text("❌ جيشك 0! جند جنوداً أولاً."); return
            data["players"][str(uid)]["army"]      = max(0, p["army"]-la)
            data["players"][str(uid)]["wars_lost"] = p.get("wars_lost",0)+1
            data["players"][tuid]["army"]          = max(0, tp["army"]-ld)
            save_data(data)
            await update.message.reply_text(
                f"⚔️ *نتيجة المعركة*\n{sep('═')}\n❌ *هزيمة!*\n\n"
                f"💀 خسائرك: {la} | خسائر العدو: {ld}\n💡 جنّد أكثر وأعد المحاولة!",
                parse_mode="Markdown")
        return

    # ======= طلبات التحالف الواردة =======
    if text in ["طلبات التحالف", "طلبات الحلف", "عروض التحالف"]:
        p = get_player(data, uid)
        if not p: await update.message.reply_text("❌ مش مسجل."); return
        reqs = [r for r in data.get("alliance_requests",{}).values()
                if r["to_uid"] == str(uid)]
        dissolve = [r for r in data.get("dissolve_requests",{}).values()
                    if r["to_uid"] == str(uid)]
        if not reqs and not dissolve:
            await update.message.reply_text(
                f"{box_title('📨','الطلبات الواردة')}\n\nمفيش طلبات حالياً.", parse_mode="Markdown"); return
        msg = f"{box_title('📨','الطلبات الواردة')}\n\n"
        if reqs:
            msg += "🤝 *عروض تحالف:*\n"
            for r in reqs:
                msg += f"   • *{r['from_name']}* — رد بـ `تحالف مع {r['from_name']}`\n"
            msg += "\n"
        if dissolve:
            msg += "⚠️ *طلبات حل حلف:*\n"
            for r in dissolve:
                msg += f"   • *{r['from_name']}* يطلب حل الحلف\n"
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    # ======= البنك الدولي - القروض =======
    if text in ["البنك الدولي","بنك","قرض","اخد قرض"]:
        p = get_player(data, uid)
        if not p: await update.message.reply_text("❌ مش مسجل."); return
        active = p.get("loans",[])
        if len(active) >= 2:
            await update.message.reply_text(
                f"❌ *عندك {len(active)} قروض نشطة*\n{sep()}\n"
                f"لازم تسدد القروض الحالية قبل قرض جديد.",
                parse_mode="Markdown"); return
        rows = []
        for l in LOAN_OPTIONS:
            total = int(l["amount"]*(1+l["interest"]))
            rows.append([InlineKeyboardButton(
                f"{l['emoji']} {l['name']}: {l['amount']:,}ذ → يُسدَّد {total:,}ذ في {l['due_cycles']} دورات",
                callback_data=f"loan_{l['id']}")])
        rows.append([InlineKeyboardButton("❌ إلغاء", callback_data="cancel")])
        loans_txt = ""
        for loan in active:
            loans_txt += f"  • {loan['name']}: يُسدَّد بعد {loan['remaining_cycles']} دورات\n"
        msg = (
            f"{box_title('🏦','البنك الدولي')}\n\n"
            f"اقترض الآن وسدّد تلقائياً من الحصاد!\n"
            f"⚠️ عدم السداد = عقوبة 50% إضافية\n"
        )
        if loans_txt:
            msg += f"\n📋 *قروضك الحالية:*\n{loans_txt}"
        msg += f"\n{sep()}\n*اختار نوع القرض:*"
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(rows), parse_mode="Markdown")
        return

    # ======= تحالف مع =======
    if text.startswith("تحالف مع "):
        p = get_player(data, uid)
        if not p: await update.message.reply_text("❌ مش مسجل."); return
        tname = text.replace("تحالف مع","").strip()
        tuid, tp = find_by_name(data, tname)
        if not tp: await update.message.reply_text(f"❌ مش لاقي '{tname}'."); return
        if tuid == str(uid): await update.message.reply_text("❌ مينفعش تتحالف مع نفسك!"); return
        if tp["country_name"] in p.get("allies",[]): await update.message.reply_text("✅ حليف بالفعل."); return
        # حفظ الطلب
        req_key = f"{uid}_{tuid}"
        data.setdefault("alliance_requests",{})[req_key] = {
            "from_uid":str(uid),"from_name":p["country_name"],
            "to_uid":tuid,"to_name":tp["country_name"],"time":time.time()
        }
        save_data(data)
        await update.message.reply_text(
            f"📨 *تم ارسال عرض التحالف!*\n{sep()}\nالى: *{tp['country_name']}*\n⏳ في انتظار الموافقة...",
            parse_mode="Markdown")
        try:
            kbd = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ قبول", callback_data=f"ally_accept_{req_key}"),
                InlineKeyboardButton("❌ رفض",  callback_data=f"ally_reject_{req_key}"),
            ]])
            await context.bot.send_message(chat_id=int(tuid),
                text=f"🤝 *عرض تحالف!*\n{sep()}\n*{p['country_name']}* يعرض التحالف معك!\nهل توافق؟",
                reply_markup=kbd, parse_mode="Markdown")
        except: pass
        return

    # ======= حل الحلف بالتراضي =======
    if text.startswith("حل الحلف مع ") or text.startswith("حل حلف مع "):
        p = get_player(data, uid)
        if not p: await update.message.reply_text("❌ مش مسجل."); return
        tname = text.replace("حل الحلف مع","").replace("حل حلف مع","").strip()
        tuid, tp = find_by_name(data, tname)
        if not tp: await update.message.reply_text(f"❌ مش لاقي '{tname}'."); return
        if tp["country_name"] not in p.get("allies",[]): await update.message.reply_text("❌ مش حليفك."); return
        req_key = f"{uid}_{tuid}_dissolve"
        data.setdefault("dissolve_requests",{})[req_key] = {
            "from_uid":str(uid),"from_name":p["country_name"],
            "to_uid":tuid,"to_name":tp["country_name"]
        }
        save_data(data)
        await update.message.reply_text(f"📨 تم ارسال طلب حل الحلف الى *{tp['country_name']}*...", parse_mode="Markdown")
        try:
            kbd = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ موافق", callback_data=f"dissolve_accept_{req_key}"),
                InlineKeyboardButton("❌ رفض",   callback_data=f"dissolve_reject_{req_key}"),
            ]])
            await context.bot.send_message(chat_id=int(tuid),
                text=f"⚠️ *طلب حل الحلف!*\n{sep()}\n*{p['country_name']}* يريد حل الحلف بالتراضي.\nهل توافق؟",
                reply_markup=kbd, parse_mode="Markdown")
        except: pass
        return

    # ======= نقض الحلف =======
    if text.startswith("نقض الحلف مع ") or text.startswith("نقض حلف مع "):
        p = get_player(data, uid)
        if not p: await update.message.reply_text("❌ مش مسجل."); return
        tname = text.replace("نقض الحلف مع","").replace("نقض حلف مع","").strip()
        tuid, tp = find_by_name(data, tname)
        if not tp: await update.message.reply_text(f"❌ مش لاقي '{tname}'."); return
        if tp["country_name"] not in p.get("allies",[]): await update.message.reply_text("❌ مش حليفك."); return
        data["players"][str(uid)]["allies"] = [a for a in p["allies"] if a!=tp["country_name"]]
        data["players"][tuid]["allies"]     = [a for a in tp.get("allies",[]) if a!=p["country_name"]]
        penalty = min(p["gold"]//4, 1000)
        data["players"][str(uid)]["gold"]    = max(0, p["gold"]-penalty)
        data["players"][str(uid)]["traitor"] = True
        save_data(data)
        await update.message.reply_text(
            f"🗡️ *نقضت الحلف!*\n{sep()}\n💸 عقوبة: {penalty:,}ذ\n🗡️ لقب *خائن* اضيف لدولتك\n💡 `ازالة الخيانة` = 2000ذ",
            parse_mode="Markdown")
        try:
            await context.bot.send_message(chat_id=int(tuid),
                text=f"🚨 *خيانة!*\n{sep()}\n*{p['country_name']}* 🗡️خائن نقض الحلف معك!\nحر في مهاجمتهم ⚔️", parse_mode="Markdown")
        except: pass
        return

    # ======= ازالة الخيانة =======
    if text in ["ازالة الخيانة","تنظيف السمعة"]:
        p = get_player(data, uid)
        if not p: await update.message.reply_text("❌ مش مسجل."); return
        if not p.get("traitor"): await update.message.reply_text("✅ دولتك نظيفة."); return
        if p["gold"]<2000: await update.message.reply_text(f"❌ محتاج 2,000ذ. عندك {p['gold']:,}."); return
        data["players"][str(uid)]["gold"]   -= 2000
        data["players"][str(uid)]["traitor"] = False
        save_data(data)
        await update.message.reply_text(f"✅ *تم تنظيف سمعة دولتك!*\n💸 2,000ذ\n🗡️ لقب الخائن ازيل!", parse_mode="Markdown")
        return

    # ======= تحويل ذهب =======
    if text.startswith("تحويل "):
        p = get_player(data, uid)
        if not p: await update.message.reply_text("❌ مش مسجل."); return
        parts = text.split()
        if len(parts)!=3: await update.message.reply_text("❌ الصيغة: تحويل [مبلغ] [كود]", parse_mode="Markdown"); return
        try: amount=int(parts[1]); assert amount>0
        except: await update.message.reply_text("❌ المبلغ لازم رقم موجب."); return
        if p["gold"]<amount: await update.message.reply_text(f"❌ عندك {p['gold']:,} بس."); return
        tuid, tp = find_by_code(data, parts[2])
        if not tp: await update.message.reply_text("❌ مش لاقي لاعب."); return
        if tuid==str(uid): await update.message.reply_text("❌ مينفعش تحول لنفسك!"); return
        data["players"][str(uid)]["gold"] -= amount
        data["players"][tuid]["gold"]     += amount
        save_data(data)
        await update.message.reply_text(
            f"💸 *تحويل ناجح!*\n{sep()}\nالى: *{tp['country_name']}*\n{amount:,}ذ\nرصيدك: {p['gold']-amount:,}",
            parse_mode="Markdown")
        try:
            await context.bot.send_message(chat_id=int(tuid),
                text=f"💰 *تحويل وارد!*\n{sep()}\nمن: *{p['country_name']}*\n+{amount:,}ذ", parse_mode="Markdown")
        except: pass
        return

    # ======= المتصدرين =======
    if text in ["المتصدرين","الترتيب"]:
        if not data["players"]: await update.message.reply_text("لا يوجد لاعبين."); return
        sorted_p = sorted(data["players"].items(), key=lambda x:x[1].get("xp",0), reverse=True)
        msg = f"{box_title('🏆','المتصدرين')}\n\n"
        medals = ["🥇","🥈","🥉"]
        for i,(puid,pp) in enumerate(sorted_p[:10]):
            m   = medals[i] if i<3 else f"  {i+1}."
            lvl = get_level(pp.get("xp",0))
            bar_xp = progress_bar(pp.get("xp",0), 25000, 8)
            tag = " 🗡️" if pp.get("traitor") else ""
            msg += f"{m} {lvl['emoji']} *{pp['country_name']}*{tag}\n      Lv.{lvl['level']} | {pp.get('xp',0):,} XP | `{bar_xp}`\n\n"
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    # ======= قائمة الدول =======
    if text in ["قائمة الدول","الدول"]:
        if not data["players"]: await update.message.reply_text("لا يوجد دول."); return
        msg = f"{box_title('🗺️','الدول')} ({len(data['players'])} دولة)\n\n"
        for i,(puid,pp) in enumerate(sorted(data["players"].items(),key=lambda x:x[1].get("xp",0),reverse=True),1):
            lvl = get_level(pp.get("xp",0))
            tag = " 🗡️" if pp.get("traitor") else ""
            msg += f"{i}. {lvl['emoji']} *{pp['country_name']}*{tag} — {pp['region']}\n    💰{pp['gold']:,} | ⚔️{pp['army']:,} | 🗺️{pp['territories']}\n\n"
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    # ======= خريطة =======
    if text in ["خريطة","الخريطة"]:
        if not data["players"]: await update.message.reply_text("لا يوجد دول."); return
        await update.message.reply_text("🗺️ جاري التوليد...")
        try:
            buf = generate_map(data["players"], data)
            cap = "🗺️ *خريطة الشرق الاوسط*\n"
            for pp in data["players"].values():
                lvl = get_level(pp.get("xp",0))
                cap += f"{lvl['emoji']} *{pp['country_name']}* ← {pp['region']}\n"
            await update.message.reply_photo(photo=buf, caption=cap, parse_mode="Markdown")
        except Exception as e: await update.message.reply_text(f"❌ خطا: {e}")
        return

    # ======= مساعدة =======
    if text in ["مساعدة","اوامر","help"]:
        await update.message.reply_text(
            f"{box_title('📖','اوامر اللعبة')}\n\n"
            f"🔹 *انضمام:*\n`انشاء دولة` | `كودي`\n\n"
            f"🔹 *معلومات:*\n`حالة دولتي` | `قائمة الدول` | `خريطة` | `المتصدرين` | `المضائق`\n\n"
            f"🔹 *اقتصاد:*\n`بناء مزرعة` | `بناء منشاة` | `بناء بنية تحتية`\n"
            f"`العاصمة [اسم]` | `تحويل [مبلغ] [كود]`\n"
            f"`البنك الدولي` — اقترض ذهب وسدّد من الحصاد\n"
            f"💡 الحصاد تلقائي كل 15 دقيقة\n\n"
            f"🔹 *جيش:*\n`تجنيد [عدد]` | `هجوم على [اسم]`\n\n"
            f"🔹 *دبلوماسية:*\n`تحالف مع [اسم]` — بيبعت طلب للقبول\n"
            f"`حل الحلف مع [اسم]` — بالتراضي\n"
            f"`نقض الحلف مع [اسم]` — بعقوبات 🗡️\n"
            f"`ازالة الخيانة` — 2000ذ\n\n"
            f"🔹 *المضائق:*\n`اغلق/افتح مضيق [اسم]`\nالاسماء: هرمز | باب المندب | السويس\n\n"
            f"{'⚔️ الحروب: مفتوحة' if data.get('wars_enabled',True) else '🕊️ الحروب: موقوفة'}",
            parse_mode="Markdown")
        return

    # ======= اوامر الادمن =======
    if is_admin(uid):
        # انشاء دولة نصي (بدون علم)
        if text.startswith("دولة "):
            parts = text.split()
            if len(parts)<4:
                await update.message.reply_text("الصيغة: دولة [المنطقة] [الاسم] [الكود]"); return
            code=parts[-1].upper(); region=parts[1]; cname=" ".join(parts[2:-1])
            if code not in data["pending_codes"]: await update.message.reply_text(f"الكود {code} مش موجود."); return
            if region not in AVAILABLE_REGIONS: await update.message.reply_text(f"'{region}' مش في القائمة."); return
            for _,pp in data["players"].items():
                if pp["region"]==region: await update.message.reply_text(f"'{region}' محجوزة."); return
            pid = data["pending_codes"].pop(code)
            pl  = new_player(region, cname, pid)
            data["players"][str(pid)] = pl; save_data(data)
            await update.message.reply_text(f"✅ *{cname}* ← {region} | كود: `{pl['player_code']}`", parse_mode="Markdown")
            try: await context.bot.send_message(chat_id=pid, text=f"🎊 *دولتك اتفعّلت!*\n🏳️ *{cname}*\nاكتب *مساعدة*", parse_mode="Markdown")
            except: pass
            return

        # حذف دولة
        if text.startswith("حذف دولة "):
            cname = text.replace("حذف دولة","").strip()
            for puid,pp in list(data["players"].items()):
                if pp["country_name"]==cname:
                    del data["players"][puid]; save_data(data)
                    await update.message.reply_text(f"✅ تم حذف {cname}."); return
            await update.message.reply_text(f"❌ مش لاقي '{cname}'."); return

        # تحويل ملكية دولة
        if text.startswith("تحويل ملكية "):
            # الصيغة: تحويل ملكية [اسم الدولة] الى [كود اللاعب الجديد]
            parts = text.replace("تحويل ملكية","").strip().split(" الى ")
            if len(parts)!=2:
                await update.message.reply_text("الصيغة: تحويل ملكية [اسم الدولة] الى [user_id]"); return
            cname = parts[0].strip(); new_uid = parts[1].strip()
            for puid,pp in list(data["players"].items()):
                if pp["country_name"]==cname:
                    data["players"][new_uid] = data["players"].pop(puid)
                    save_data(data)
                    await update.message.reply_text(f"✅ ملكية {cname} تحولت الى ID: {new_uid}"); return
            await update.message.reply_text(f"❌ مش لاقي '{cname}'."); return

        # فتح/قفل الحروب
        if text in ["اقفل الحروب","وقف الحروب"]:
            data["wars_enabled"] = False
            save_data(data)
            await update.message.reply_text("🕊️ *تم إيقاف الحروب!* لا أحد يستطيع الهجوم الآن.", parse_mode="Markdown"); return

        if text in ["افتح الحروب","شغّل الحروب","شغل الحروب"]:
            data["wars_enabled"] = True
            save_data(data)
            await update.message.reply_text("⚔️ *تم فتح الحروب!* يمكن للدول الهجوم الآن.", parse_mode="Markdown"); return

        # الطلبات المعلقة
        if text == "الطلبات":
            if not data["pending_codes"]: await update.message.reply_text("✅ مفيش طلبات."); return
            msg = f"{box_title('📋','طلبات الانضمام')}\n\n"
            for c,v in data["pending_codes"].items():
                msg += f"• `{c}` — ID: `{v}`\n"
            await update.message.reply_text(msg, parse_mode="Markdown"); return

        # اوامر الادمن
        if text in ["اوامر الادمن","ادمن"]:
            await update.message.reply_text(
                f"{box_title('🔧','اوامر الادمن')}\n\n"
                f"• `دولة [منطقة] [اسم] [كود]` — انشاء دولة\n"
                f"• `حذف دولة [اسم]` — حذف دولة\n"
                f"• `تحويل ملكية [اسم] الى [user_id]` — تغيير الملكية\n"
                f"• `الطلبات` — شوف طلبات الانضمام\n"
                f"• `اقفل الحروب` / `افتح الحروب`\n"
                f"• ارسل صورة + `دولة [منطقة] [اسم] [كود]` لاضافة علم",
                parse_mode="Markdown"); return

# ==================== Callbacks ====================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid   = query.from_user.id
    data  = load_data()
    p     = get_player(data, uid)

    if query.data == "cancel":
        await query.edit_message_text("❌ تم الالغاء."); return

    # ---- القرض ----
    if query.data.startswith("loan_"):
        loan_id = query.data.replace("loan_","")
        if not p: await query.edit_message_text("❌ مش مسجل."); return
        loan_def = next((l for l in LOAN_OPTIONS if l["id"]==loan_id), None)
        if not loan_def: await query.edit_message_text("❌ قرض غير معروف."); return
        active = p.get("loans",[])
        if len(active) >= 2:
            await query.edit_message_text("❌ عندك 2 قروض بالفعل. سدّد أولاً."); return
        total_due = int(loan_def["amount"] * (1+loan_def["interest"]))
        new_loan  = {
            "id": loan_id,
            "name": loan_def["name"],
            "amount": loan_def["amount"],
            "due": total_due,
            "remaining_cycles": loan_def["due_cycles"],
        }
        data["players"][str(uid)]["gold"]  = p["gold"] + loan_def["amount"]
        data["players"][str(uid)]["loans"] = active + [new_loan]
        save_data(data)
        await query.edit_message_text(
            f"🏦 *تم صرف القرض!*\n{sep()}\n"
            f"{loan_def['emoji']} {loan_def['name']}\n"
            f"💵 المبلغ: +{loan_def['amount']:,}ذ\n"
            f"💰 رصيدك الآن: {p['gold']+loan_def['amount']:,}ذ\n"
            f"{sep()}\n"
            f"📅 السداد: {total_due:,}ذ خلال {loan_def['due_cycles']} دورات حصاد\n"
            f"⚠️ عدم السداد = عقوبة 50% إضافية!",
            parse_mode="Markdown")
        return

    # ---- قبول التحالف ----
    if query.data.startswith("ally_accept_"):
        req_key = query.data.replace("ally_accept_","")
        req     = data.get("alliance_requests",{}).get(req_key)
        if not req: await query.edit_message_text("❌ انتهت صلاحية الطلب."); return
        fu,fn = req["from_uid"], req["from_name"]
        tu,tn = req["to_uid"],   req["to_name"]
        for x,y in [(fu,tn),(tu,fn)]:
            data["players"].setdefault(x,{}).setdefault("allies",[])
            if y not in data["players"][x]["allies"]:
                data["players"][x]["allies"].append(y)
        del data["alliance_requests"][req_key]
        save_data(data)
        await query.edit_message_text(f"✅ *قبلت التحالف مع {fn}!*\n🤝 انتما الان حلفاء!", parse_mode="Markdown")
        try:
            await context.bot.send_message(chat_id=int(fu),
                text=f"🎉 *{tn} قبل التحالف!*\nانتما الان حلفاء رسميون 🤝", parse_mode="Markdown")
        except: pass
        return

    # ---- رفض التحالف ----
    if query.data.startswith("ally_reject_"):
        req_key = query.data.replace("ally_reject_","")
        req     = data.get("alliance_requests",{}).get(req_key)
        if not req: await query.edit_message_text("❌ انتهت صلاحية الطلب."); return
        fu,fn = req["from_uid"], req["from_name"]
        tn    = req["to_name"]
        del data["alliance_requests"][req_key]
        save_data(data)
        await query.edit_message_text(f"❌ رفضت التحالف مع {fn}.")
        try:
            await context.bot.send_message(chat_id=int(fu),
                text=f"❌ *{tn} رفض التحالف.*", parse_mode="Markdown")
        except: pass
        return

    # ---- قبول حل الحلف ----
    if query.data.startswith("dissolve_accept_"):
        req_key = query.data.replace("dissolve_accept_","")
        req     = data.get("dissolve_requests",{}).get(req_key)
        if not req: await query.edit_message_text("❌ انتهت صلاحية الطلب."); return
        fu,fn = req["from_uid"], req["from_name"]
        tu,tn = req["to_uid"],   req["to_name"]
        for x,y in [(fu,tn),(tu,fn)]:
            if x in data["players"]:
                data["players"][x]["allies"] = [a for a in data["players"][x].get("allies",[]) if a!=y]
        del data["dissolve_requests"][req_key]
        save_data(data)
        await query.edit_message_text(f"🤝 *تم حل الحلف مع {fn} بالتراضي.* ✅", parse_mode="Markdown")
        try:
            await context.bot.send_message(chat_id=int(fu),
                text=f"🤝 *{tn} وافق على حل الحلف.* لا عقوبات ✅", parse_mode="Markdown")
        except: pass
        return

    # ---- رفض حل الحلف ----
    if query.data.startswith("dissolve_reject_"):
        req_key = query.data.replace("dissolve_reject_","")
        req     = data.get("dissolve_requests",{}).get(req_key)
        if not req: await query.edit_message_text("❌ انتهت صلاحية الطلب."); return
        fu = req["from_uid"]; tn = req["to_name"]
        del data["dissolve_requests"][req_key]
        save_data(data)
        await query.edit_message_text("❌ رفضت حل الحلف. التحالف مستمر 🤝")
        try:
            await context.bot.send_message(chat_id=int(fu),
                text=f"❌ *{tn} رفض حل الحلف.* التحالف مستمر 🤝", parse_mode="Markdown")
        except: pass
        return

    # ---- بناء منشاة صناعية ----
    if query.data.startswith("build_"):
        resource = query.data.replace("build_","")
        if not p: await query.edit_message_text("❌ مش مسجل."); return
        if resource not in RESOURCE_FACILITIES: await query.edit_message_text("❌ مورد غير معروف."); return
        f    = RESOURCE_FACILITIES[resource]
        cost = f["base_cost"]
        if p["gold"] < cost:
            await query.edit_message_text(f"❌ محتاج {cost:,}ذ. عندك {p['gold']:,}."); return
        data["players"][str(uid)]["gold"] -= cost
        facs = data["players"][str(uid)].get("facilities",{})
        facs[resource] = facs.get(resource,0)+1
        data["players"][str(uid)]["facilities"] = facs
        leveled_up, new_lvl = add_xp(data, uid, 120)
        save_data(data)
        msg = (f"🏭 *تم البناء!*\n{'─'*28}\n{f['emoji']} *{f['name']}*\n"
               f"📦 +{f['amount']} {resource}/دورة\n💰 {p['gold']-cost:,}ذ متبقي\n⭐+120")
        if leveled_up: msg += f"\n🎊 {new_lvl['name']} {new_lvl['emoji']}"
        await query.edit_message_text(msg, parse_mode="Markdown")
        return

    # ---- زراعة محصول ----
    if query.data.startswith("farm_"):
        crop = query.data.replace("farm_","")
        if not p: await query.edit_message_text("❌ مش مسجل."); return
        if crop not in FARM_CROPS: await query.edit_message_text("❌ محصول غير معروف."); return
        fc   = FARM_CROPS[crop]
        cost = get_farm_cost(data, crop)
        if p["gold"] < cost:
            await query.edit_message_text(f"❌ محتاج {cost:,}ذ. عندك {p['gold']:,}."); return
        preferred = REGION_PREFERRED_CROPS.get(p.get("region",""),[])
        amount    = int(fc["amount"]*1.5) if crop in preferred else fc["amount"]
        bonus_txt = " (+50% ⭐)" if crop in preferred else ""
        data["players"][str(uid)]["gold"] -= cost
        crops_inv = data["players"][str(uid)].get("crops",{})
        crops_inv[crop] = crops_inv.get(crop,0)+1
        data["players"][str(uid)]["crops"] = crops_inv
        ca = data["players"][str(uid)].get("crops_amount",{})
        ca[crop] = amount
        data["players"][str(uid)]["crops_amount"] = ca
        leveled_up, new_lvl = add_xp(data, uid, 70)
        save_data(data)
        msg = (f"🌾 *تمت الزراعة!*\n{'─'*28}\n{fc['emoji']} *{fc['name']}*{bonus_txt}\n"
               f"📦 {amount}طن/دورة | يُباع تلقائياً\n💰 {p['gold']-cost:,}ذ متبقي\n⭐+70")
        if leveled_up: msg += f"\n🎊 {new_lvl['name']} {new_lvl['emoji']}"
        await query.edit_message_text(msg, parse_mode="Markdown")
        return

# ==================== /start ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name
    await update.message.reply_text(
        f"🌍 *اهلاً {name} في لعبة الشرق الاوسط!*\n{sep('═')}\n\n"
        f"🎮 ابنِ دولتك وطورها\n⚔️ جند جيوشك واحتل الاراضي\n"
        f"🤝 تحالف مع الدول الاخرى\n🌾 المحاصيل تُباع تلقائياً!\n"
        f"⚓ تحكم في مضيق السويس وهرمز وباب المندب\n\n"
        f"{sep()}\n▶️ *انشاء دولة* | 📖 *مساعدة*",
        parse_mode="Markdown")

# ==================== main ====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_message))

    loop = asyncio.get_event_loop()
    loop.create_task(disaster_loop(app))
    loop.create_task(harvest_loop(app))

    print("✅ البوت شغال!")
    app.run_polling()

if __name__ == "__main__":
    main()
