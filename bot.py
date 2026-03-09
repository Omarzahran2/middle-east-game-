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
from PIL import Image, ImageDraw, ImageFont
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, ContextTypes,
    MessageHandler, filters
)

# ==================== إعدادات ====================
BOT_TOKEN = "8734935129:AAFq1VOM9BLD415c7rdtBTBw1bmTo--trDO"
ADMIN_ID = 6396528253  # ضع الـ ID بتاعك هنا
DATA_FILE = "game_data.json"
MAP_FILE = "map_base.png"   # صورة الخريطة الأساسية
FLAGS_DIR = "flags"         # مجلد الأعلام  (flags/مصر.png مثلاً)
os.makedirs(FLAGS_DIR, exist_ok=True)

# ==================== إحداثيات الدول على الخريطة (2048x2048) ====================
REGION_COORDS = {
    "مصر":       [(378,  1077)],
    "تركيا":     [(532,  407), (192, 306)],    # آسيا + أوروبا
    "إيران":     [(1267, 642)],
    "الأردن":    [(662,  906)],
    "قطر":       [(1331, 1187)],
    "الإمارات":  [(1482, 1288)],
    "عُمان":     [(1610, 1509), (1549, 1149)], # الجنوب + مضيق هرمز
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

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ==================== الدول المتاحة ====================
AVAILABLE_REGIONS = [
    "مصر", "السعودية", "العراق", "سوريا", "تركيا",
    "إيران", "الأردن", "لبنان", "اليمن", "الإمارات",
    "قطر", "الكويت", "البحرين", "عُمان", "فلسطين",
    "إسرائيل", "ليبيا", "السودان"
]

# ==================== تحميل وحفظ البيانات ====================
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "players": {},       # user_id -> بيانات اللاعب
        "pending_codes": {}, # code -> user_id
        "game_started": False
    }

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

# ==================== توليد صورة الخريطة ====================
def generate_map(players: dict) -> io.BytesIO:
    """يرسم الخريطة مع أعلام الدول - يدعم الدول متعددة الأجزاء"""
    img = Image.open(MAP_FILE).convert("RGBA")
    draw = ImageDraw.Draw(img)

    FLAG_SIZE = 120

    for uid, p in players.items():
        region = p.get("region")
        country_name = p.get("country_name", region)
        flag_path = os.path.join(FLAGS_DIR, f"{region}.png")

        if region not in REGION_COORDS:
            continue

        coords_list = REGION_COORDS[region]  # دايماً list

        for i, (cx, cy) in enumerate(coords_list):
            if os.path.exists(flag_path):
                flag = Image.open(flag_path).convert("RGBA")
                # الجزء الأول: علم كامل - الأجزاء التانية: أصغر
                size = FLAG_SIZE if i == 0 else FLAG_SIZE // 2
                flag = flag.resize((size, int(size * 0.6)), Image.LANCZOS)
                fw, fh = flag.size
                fx = cx - fw // 2
                fy = cy - fh // 2
                img.paste(flag, (fx, fy), flag)
                draw.rectangle([fx-2, fy-2, fx+fw+2, fy+fh+2], outline="white", width=3)
                if i == 0:
                    draw.text((cx, fy + fh + 5), country_name, fill="black", anchor="mt")
            else:
                r = 25 if i == 0 else 15
                draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill="#e74c3c", outline="white", width=3)
                if i == 0:
                    draw.text((cx, cy + r + 5), country_name, fill="black", anchor="mt")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

