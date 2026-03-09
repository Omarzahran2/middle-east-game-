"""
🗺️ لعبة الشرق الأوسط الجيوسياسية
Middle East Geopolitical Game Bot
بوت تليجرام - أوامر عربية طبيعية
"""

import logging
import random
import string
import json
import os
import io
import time
from PIL import Image, ImageDraw, ImageFont
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, ContextTypes,
    MessageHandler, filters
)

# ==================== إعدادات ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID  = int(os.environ.get("ADMIN_ID", "0"))
DATA_FILE = "game_data.json"
MAP_FILE  = "map_base.png"
FLAGS_DIR = "flags"
os.makedirs(FLAGS_DIR, exist_ok=True)

TAX_COOLDOWN = 15 * 60   # 15 دقيقة بالثواني
FLAG_SIZE_MAIN = 200     # حجم العلم الرئيسي (كبير)
FLAG_SIZE_SMALL = 100    # حجم العلم للأجزاء الثانوية

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ==================== إحداثيات الدول (2048x2048) ====================
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

# ==================== تحميل وحفظ البيانات ====================
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"players": {}, "pending_codes": {}, "unclaimed_lands": {}}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ==================== مساعد ====================
def generate_code():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

def get_player(data, user_id):
    return data["players"].get(str(user_id))

def is_admin(user_id):
    return user_id == ADMIN_ID

def find_player_by_code(data, code):
    """ابحث عن لاعب بكوده"""
    for uid, p in data["players"].items():
        if p.get("player_code") == code.upper():
            return uid, p
    return None, None

# ==================== توليد الخريطة ====================
def generate_map(players: dict) -> io.BytesIO:
    img = Image.open(MAP_FILE).convert("RGBA")
    draw = ImageDraw.Draw(img)

    for uid, p in players.items():
        region = p.get("region")
        country_name = p.get("country_name", region)
        flag_path = os.path.join(FLAGS_DIR, f"{region}.png")
        if region not in REGION_COORDS:
            continue

        for i, (cx, cy) in enumerate(REGION_COORDS[region]):
            size = FLAG_SIZE_MAIN if i == 0 else FLAG_SIZE_SMALL
            if os.path.exists(flag_path):
                flag = Image.open(flag_path).convert("RGBA")
                flag = flag.resize((size, int(size * 0.6)), Image.LANCZOS)
                fw, fh = flag.size
                fx, fy = cx - fw // 2, cy - fh // 2
                img.paste(flag, (fx, fy), flag)
                draw.rectangle([fx-3, fy-3, fx+fw+3, fy+fh+3], outline="white", width=4)
                if i == 0:
                    draw.text((cx, fy + fh + 6), country_name, fill="black", anchor="mt")
            else:
                r = 30 if i == 0 else 15
                draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill="#e74c3c", outline="white", width=3)
                if i == 0:
                    draw.text((cx, cy + r + 6), country_name, fill="black", anchor="mt")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

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

    # ======= أدمن: إنشاء دولة مع علم (صورة + caption) =======
    if is_admin(user_id) and update.message.photo and text.startswith("دولة "):
        parts = text.split()
        if len(parts) < 4:
            await update.message.reply_text(
                "❌ الصيغة:\n`دولة [المنطقة] [اسم الدولة] [الكود]`\nوارفق صورة العلم",
                parse_mode="Markdown"
            )
            return

        code         = parts[-1].upper()
        region       = parts[1]
        country_name = " ".join(parts[2:-1])

        if code not in data["pending_codes"]:
            await update.message.reply_text(f"❌ الكود `{code}` مش موجود.", parse_mode="Markdown")
            return
        if region not in AVAILABLE_REGIONS:
            await update.message.reply_text(f"⚠️ المنطقة '{region}' مش في القائمة.\nالمتاح: {', '.join(AVAILABLE_REGIONS)}")
            return
        for uid, p in data["players"].items():
            if p["region"] == region:
                await update.message.reply_text(f"❌ '{region}' محجوزة من {p['country_name']}.")
                return

        photo     = update.message.photo[-1]
        flag_file = await context.bot.get_file(photo.file_id)
        flag_path = os.path.join(FLAGS_DIR, f"{region}.png")
        await flag_file.download_to_drive(flag_path)

        player_id  = data["pending_codes"].pop(code)
        player_code = generate_code()
        data["players"][str(player_id)] = {
            "country_name": country_name,
            "region":       region,
            "gold":         1000,
            "army":         100,
            "factories":    1,
            "farms":        1,
            "territories":  1,
            "allies":       [],
            "at_war":       [],
            "last_tax":     0,
            "player_code":  player_code,
        }
        save_data(data)

        await update.message.reply_text(
            f"✅ تم إنشاء الدولة مع العلم!\n\n"
            f"🏳️ *{country_name}* ← {region}\n"
            f"🔑 كود اللاعب: `{player_code}`",
            parse_mode="Markdown"
        )
        try:
            await context.bot.send_message(
                chat_id=player_id,
                text=(
                    f"🎉 تم تفعيل دولتك!\n\n"
                    f"🏳️ *{country_name}* ← {region}\n\n"
                    f"💰 ذهب: 1,000 | ⚔️ جيش: 100\n\n"
                    f"اكتب *مساعدة* لشوف الأوامر!"
                ),
                parse_mode="Markdown"
            )
        except Exception:
            pass
        return

    # ======= أوامر اللاعبين =======

    # انشاء دولة
    if text == "انشاء دولة":
        player = get_player(data, user_id)
        if player:
            await update.message.reply_text(
                f"⚠️ عندك بالفعل دولة: *{player['country_name']}*",
                parse_mode="Markdown"
            )
            return
        existing_code = next((c for c, uid in data["pending_codes"].items() if uid == user_id), None)
        if existing_code:
            await update.message.reply_text(
                f"⏳ طلبك منتظر!\nكودك: `{existing_code}`\nابعته للأدمن.",
                parse_mode="Markdown"
            )
            return
        code = generate_code()
        while code in data["pending_codes"]:
            code = generate_code()
        data["pending_codes"][code] = user_id
        save_data(data)
        await update.message.reply_text(
            f"🎮 أهلاً {user_name}!\n\nكودك:\n```\n{code}\n```\n\nابعته للأدمن عشان يفعّل دولتك.",
            parse_mode="Markdown"
        )
        return

    # كودي
    if text in ["كودي", "كود اللاعب", "الكود"]:
        player = get_player(data, user_id)
        if not player:
            await update.message.reply_text("❌ مش مسجل في اللعبة.")
            return
        await update.message.reply_text(
            f"🔑 كودك الشخصي:\n```\n{player.get('player_code', 'غير متوفر')}\n```\n\nاستخدمه لاستقبال التحويلات.",
            parse_mode="Markdown"
        )
        return

    # حالة دولتي
    if text in ["حالة دولتي", "دولتي", "وضعي"]:
        player = get_player(data, user_id)
        if not player:
            await update.message.reply_text("❌ مش مسجل.\nاكتب *انشاء دولة*", parse_mode="Markdown")
            return
        p = player
        cooldown_left = TAX_COOLDOWN - (time.time() - p.get("last_tax", 0))
        tax_status = "✅ جاهزة" if cooldown_left <= 0 else f"⏳ {int(cooldown_left // 60)} دقيقة"
        msg = (
            f"🏳️ *{p['country_name']}* ({p['region']})\n\n"
            f"💰 الذهب: {p['gold']:,}\n"
            f"⚔️ الجيش: {p['army']:,}\n"
            f"🏭 المصانع: {p['factories']}\n"
            f"🌾 المزارع: {p['farms']}\n"
            f"🗺️ الأراضي: {p['territories']}\n\n"
            f"💵 جمع الضرائب: {tax_status}\n\n"
            f"🤝 التحالفات: {', '.join(p['allies']) if p['allies'] else 'لا يوجد'}\n"
            f"⚔️ الحروب: {', '.join(p['at_war']) if p['at_war'] else 'في سلام'}"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    # قائمة الدول
    if text in ["قائمة الدول", "الدول", "اللاعبين"]:
        if not data["players"]:
            await update.message.reply_text("🗺️ لا يوجد دول بعد.")
            return
        msg = "🗺️ *الدول في اللعبة:*\n\n"
        for uid, p in data["players"].items():
            msg += f"• *{p['country_name']}* ({p['region']}) — ذهب: {p['gold']:,} | جيش: {p['army']:,} | أراضي: {p['territories']}\n"
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    # جمع الضرائب (كول داون 15 دقيقة)
    if text in ["جمع الضرائب", "اجمع الضرائب", "جمع موارد"]:
        player = get_player(data, user_id)
        if not player:
            await update.message.reply_text("❌ مش مسجل في اللعبة.")
            return
        now = time.time()
        last_tax = player.get("last_tax", 0)
        cooldown_left = TAX_COOLDOWN - (now - last_tax)
        if cooldown_left > 0:
            mins = int(cooldown_left // 60)
            secs = int(cooldown_left % 60)
            await update.message.reply_text(
                f"⏳ لازم تستنى *{mins}:{secs:02d}* دقيقة قبل ما تجمع تاني!",
                parse_mode="Markdown"
            )
            return
        income = (player["factories"] * 150) + (player["farms"] * 80) + (player["territories"] * 50) + 200
        data["players"][str(user_id)]["gold"]    += income
        data["players"][str(user_id)]["last_tax"] = now
        save_data(data)
        await update.message.reply_text(
            f"💰 *تم جمع الموارد!*\n\n"
            f"🏭 مصانع ({player['factories']}): +{player['factories']*150:,}\n"
            f"🌾 مزارع ({player['farms']}): +{player['farms']*80:,}\n"
            f"🗺️ أراضي ({player['territories']}): +{player['territories']*50:,}\n"
            f"👑 دخل أساسي: +200\n\n"
            f"✅ الإجمالي: +{income:,} ذهب\n"
            f"💰 رصيدك الكلي: {player['gold']+income:,}\n\n"
            f"⏳ القادم بعد 15 دقيقة",
            parse_mode="Markdown"
        )
        return

    # بناء مصنع
    if text in ["بناء مصنع", "ابني مصنع"]:
        player = get_player(data, user_id)
        if not player:
            await update.message.reply_text("❌ مش مسجل في اللعبة.")
            return
        cost = 500
        if player["gold"] < cost:
            await update.message.reply_text(f"❌ محتاج {cost} ذهب. عندك {player['gold']:,} فقط.")
            return
        data["players"][str(user_id)]["gold"]     -= cost
        data["players"][str(user_id)]["factories"] += 1
        save_data(data)
        await update.message.reply_text(
            f"🏭 تم بناء مصنع!\nالمصانع: {player['factories']+1} | الذهب: {player['gold']-cost:,}"
        )
        return

    # بناء مزرعة
    if text in ["بناء مزرعة", "ابني مزرعة"]:
        player = get_player(data, user_id)
        if not player:
            await update.message.reply_text("❌ مش مسجل في اللعبة.")
            return
        cost = 300
        if player["gold"] < cost:
            await update.message.reply_text(f"❌ محتاج {cost} ذهب. عندك {player['gold']:,} فقط.")
            return
        data["players"][str(user_id)]["gold"]  -= cost
        data["players"][str(user_id)]["farms"] += 1
        save_data(data)
        await update.message.reply_text(
            f"🌾 تم بناء مزرعة!\nالمزارع: {player['farms']+1} | الذهب: {player['gold']-cost:,}"
        )
        return

    # تجنيد
    if text.startswith("تجنيد "):
        player = get_player(data, user_id)
        if not player:
            await update.message.reply_text("❌ مش مسجل في اللعبة.")
            return
        try:
            amount = int(text.replace("تجنيد", "").strip())
            if amount <= 0:
                raise ValueError
            cost = amount * 10
            if player["gold"] < cost:
                await update.message.reply_text(f"❌ تجنيد {amount:,} يكلف {cost:,} ذهب. عندك {player['gold']:,} فقط.")
                return
            data["players"][str(user_id)]["gold"] -= cost
            data["players"][str(user_id)]["army"] += amount
            save_data(data)
            await update.message.reply_text(
                f"⚔️ تم تجنيد {amount:,} جندي!\nالجيش: {player['army']+amount:,} | الذهب: {player['gold']-cost:,}"
            )
        except ValueError:
            await update.message.reply_text("❌ مثال: تجنيد 100")
        return

    # هجوم
    if text.startswith("هجوم على "):
        player = get_player(data, user_id)
        if not player:
            await update.message.reply_text("❌ مش مسجل في اللعبة.")
            return

        target_name = text.replace("هجوم على", "").strip()
        target_player, target_uid = None, None

        # هجوم على أرض بدون صاحب
        unclaimed = data.get("unclaimed_lands", {})
        if target_name in unclaimed:
            land = unclaimed[target_name]
            defend_power = land.get("defense", 50) * random.uniform(0.7, 1.3)
            attack_power = player["army"] * random.uniform(0.7, 1.3)
            if attack_power > defend_power:
                data["players"][str(user_id)]["territories"] += 1
                del data["unclaimed_lands"][target_name]
                losses = random.randint(5, 30)
                data["players"][str(user_id)]["army"] = max(0, player["army"] - losses)
                save_data(data)
                await update.message.reply_text(
                    f"⚔️ *انتصار على أرض '{target_name}'!*\n\n"
                    f"🗺️ ضممت أرض جديدة!\n💀 خسائر: {losses} جندي",
                    parse_mode="Markdown"
                )
            else:
                losses = random.randint(20, 80)
                data["players"][str(user_id)]["army"] = max(0, player["army"] - losses)
                save_data(data)
                await update.message.reply_text(
                    f"❌ *هزيمة أمام دفاعات '{target_name}'!*\n\n💀 خسائر: {losses} جندي",
                    parse_mode="Markdown"
                )
            return

        # هجوم على لاعب
        for uid, p in data["players"].items():
            if p["country_name"] == target_name or p["region"] == target_name:
                target_player, target_uid = p, uid
                break

        if not target_player:
            await update.message.reply_text(
                f"❌ مش لاقي '{target_name}'.\nاكتب *قائمة الدول* للأراضي المتاحة.",
                parse_mode="Markdown"
            )
            return
        if target_uid == str(user_id):
            await update.message.reply_text("❌ مينفعش تهاجم نفسك!")
            return
        if target_player["country_name"] in player.get("allies", []):
            await update.message.reply_text(f"❌ {target_player['country_name']} حليفك!")
            return

        att = player["army"] * random.uniform(0.7, 1.3)
        deff = target_player["army"] * random.uniform(0.7, 1.3)

        if att > deff:
            loot = min(target_player["gold"] // 3, 500)
            losses_att = random.randint(10, 50)
            losses_def = random.randint(50, 150)
            data["players"][str(user_id)]["gold"]        += loot
            data["players"][str(user_id)]["territories"] += 1
            data["players"][str(user_id)]["army"]         = max(0, player["army"] - losses_att)
            data["players"][target_uid]["gold"]           -= loot
            data["players"][target_uid]["territories"]    = max(1, target_player["territories"] - 1)
            data["players"][target_uid]["army"]           = max(0, target_player["army"] - losses_def)
            save_data(data)
            await update.message.reply_text(
                f"⚔️ *انتصار!*\n\n"
                f"🏆 {player['country_name']} هزم {target_player['country_name']}\n"
                f"💰 غنيمة: {loot:,} ذهب\n🗺️ أرض جديدة!\n"
                f"💀 خسائرك: {losses_att} | خسائر العدو: {losses_def}",
                parse_mode="Markdown"
            )
            try:
                await context.bot.send_message(
                    chat_id=int(target_uid),
                    text=f"⚠️ *{player['country_name']} هاجمك وانتصر!*\nخسرت {loot:,} ذهب وأرض.\nخسائر جيشك: {losses_def}",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
        else:
            losses_att = random.randint(50, 200)
            losses_def = random.randint(10, 50)
            data["players"][str(user_id)]["army"]  = max(0, player["army"] - losses_att)
            data["players"][target_uid]["army"]    = max(0, target_player["army"] - losses_def)
            save_data(data)
            await update.message.reply_text(
                f"⚔️ *هزيمة!*\n\n"
                f"❌ {player['country_name']} انهزم أمام {target_player['country_name']}\n"
                f"💀 خسائرك: {losses_att} | خسائر العدو: {losses_def}",
                parse_mode="Markdown"
            )
        return

    # تحالف مع
    if text.startswith("تحالف مع "):
        player = get_player(data, user_id)
        if not player:
            await update.message.reply_text("❌ مش مسجل في اللعبة.")
            return
        target_name = text.replace("تحالف مع", "").strip()
        for uid, p in data["players"].items():
            if p["country_name"] == target_name or p["region"] == target_name:
                if target_name in player.get("allies", []):
                    await update.message.reply_text(f"✅ أنت بالفعل حليف مع {target_name}.")
                    return
                data["players"][str(user_id)]["allies"].append(p["country_name"])
                data["players"][uid]["allies"].append(player["country_name"])
                save_data(data)
                await update.message.reply_text(f"🤝 تم التحالف مع *{p['country_name']}*!", parse_mode="Markdown")
                try:
                    await context.bot.send_message(
                        chat_id=int(uid),
                        text=f"🤝 *{player['country_name']}* أعلن التحالف معك!",
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass
                return
        await update.message.reply_text(f"❌ مش لاقي '{target_name}'.")
        return

    # إهداء أراضي: اهدي أرض [كود اللاعب]
    if text.startswith("اهدي أرض ") or text.startswith("اهدي ارض "):
        player = get_player(data, user_id)
        if not player:
            await update.message.reply_text("❌ مش مسجل في اللعبة.")
            return
        if player["territories"] <= 1:
            await update.message.reply_text("❌ ما عندكش أراضي كافية للإهداء (الحد الأدنى 1).")
            return
        target_code = text.split()[-1].upper()
        target_uid, target_player = find_player_by_code(data, target_code)
        if not target_player:
            await update.message.reply_text(f"❌ مش لاقي لاعب بالكود `{target_code}`.", parse_mode="Markdown")
            return
        if target_uid == str(user_id):
            await update.message.reply_text("❌ مينفعش تهدي نفسك!")
            return
        data["players"][str(user_id)]["territories"] -= 1
        data["players"][target_uid]["territories"]   += 1
        save_data(data)
        await update.message.reply_text(
            f"🎁 أهديت أرض لـ *{target_player['country_name']}*!\n"
            f"أراضيك الآن: {player['territories']-1}",
            parse_mode="Markdown"
        )
        try:
            await context.bot.send_message(
                chat_id=int(target_uid),
                text=f"🎁 *{player['country_name']}* أهداك أرض!\nأراضيك الآن: {target_player['territories']+1}",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        return

    # تحويل ذهب: تحويل [مبلغ] [كود اللاعب]
    if text.startswith("تحويل "):
        player = get_player(data, user_id)
        if not player:
            await update.message.reply_text("❌ مش مسجل في اللعبة.")
            return
        parts = text.split()
        if len(parts) != 3:
            await update.message.reply_text(
                "❌ الصيغة الصحيحة:\n`تحويل [المبلغ] [كود اللاعب]`\n\nمثال: `تحويل 500 ABC123`",
                parse_mode="Markdown"
            )
            return
        try:
            amount = int(parts[1])
            if amount <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("❌ المبلغ لازم يكون رقم أكبر من صفر.")
            return
        if player["gold"] < amount:
            await update.message.reply_text(f"❌ ما عندكش كفاية. عندك {player['gold']:,} ذهب بس.")
            return
        target_code = parts[2].upper()
        target_uid, target_player = find_player_by_code(data, target_code)
        if not target_player:
            await update.message.reply_text(f"❌ مش لاقي لاعب بالكود `{target_code}`.", parse_mode="Markdown")
            return
        if target_uid == str(user_id):
            await update.message.reply_text("❌ مينفعش تحول لنفسك!")
            return
        data["players"][str(user_id)]["gold"] -= amount
        data["players"][target_uid]["gold"]   += amount
        save_data(data)
        await update.message.reply_text(
            f"💸 تم تحويل *{amount:,}* ذهب لـ *{target_player['country_name']}*!\n"
            f"رصيدك: {player['gold']-amount:,}",
            parse_mode="Markdown"
        )
        try:
            await context.bot.send_message(
                chat_id=int(target_uid),
                text=f"💰 استلمت *{amount:,}* ذهب من *{player['country_name']}*!\nرصيدك: {target_player['gold']+amount:,}",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        return

    # خريطة
    if text in ["خريطة", "الخريطة", "map"]:
        if not data["players"]:
            await update.message.reply_text("🗺️ لا يوجد دول بعد.")
            return
        await update.message.reply_text("🗺️ جاري توليد الخريطة...")
        try:
            map_buf = generate_map(data["players"])
            caption = "🗺️ *خريطة الشرق الأوسط*\n\n"
            for uid, p in data["players"].items():
                caption += f"🏳️ *{p['country_name']}* ← {p['region']}\n"
            await update.message.reply_photo(photo=map_buf, caption=caption, parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ: {e}")
        return

    # مساعدة
    if text in ["مساعدة", "الأوامر", "اوامر", "help"]:
        await update.message.reply_text(
            "📖 *أوامر اللعبة:*\n\n"
            "🔹 *انضمام:*\n"
            "• `انشاء دولة` — طلب الانضمام\n"
            "• `كودي` — اعرف كودك الشخصي\n\n"
            "🔹 *معلومات:*\n"
            "• `حالة دولتي` — وضع دولتك\n"
            "• `قائمة الدول` — كل الدول\n"
            "• `خريطة` — الخريطة الحالية\n\n"
            "🔹 *اقتصاد:*\n"
            "• `جمع الضرائب` — كل 15 دقيقة\n"
            "• `بناء مصنع` — 500 ذهب\n"
            "• `بناء مزرعة` — 300 ذهب\n"
            "• `تحويل 500 [كود]` — حول ذهب\n\n"
            "🔹 *جيش:*\n"
            "• `تجنيد 100` — 10 ذهب/جندي\n"
            "• `هجوم على [اسم]` — هاجم دولة أو أرض\n\n"
            "🔹 *دبلوماسية:*\n"
            "• `تحالف مع [اسم]` — اعقد تحالف\n"
            "• `اهدي أرض [كود]` — أهدي أرض للاعب\n",
            parse_mode="Markdown"
        )
        return

    # ======= أوامر الأدمن =======
    if is_admin(user_id):

        # دولة (بدون علم - نصي فقط)
        if text.startswith("دولة "):
            parts = text.split()
            if len(parts) < 4:
                await update.message.reply_text(
                    "❌ الصيغة:\n`دولة [المنطقة] [اسم الدولة] [الكود]`\nوارفق صورة العلم",
                    parse_mode="Markdown"
                )
                return
            code         = parts[-1].upper()
            region       = parts[1]
            country_name = " ".join(parts[2:-1])
            if code not in data["pending_codes"]:
                await update.message.reply_text(f"❌ الكود `{code}` مش موجود.", parse_mode="Markdown")
                return
            if region not in AVAILABLE_REGIONS:
                await update.message.reply_text(f"⚠️ المنطقة '{region}' مش في القائمة.")
                return
            for uid, p in data["players"].items():
                if p["region"] == region:
                    await update.message.reply_text(f"❌ '{region}' محجوزة من {p['country_name']}.")
                    return
            player_id   = data["pending_codes"].pop(code)
            player_code = generate_code()
            data["players"][str(player_id)] = {
                "country_name": country_name,
                "region":       region,
                "gold":         1000,
                "army":         100,
                "factories":    1,
                "farms":        1,
                "territories":  1,
                "allies":       [],
                "at_war":       [],
                "last_tax":     0,
                "player_code":  player_code,
            }
            save_data(data)
            await update.message.reply_text(
                f"✅ تم إنشاء الدولة!\n🏳️ *{country_name}* ← {region}\n🔑 كود اللاعب: `{player_code}`",
                parse_mode="Markdown"
            )
            try:
                await context.bot.send_message(
                    chat_id=player_id,
                    text=f"🎉 دولتك اتفعّلت!\n🏳️ *{country_name}* ← {region}\n\nاكتب *مساعدة* لشوف الأوامر!",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
            return

        # إضافة أرض بدون صاحب
        if text.startswith("أضف أرض "):
            parts = text.split(maxsplit=3)
            # أضف أرض [اسم الأرض] [قوة الدفاع]
            if len(parts) < 4:
                await update.message.reply_text("❌ الصيغة: `أضف أرض [الاسم] [قوة الدفاع]`\nمثال: `أضف أرض الصحراء 80`", parse_mode="Markdown")
                return
            try:
                land_name   = parts[2]
                defense_val = int(parts[3])
            except (ValueError, IndexError):
                await update.message.reply_text("❌ قوة الدفاع لازم تكون رقم.")
                return
            if "unclaimed_lands" not in data:
                data["unclaimed_lands"] = {}
            data["unclaimed_lands"][land_name] = {"defense": defense_val}
            save_data(data)
            await update.message.reply_text(f"✅ تمت إضافة أرض '{land_name}' بقوة دفاع {defense_val}.")
            return

        # حذف دولة
        if text.startswith("حذف دولة "):
            country_name = text.replace("حذف دولة", "").strip()
            for uid, p in list(data["players"].items()):
                if p["country_name"] == country_name:
                    del data["players"][uid]
                    save_data(data)
                    await update.message.reply_text(f"✅ تم حذف {country_name}.")
                    return
            await update.message.reply_text(f"❌ مش لاقي '{country_name}'.")
            return

        # الطلبات المعلقة
        if text in ["الطلبات", "الكودات المعلقة"]:
            if not data["pending_codes"]:
                await update.message.reply_text("✅ مفيش طلبات معلقة.")
                return
            msg = "📋 *الطلبات:*\n\n"
            for code, uid in data["pending_codes"].items():
                msg += f"• كود: `{code}` — ID: `{uid}`\n"
            await update.message.reply_text(msg, parse_mode="Markdown")
            return

# ==================== /start ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌍 *أهلاً بك في لعبة الشرق الأوسط!*\n\n"
        "ابن دولتك، طور اقتصادك، جند جيشك!\n\n"
        "للبدء: *انشاء دولة*\n"
        "للمساعدة: *مساعدة*",
        parse_mode="Markdown"
    )

# ==================== تشغيل ====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_message))
    print("✅ البوت شغال!")
    app.run_polling()

if __name__ == "__main__":
    main()