# ==================== معالج الرسائل العربية ====================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # نحدد النص - ممكن يجي من رسالة نصية أو caption لصورة
    if update.message.text:
        text = update.message.text.strip()
    elif update.message.caption:
        text = update.message.caption.strip()
    else:
        text = ""

    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    data = load_data()

    # ======= أدمن: رفع علم مع أمر دولة =======
    if is_admin(user_id) and update.message.photo and text.startswith("دولة "):
        parts = text.split()
        if len(parts) < 4:
            await update.message.reply_text(
                "❌ الصيغة:\n`دولة [المنطقة] [اسم الدولة] [الكود]`\nوارفق صورة العلم",
                parse_mode="Markdown"
            )
            return

        code = parts[-1].upper()
        region = parts[1]
        country_name = " ".join(parts[2:-1])

        if code not in data["pending_codes"]:
            await update.message.reply_text(f"❌ الكود `{code}` مش موجود.", parse_mode="Markdown")
            return

        if region not in AVAILABLE_REGIONS:
            await update.message.reply_text(f"⚠️ المنطقة '{region}' مش في القائمة.")
            return

        for uid, p in data["players"].items():
            if p["region"] == region:
                await update.message.reply_text(f"❌ المنطقة '{region}' محجوزة من {p['country_name']}.")
                return

        # حفظ العلم
        photo = update.message.photo[-1]
        flag_file = await context.bot.get_file(photo.file_id)
        flag_path = os.path.join(FLAGS_DIR, f"{region}.png")
        await flag_file.download_to_drive(flag_path)

        player_id = data["pending_codes"].pop(code)
        data["players"][str(player_id)] = {
            "country_name": country_name,
            "region": region,
            "gold": 1000,
            "army": 100,
            "factories": 1,
            "farms": 1,
            "territories": 1,
            "allies": [],
            "at_war": []
        }
        save_data(data)

        await update.message.reply_text(
            f"✅ تم إنشاء الدولة مع العلم!\n\n"
            f"🏳️ *{country_name}* ← {region}\n"
            f"💰 ذهب: 1,000 | ⚔️ جيش: 100",
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
                f"⚠️ أنت بالفعل لديك دولة: *{player['country_name']}* ({player['region']})",
                parse_mode="Markdown"
            )
            return

        # تحقق لو اللاعب عنده كود معلق
        existing_code = None
        for code, uid in data["pending_codes"].items():
            if uid == user_id:
                existing_code = code
                break

        if existing_code:
            await update.message.reply_text(
                f"⏳ طلبك قيد الانتظار!\n\n"
                f"كودك هو: `{existing_code}`\n\n"
                f"ابعته للأدمن عشان يفعّل دولتك.",
                parse_mode="Markdown"
            )
            return

        code = generate_code()
        while code in data["pending_codes"]:
            code = generate_code()

        data["pending_codes"][code] = user_id
        save_data(data)

        await update.message.reply_text(
            f"🎮 أهلاً {user_name}!\n\n"
            f"كودك الشخصي هو:\n"
            f"```\n{code}\n```\n\n"
            f"📌 ابعت الكود ده للأدمن عشان يختارلك:\n"
            f"• المنطقة الجغرافية (مثلاً: مصر، العراق...)\n"
            f"• اسم دولتك اللي عايزه\n\n"
            f"⏳ استنى تأكيد الأدمن...",
            parse_mode="Markdown"
        )
        return

    # حالة دولتي
    if text in ["حالة دولتي", "دولتي", "وضعي"]:
        player = get_player(data, user_id)
        if not player:
            await update.message.reply_text(
                "❌ مش مسجل في اللعبة.\n\nاكتب *انشاء دولة* للانضمام.",
                parse_mode="Markdown"
            )
            return

        p = player
        msg = (
            f"🏳️ دولة: *{p['country_name']}*\n"
            f"🗺️ منطقة: {p['region']}\n\n"
            f"💰 الذهب: {p['gold']:,}\n"
            f"⚔️ الجيش: {p['army']:,}\n"
            f"🏭 المصانع: {p['factories']}\n"
            f"🌾 المزارع: {p['farms']}\n"
            f"🗺️ الأراضي: {p['territories']} منطقة\n\n"
            f"🤝 التحالفات: {', '.join(p['allies']) if p['allies'] else 'لا يوجد'}\n"
            f"⚠️ الحروب: {', '.join(p['at_war']) if p['at_war'] else 'في سلام'}"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    # قائمة الدول
    if text in ["قائمة الدول", "الدول", "اللاعبين"]:
        if not data["players"]:
            await update.message.reply_text("🗺️ لا يوجد دول مسجلة بعد.")
            return

        msg = "🗺️ *الدول في اللعبة:*\n\n"
        for uid, p in data["players"].items():
            msg += f"• *{p['country_name']}* ({p['region']}) - ذهب: {p['gold']:,} | جيش: {p['army']:,}\n"
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    # بناء مصنع
    if text in ["بناء مصنع", "ابني مصنع"]:
        player = get_player(data, user_id)
        if not player:
            await update.message.reply_text("❌ مش مسجل في اللعبة.")
            return
        cost = 500
        if player["gold"] < cost:
            await update.message.reply_text(f"❌ محتاج {cost} ذهب لبناء مصنع. عندك {player['gold']} فقط.")
            return
        data["players"][str(user_id)]["gold"] -= cost
        data["players"][str(user_id)]["factories"] += 1
        save_data(data)
        await update.message.reply_text(
            f"🏭 تم بناء مصنع جديد!\n"
            f"المصانع الكلية: {player['factories'] + 1}\n"
            f"الذهب المتبقي: {player['gold'] - cost:,}"
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
            await update.message.reply_text(f"❌ محتاج {cost} ذهب لبناء مزرعة. عندك {player['gold']} فقط.")
            return
        data["players"][str(user_id)]["gold"] -= cost
        data["players"][str(user_id)]["farms"] += 1
        save_data(data)
        await update.message.reply_text(
            f"🌾 تم بناء مزرعة جديدة!\n"
            f"المزارع الكلية: {player['farms'] + 1}\n"
            f"الذهب المتبقي: {player['gold'] - cost:,}"
        )
        return

    # تجنيد جيش
    if text.startswith("تجنيد "):
        player = get_player(data, user_id)
        if not player:
            await update.message.reply_text("❌ مش مسجل في اللعبة.")
            return
        try:
            amount = int(text.replace("تجنيد", "").strip())
            cost = amount * 10
            if player["gold"] < cost:
                await update.message.reply_text(f"❌ تجنيد {amount:,} جندي يكلف {cost:,} ذهب. عندك {player['gold']:,} فقط.")
                return
            data["players"][str(user_id)]["gold"] -= cost
            data["players"][str(user_id)]["army"] += amount
            save_data(data)
            await update.message.reply_text(
                f"⚔️ تم تجنيد {amount:,} جندي!\n"
                f"حجم الجيش الكلي: {player['army'] + amount:,}\n"
                f"الذهب المتبقي: {player['gold'] - cost:,}"
            )
        except ValueError:
            await update.message.reply_text("❌ اكتب العدد صح. مثال: تجنيد 100")
        return

    # هجوم
    if text.startswith("هجوم على "):
        player = get_player(data, user_id)
        if not player:
            await update.message.reply_text("❌ مش مسجل في اللعبة.")
            return

        target_name = text.replace("هجوم على", "").strip()
        target_player = None
        target_uid = None

        for uid, p in data["players"].items():
            if p["country_name"] == target_name or p["region"] == target_name:
                target_player = p
                target_uid = uid
                break

        if not target_player:
            await update.message.reply_text(f"❌ مش لاقي دولة اسمها '{target_name}'.")
            return

        if target_uid == str(user_id):
            await update.message.reply_text("❌ مينفعش تهاجم نفسك! 😅")
            return

        if target_name in player.get("allies", []):
            await update.message.reply_text(f"❌ {target_name} حليفك! مينفعش تهاجمه.")
            return

        # حساب نتيجة الحرب
        attacker_power = player["army"] * random.uniform(0.7, 1.3)
        defender_power = target_player["army"] * random.uniform(0.7, 1.3)

        if attacker_power > defender_power:
            # المهاجم يكسب
            loot = min(target_player["gold"] // 3, 500)
            data["players"][str(user_id)]["gold"] += loot
            data["players"][str(user_id)]["territories"] += 1
            data["players"][target_uid]["gold"] -= loot
            data["players"][target_uid]["territories"] = max(1, target_player["territories"] - 1)
            losses_att = random.randint(10, 50)
            losses_def = random.randint(50, 150)
            data["players"][str(user_id)]["army"] = max(0, player["army"] - losses_att)
            data["players"][target_uid]["army"] = max(0, target_player["army"] - losses_def)
            save_data(data)
            await update.message.reply_text(
                f"⚔️ *نتيجة المعركة - انتصار!*\n\n"
                f"🏆 {player['country_name']} هزم {target_player['country_name']}\n"
                f"💰 غنيمة: {loot:,} ذهب\n"
                f"🗺️ ضممت منطقة جديدة!\n"
                f"💀 خسائرك: {losses_att} جندي\n"
                f"💀 خسائر العدو: {losses_def} جندي",
                parse_mode="Markdown"
            )
        else:
            # المدافع يكسب
            losses_att = random.randint(50, 200)
            losses_def = random.randint(10, 50)
            data["players"][str(user_id)]["army"] = max(0, player["army"] - losses_att)
            data["players"][target_uid]["army"] = max(0, target_player["army"] - losses_def)
            save_data(data)
            await update.message.reply_text(
                f"⚔️ *نتيجة المعركة - هزيمة!*\n\n"
                f"❌ {player['country_name']} انهزم أمام {target_player['country_name']}\n"
                f"💀 خسائرك: {losses_att} جندي\n"
                f"💀 خسائر العدو: {losses_def} جندي",
                parse_mode="Markdown"
            )
        return

    # طلب تحالف
    if text.startswith("تحالف مع "):
        player = get_player(data, user_id)
        if not player:
            await update.message.reply_text("❌ مش مسجل في اللعبة.")
            return

        target_name = text.replace("تحالف مع", "").strip()
        found = False
        for uid, p in data["players"].items():
            if p["country_name"] == target_name or p["region"] == target_name:
                found = True
                if target_name in player.get("allies", []):
                    await update.message.reply_text(f"✅ أنت بالفعل حليف مع {target_name}.")
                    return
                data["players"][str(user_id)]["allies"].append(target_name)
                data["players"][uid]["allies"].append(player["country_name"])
                save_data(data)
                await update.message.reply_text(
                    f"🤝 تم إعلان التحالف مع *{target_name}*!",
                    parse_mode="Markdown"
                )
                return

        if not found:
            await update.message.reply_text(f"❌ مش لاقي دولة اسمها '{target_name}'.")
        return

    # جمع الضرائب
    if text in ["جمع الضرائب", "اجمع الضرائب", "جمع موارد"]:
        player = get_player(data, user_id)
        if not player:
            await update.message.reply_text("❌ مش مسجل في اللعبة.")
            return

        income = (player["factories"] * 150) + (player["farms"] * 80) + (player["territories"] * 50) + 200
        data["players"][str(user_id)]["gold"] += income
        save_data(data)
        await update.message.reply_text(
            f"💰 *تم جمع الموارد!*\n\n"
            f"🏭 من المصانع ({player['factories']}): {player['factories'] * 150:,}\n"
            f"🌾 من المزارع ({player['farms']}): {player['farms'] * 80:,}\n"
            f"🗺️ من الأراضي ({player['territories']}): {player['territories'] * 50:,}\n"
            f"👑 دخل أساسي: 200\n\n"
            f"✅ إجمالي: +{income:,} ذهب\n"
            f"💰 الرصيد الكلي: {player['gold'] + income:,}",
            parse_mode="Markdown"
        )
        return

    # خريطة
    if text in ["خريطة", "الخريطة", "map"]:
        if not data["players"]:
            await update.message.reply_text("🗺️ لا يوجد دول مسجلة بعد في الخريطة.")
            return
        await update.message.reply_text("🗺️ جاري توليد الخريطة...")
        try:
            map_buf = generate_map(data["players"])
            caption = "🗺️ *خريطة الشرق الأوسط الحالية*\n\n"
            for uid, p in data["players"].items():
                caption += f"🏳️ *{p['country_name']}* ← {p['region']}\n"
            await update.message.reply_photo(photo=map_buf, caption=caption, parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ حصل خطأ في توليد الخريطة: {e}")
        return

    # مساعدة
    if text in ["مساعدة", "الأوامر", "اوامر", "help"]:
        await update.message.reply_text(
            "📖 *أوامر اللعبة:*\n\n"
            "🔹 *انضمام:*\n"
            "• `انشاء دولة` - طلب الانضمام للعبة\n\n"
            "🔹 *معلومات:*\n"
            "• `حالة دولتي` - اعرف وضع دولتك\n"
            "• `قائمة الدول` - اشوف كل الدول\n\n"
            "🔹 *اقتصاد:*\n"
            "• `جمع الضرائب` - اجمع دخلك\n"
            "• `بناء مصنع` - ابني مصنع (500 ذهب)\n"
            "• `بناء مزرعة` - ابني مزرعة (300 ذهب)\n\n"
            "🔹 *جيش:*\n"
            "• `تجنيد 100` - جند جنود (10 ذهب/جندي)\n"
            "• `هجوم على [اسم الدولة]` - اهاجم دولة\n\n"
            "🔹 *دبلوماسية:*\n"
            "• `تحالف مع [اسم الدولة]` - اعقد تحالف\n",
            parse_mode="Markdown"
        )
        return

    # ======= أوامر الأدمن =======
    if is_admin(user_id):

        # دولة [منطقة] [اسم الدولة] [كود]
        if text.startswith("دولة "):
            parts = text.split()
            # مثال: دولة مصر كردستان ABC123
            if len(parts) < 4:
                await update.message.reply_text(
                    "❌ الصيغة الصحيحة:\n`دولة [المنطقة] [اسم الدولة] [الكود]`\n\n"
                    "مثال: `دولة مصر كردستان ABC123`",
                    parse_mode="Markdown"
                )
                return

            code = parts[-1].upper()
            region = parts[1]
            country_name = " ".join(parts[2:-1])

            if code not in data["pending_codes"]:
                await update.message.reply_text(f"❌ الكود `{code}` مش موجود أو استُخدم من قبل.", parse_mode="Markdown")
                return

            if region not in AVAILABLE_REGIONS:
                await update.message.reply_text(
                    f"⚠️ المنطقة '{region}' مش في القائمة.\n\n"
                    f"المناطق المتاحة:\n{', '.join(AVAILABLE_REGIONS)}"
                )
                return

            # تحقق إن المنطقة مش محجوزة
            for uid, p in data["players"].items():
                if p["region"] == region:
                    await update.message.reply_text(f"❌ المنطقة '{region}' محجوزة بالفعل من {p['country_name']}.")
                    return

            player_id = data["pending_codes"].pop(code)
            data["players"][str(player_id)] = {
                "country_name": country_name,
                "region": region,
                "gold": 1000,
                "army": 100,
                "factories": 1,
                "farms": 1,
                "territories": 1,
                "allies": [],
                "at_war": []
            }
            save_data(data)

            await update.message.reply_text(
                f"✅ تم إنشاء الدولة!\n\n"
                f"🏳️ الاسم: *{country_name}*\n"
                f"🗺️ المنطقة: {region}\n"
                f"💰 ذهب ابتدائي: 1,000\n"
                f"⚔️ جيش ابتدائي: 100",
                parse_mode="Markdown"
            )

            # إبلاغ اللاعب
            try:
                await context.bot.send_message(
                    chat_id=player_id,
                    text=(
                        f"🎉 تم تفعيل دولتك!\n\n"
                        f"🏳️ اسم الدولة: *{country_name}*\n"
                        f"🗺️ المنطقة: {region}\n\n"
                        f"💰 ذهب: 1,000\n"
                        f"⚔️ جيش: 100\n\n"
                        f"اكتب *مساعدة* لشوف الأوامر!"
                    ),
                    parse_mode="Markdown"
                )
            except Exception:
                pass
            return

        # حذف دولة
        if text.startswith("حذف دولة "):
            country_name = text.replace("حذف دولة", "").strip()
            for uid, p in list(data["players"].items()):
                if p["country_name"] == country_name:
                    del data["players"][uid]
                    save_data(data)
                    await update.message.reply_text(f"✅ تم حذف دولة {country_name}.")
                    return
            await update.message.reply_text(f"❌ مش لاقي دولة اسمها '{country_name}'.")
            return

        # الطلبات المعلقة
        if text in ["الطلبات", "الكودات المعلقة"]:
            if not data["pending_codes"]:
                await update.message.reply_text("✅ مفيش طلبات معلقة.")
                return
            msg = "📋 *الطلبات المعلقة:*\n\n"
            for code, uid in data["pending_codes"].items():
                msg += f"• كود: `{code}` - User ID: `{uid}`\n"
            await update.message.reply_text(msg, parse_mode="Markdown")
            return

# ==================== الأمر /start ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌍 *أهلاً بك في لعبة الشرق الأوسط الجيوسياسية!*\n\n"
        "ابن دولتك، طور اقتصادك، جند جيشك، واتحالف أو احارب!\n\n"
        "للبدء اكتب: *انشاء دولة*\n"
        "للمساعدة اكتب: *مساعدة*",
        parse_mode="Markdown"
    )

# ==================== تشغيل البوت ====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_message))  # لاستقبال الأعلام
    print("✅ البوت شغال!")
    app.run_polling()

if __name__ == "__main__":
    main()
