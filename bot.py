import asyncio
import json
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    WebAppInfo
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web

import database as db
from config import BOT_TOKEN, WEBAPP_URL, ADMIN_PASSWORD

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


def main_menu_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Web App", web_app=WebAppInfo(url=f"{WEBAPP_URL}/index.html"))],
        [InlineKeyboardButton(text="👤 Mening anketam", callback_data="show_profile")],
        [InlineKeyboardButton(text="📨 Do'stlarni taklif qilish", callback_data="invite_friends")],
    ])
    return keyboard


@dp.message(CommandStart())
async def start_handler(message: types.Message):
    args = message.text.split()
    telegram_id = message.from_user.id

    # Referral tekshirish
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            inviter_id = int(args[1].replace("ref_", ""))
            if inviter_id != telegram_id:
                registered = await db.register_invite(inviter_id, telegram_id)
                if registered:
                    count = await db.get_invite_count(inviter_id)
                    await bot.send_message(
                        inviter_id,
                        f"🎉 Yangi do'st siz orqali qo'shildi! Jami taklif qilganlar: {count}/2\n"
                        + ("✅ Endi siz bepul yozishingiz mumkin!" if count >= 2 else f"⏳ Yana {2 - count} ta do'stni taklif qiling!")
                    )
        except Exception as e:
            logger.error(f"Referral error: {e}")

    user = await db.get_user(telegram_id)

    await message.answer(
        f"👋 Assalomu alaykum, {message.from_user.first_name}!\n\n"
        "💙 *Do'stlik & Tanishuv Botiga xush kelibsiz!*\n\n"
        "Bu yerda siz yangi do'stlar topishingiz, muloqot qilishingiz mumkin.\n\n"
        "🌐 Web App orqali boshlang!",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )


@dp.message(F.text == "👤 Mening anketam")
async def my_profile(message: types.Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Siz hali anketa to'ldirgmansiz. Iltimos, avval anketangizni to'ldiring.")
        return

    gender_icon = "👨" if user["gender"] == "erkak" else "👩"
    goals_text = ", ".join(user["goals"]) if user["goals"] else "ko'rsatilmagan"
    interests_text = ", ".join(user["interests"]) if user["interests"] else "ko'rsatilmagan"

    text = (
        f"{gender_icon} *{user['full_name']}*\n"
        f"🎂 Yosh: {user['age']}\n"
        f"📍 Shahar: {user['city']}\n"
        f"⭐ Burj: {user['zodiac'] or 'ko\'rsatilmagan'}\n"
        f"❤️ Maqsad: {goals_text}\n"
        f"🎯 Qiziqishlar: {interests_text}\n"
        f"👥 Taklif qilingan do'stlar: {user['invited_friends']}/2"
    )

    if user.get("photo_file_id"):
        await message.answer_photo(user["photo_file_id"], caption=text, parse_mode="Markdown")
    else:
        await message.answer(text, parse_mode="Markdown")


@dp.message(F.text == "📨 Do'stlarni taklif qilish")
async def invite_friends(message: types.Message):
    telegram_id = message.from_user.id
    count = await db.get_invite_count(telegram_id)
    invite_link = f"https://t.me/{(await bot.get_me()).username}?start=ref_{telegram_id}"

    text = (
        f"📨 *Do'stlarni taklif qiling!*\n\n"
        f"Do'stlaringizni botga taklif qiling va bepul yozish imkoniyatiga ega bo'ling.\n\n"
        f"👥 Taklif qilganlar: *{count}/2*\n"
        f"{'✅ Siz allaqachon bepul yozish imkoniyatiga egasiz!' if count >= 2 else f'⏳ Yana {2 - count} ta do\'stingizni taklif qiling!'}\n\n"
        f"🔗 Sizning havola:\n`{invite_link}`"
    )

    await message.answer(text, parse_mode="Markdown")


@dp.callback_query(F.data == "show_profile")
async def show_profile_callback(callback: types.CallbackQuery):
    await callback.answer()
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.message.answer("❌ Siz hali anketa to'ldirgmansiz. Iltimos, avval anketangizni to'ldiring.")
        return

    gender_icon = "👨" if user["gender"] == "erkak" else "👩"
    goals_text = ", ".join(user["goals"]) if user["goals"] else "ko'rsatilmagan"
    interests_text = ", ".join(user["interests"]) if user["interests"] else "ko'rsatilmagan"

    text = (
        f"{gender_icon} *{user['full_name']}*\n"
        f"🎂 Yosh: {user['age']}\n"
        f"📍 Shahar: {user['city']}\n"
        f"⭐ Burj: {user['zodiac'] or 'ko\'rsatilmagan'}\n"
        f"❤️ Maqsad: {goals_text}\n"
        f"🎯 Qiziqishlar: {interests_text}\n"
        f"👥 Taklif qilingan do'stlar: {user['invited_friends']}/2"
    )

    if user.get("photo_file_id"):
        await callback.message.answer_photo(user["photo_file_id"], caption=text, parse_mode="Markdown")
    else:
        await callback.message.answer(text, parse_mode="Markdown")


@dp.callback_query(F.data == "invite_friends")
async def invite_friends_callback(callback: types.CallbackQuery):
    await callback.answer()
    telegram_id = callback.from_user.id
    count = await db.get_invite_count(telegram_id)
    invite_link = f"https://t.me/{(await bot.get_me()).username}?start=ref_{telegram_id}"

    text = (
        f"📨 *Do'stlarni taklif qiling!*\n\n"
        f"Do'stlaringizni botga taklif qiling va bepul yozish imkoniyatiga ega bo'ling.\n\n"
        f"👥 Taklif qilganlar: *{count}/2*\n"
        f"{'✅ Siz allaqachon bepul yozish imkoniyatiga egasiz!' if count >= 2 else f'⏳ Yana {2 - count} ta do\'stingizni taklif qiling!'}\n\n"
        f"🔗 Sizning havola:\n`{invite_link}`"
    )

    await callback.message.answer(text, parse_mode="Markdown")


@dp.message(F.web_app_data)
async def web_app_data_handler(message: types.Message):
    """WebApp dan kelgan ma'lumotlarni qabul qilish"""
    try:
        data = json.loads(message.web_app_data.data)
        action = data.get("action")

        if action == "save_profile":
            profile_data = data.get("profile", {})
            profile_data["username"] = message.from_user.username
            profile_data["telegram_id"] = message.from_user.id

            success = await db.save_user(message.from_user.id, profile_data)
            if success:
                await message.answer(
                    "✅ *Anketangiz muvaffaqiyatli saqlandi!*\n\nEndi qidirish orqali yangi do'stlar toping. 🔍",
                    parse_mode="Markdown",
                    reply_markup=main_menu_keyboard()
                )
            else:
                await message.answer("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.")

        elif action == "like_user":
            to_user = int(data.get("to_user"))
            is_match = await db.add_like(message.from_user.id, to_user)
            to_user_data = await db.get_user(to_user)
            my_data = await db.get_user(message.from_user.id)
            if is_match:
                if to_user_data and my_data:
                    await message.answer(
                        f"🎉 *Match! {to_user_data['full_name']} ham sizni yoqtirdi!*\n\nEndi muloqot boshlashingiz mumkin.",
                        parse_mode="Markdown"
                    )
                    try:
                        await bot.send_message(
                            to_user,
                            f"🎉 *Match! {my_data['full_name']} ham sizni yoqtirdi!*\n\nEndi muloqot boshlashingiz mumkin.",
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.error(f"Match notify error: {e}")
                else:
                    await message.answer("🎉 Match bo'ldi! Endi muloqot qiling.")
            else:
                await message.answer("💙 Like yuborildi! Agar u ham sizni yoqtirsa, xabar beramiz.")
                if to_user_data and my_data:
                    try:
                        await bot.send_message(
                            to_user,
                            f"💌 *{my_data['full_name']}* sizni like qildi!\n\nWeb App'dagi Chat bo'limini tekshiring.",
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.error(f"Like notification error: {e}")

        elif action == "block_user":
            blocked_id = int(data.get("blocked_id"))
            await db.block_user(message.from_user.id, blocked_id)
            await message.answer("🚫 Foydalanuvchi bloklandi.")

        elif action == "check_write":
            to_user = int(data.get("to_user"))
            can = await db.can_write(message.from_user.id, to_user)
            if can:
                await message.answer(f"✅ Siz bu foydalanuvchiga yoza olasiz.")
            else:
                invite_link = f"https://t.me/{(await bot.get_me()).username}?start=ref_{message.from_user.id}"
                await message.answer(
                    f"❌ Yozish uchun match bo'lish yoki 2 ta do'st taklif qilish kerak.\n\n"
                    f"🔗 Taklif havolasi:\n`{invite_link}`",
                    parse_mode="Markdown"
                )

        elif action == "search":
            filters = data.get("filters", {})
            users = await db.search_users(message.from_user.id, filters)
            if not users:
                await message.answer("😔 Qidiruv bo'yicha hech kim topilmadi. Filtrlarni o'zgartiring.")
                return

            for u in users[:5]:
                gender_icon = "👨" if u["gender"] == "erkak" else "👩"
                goals_text = ", ".join(u["goals"]) if u["goals"] else "—"
                interests_text = ", ".join(u["interests"]) if u["interests"] else "—"

                text = (
                    f"{gender_icon} *{u['full_name']}*\n"
                    f"🎂 Yosh: {u['age']}\n"
                    f"📍 Shahar: {u['city']}\n"
                    f"❤️ Maqsad: {goals_text}\n"
                    f"🎯 Qiziqishlar: {interests_text}"
                )

                builder = InlineKeyboardBuilder()
                builder.add(InlineKeyboardButton(text="❤️ Like", callback_data=f"like_{u['telegram_id']}"))
                builder.add(InlineKeyboardButton(text="🚫 Blok", callback_data=f"block_{u['telegram_id']}"))
                builder.add(InlineKeyboardButton(text="✉️ Yozish", callback_data=f"write_{u['telegram_id']}"))

                if u.get("photo_file_id"):
                    await message.answer_photo(
                        u["photo_file_id"],
                        caption=text,
                        parse_mode="Markdown",
                        reply_markup=builder.as_markup()
                    )
                else:
                    await message.answer(text, parse_mode="Markdown", reply_markup=builder.as_markup())

    except Exception as e:
        logger.error(f"WebApp data error: {e}")
        await message.answer("❌ Xatolik yuz berdi.")


@dp.callback_query(F.data.startswith("like_"))
async def like_callback(callback: types.CallbackQuery):
    to_user = int(callback.data.replace("like_", ""))
    is_match = await db.add_like(callback.from_user.id, to_user)
    if is_match:
        to_user_data = await db.get_user(to_user)
        my_data = await db.get_user(callback.from_user.id)
        await callback.message.answer(f"🎉 Match! {to_user_data['full_name']} ham sizni yoqtirdi!")
        await bot.send_message(to_user, f"🎉 Match! {my_data['full_name']} ham sizni yoqtirdi!")
    else:
        await callback.answer("💙 Like yuborildi!", show_alert=False)


@dp.callback_query(F.data.startswith("block_"))
async def block_callback(callback: types.CallbackQuery):
    blocked_id = int(callback.data.replace("block_", ""))
    await db.block_user(callback.from_user.id, blocked_id)
    await callback.answer("🚫 Bloklandi", show_alert=True)


@dp.callback_query(F.data.startswith("write_"))
async def write_callback(callback: types.CallbackQuery):
    to_user = int(callback.data.replace("write_", ""))
    can = await db.can_write(callback.from_user.id, to_user)
    if can:
        to_user_data = await db.get_user(to_user)
        username = to_user_data.get("username")
        if username:
            await callback.answer(f"@{username} ga yozishingiz mumkin!", show_alert=True)
        else:
            await callback.answer("Bu foydalanuvchining username yo'q.", show_alert=True)
    else:
        me = await bot.get_me()
        invite_link = f"https://t.me/{me.username}?start=ref_{callback.from_user.id}"
        await callback.message.answer(
            f"❌ Yozish uchun match bo'lish yoki 2 do'st taklif qilish kerak.\n\n🔗 Havolangiz:\n`{invite_link}`",
            parse_mode="Markdown"
        )


# ========== HTTP API ==========

def serialize_value(value):
    if isinstance(value, (list, tuple)):
        return [serialize_value(v) for v in value]
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return value


def serialize_user(user):
    clean_user = {}
    for key, value in user.items():
        clean_user[key] = serialize_value(value)
    return clean_user


@web.middleware
async def cors_middleware(request, handler):
    if request.method == 'OPTIONS':
        return web.Response(
            text='',
            status=200,
            headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization',
                'Access-Control-Max-Age': '86400',
            }
        )
    
    response = await handler(request)
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response


async def search_api(request):
    try:
        data = await request.json()
        telegram_id = data.get('telegram_id')
        filters = data.get('filters', {})
        if telegram_id is None:
            telegram_id = 0
        users = await db.search_users(int(telegram_id), filters)
        clean_users = [serialize_user(u) for u in users]
        return web.json_response({'success': True, 'users': clean_users})
    except Exception as e:
        logger.error(f"SEARCH API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def profile_api(request):
    try:
        data = await request.json()
        telegram_id = data.get('telegram_id')
        if telegram_id is None:
            return web.json_response({'success': False, 'error': 'telegram_id required'}, status=400)
        user = await db.get_user(int(telegram_id))
        if user:
            return web.json_response({'success': True, 'user': serialize_user(user)})
        return web.json_response({'success': True, 'user': None})
    except Exception as e:
        logger.error(f"PROFILE API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def save_profile_api(request):
    try:
        data = await request.json()
        telegram_id = data.get('telegram_id')
        profile = data.get('profile', {})
        if telegram_id is None:
            return web.json_response({'success': False, 'error': 'telegram_id required'}, status=400)
        if not profile:
            return web.json_response({'success': False, 'error': 'profile required'}, status=400)
        profile['telegram_id'] = int(telegram_id)
        profile['username'] = profile.get('username')
        success = await db.save_user(int(telegram_id), profile)
        return web.json_response({'success': success})
    except Exception as e:
        logger.error(f"SAVE PROFILE API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def admin_users_api(request):
    try:
        data = await request.json()
        if ADMIN_PASSWORD and data.get('admin_password') != ADMIN_PASSWORD:
            return web.json_response({'success': False, 'error': 'Unauthorized'}, status=403)
        users = await db.get_all_users()
        clean_users = [serialize_user(u) for u in users]
        return web.json_response({'success': True, 'users': clean_users})
    except Exception as e:
        logger.error(f"ADMIN USERS API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def admin_analytics_api(request):
    try:
        data = await request.json()
        if ADMIN_PASSWORD and data.get('admin_password') != ADMIN_PASSWORD:
            return web.json_response({'success': False, 'error': 'Unauthorized'}, status=403)
        stats = await db.get_user_stats()
        top_cities = await db.get_top_cities(10)
        return web.json_response({'success': True, 'analytics': {
            'total': stats.get('total', 0),
            'male': stats.get('male', 0),
            'female': stats.get('female', 0),
            'avg_age': float(stats.get('avg_age')) if stats.get('avg_age') is not None else None,
            'top_cities': top_cities
        }})
    except Exception as e:
        logger.error(f"ADMIN ANALYTICS API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


# ========== CHAT API ENDPOINTS ==========

async def likes_received_api(request):
    try:
        data = await request.json()
        telegram_id = data.get('telegram_id')
        if not telegram_id:
            return web.json_response({'success': False, 'error': 'telegram_id required'}, status=400)
        likes = await db.get_pending_likes(int(telegram_id))
        return web.json_response({'success': True, 'likes': [serialize_user(u) for u in likes]})
    except Exception as e:
        logger.error(f"LIKES RECEIVED API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def accept_like_api(request):
    try:
        data = await request.json()
        telegram_id = data.get('telegram_id')
        from_user = data.get('from_user')
        if not telegram_id or not from_user:
            return web.json_response({'success': False, 'error': 'Missing params'}, status=400)
        
        match_id = await db.accept_like(int(telegram_id), int(from_user))
        if match_id:
            to_data = await db.get_user(int(telegram_id))
            from_data = await db.get_user(int(from_user))
            if to_data and from_data:
                try:
                    await bot.send_message(
                        int(from_user),
                        f"🎉 *{to_data['full_name']}* sizning like-ingizni qabul qildi!\n\n💬 Endi Web App'dagi Chat bo'limidan suhbat boshlashingiz mumkin.",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Notify liker error: {e}")
                try:
                    await bot.send_message(
                        int(telegram_id),
                        f"✅ Siz *{from_data['full_name']}* bilan muloqotni boshladingiz!",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Notify accepter error: {e}")
            return web.json_response({'success': True, 'match_id': match_id})
        return web.json_response({'success': False, 'error': 'Like not found'}, status=404)
    except Exception as e:
        logger.error(f"ACCEPT LIKE API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def reject_like_api(request):
    try:
        data = await request.json()
        telegram_id = data.get('telegram_id')
        from_user = data.get('from_user')
        if not telegram_id or not from_user:
            return web.json_response({'success': False, 'error': 'Missing params'}, status=400)

        rejected = await db.reject_like(int(telegram_id), int(from_user))
        if rejected:
            to_data = await db.get_user(int(telegram_id))
            from_data = await db.get_user(int(from_user))
            if to_data and from_data:
                try:
                    await bot.send_message(
                        int(from_user),
                        f"❌ *{to_data['full_name']}* sizni rad qildi.\n\nKeyinroq yana sinab ko'ring.",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Notify reject error: {e}")
            return web.json_response({'success': True})
        return web.json_response({'success': False, 'error': 'Like topilmadi'}, status=404)
    except Exception as e:
        logger.error(f"REJECT LIKE API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def matches_api(request):
    try:
        data = await request.json()
        telegram_id = data.get('telegram_id')
        if not telegram_id:
            return web.json_response({'success': False, 'error': 'telegram_id required'}, status=400)
        matches = await db.get_matches(int(telegram_id))
        return web.json_response({'success': True, 'matches': [serialize_user(m) for m in matches]})
    except Exception as e:
        logger.error(f"MATCHES API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def chat_messages_api(request):
    try:
        data = await request.json()
        match_id = data.get('match_id')
        if not match_id:
            return web.json_response({'success': False, 'error': 'match_id required'}, status=400)
        messages = await db.get_chat_messages(int(match_id))
        # Mark as read (optional, could be separate call)
        return web.json_response({'success': True, 'messages': [serialize_user(m) for m in messages]})
    except Exception as e:
        logger.error(f"CHAT MESSAGES API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def send_chat_api(request):
    try:
        data = await request.json()
        match_id = data.get('match_id')
        sender_id = data.get('sender_id')
        message = data.get('message', '').strip()
        if not match_id or not sender_id or not message:
            return web.json_response({'success': False, 'error': 'Missing params'}, status=400)
        success = await db.send_chat_message(int(match_id), int(sender_id), message)
        return web.json_response({'success': success})
    except Exception as e:
        logger.error(f"SEND CHAT API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def can_write_api(request):
    try:
        data = await request.json()
        from_user = data.get('from_user')
        to_user = data.get('to_user')
        if from_user is None or to_user is None:
            return web.json_response({'success': False, 'error': 'Missing params'}, status=400)
        can = await db.can_write(int(from_user), int(to_user))
        return web.json_response({'success': True, 'can_write': can})
    except Exception as e:
        logger.error(f"CAN WRITE API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def initiate_chat_api(request):
    try:
        data = await request.json()
        from_user = data.get('from_user')
        to_user = data.get('to_user')
        if not from_user or not to_user:
            return web.json_response({'success': False, 'error': 'Missing params'}, status=400)
        
        can = await db.can_write(int(from_user), int(to_user))
        if not can:
            return web.json_response({'success': False, 'error': 'Unauthorized'}, status=403)
        
        match_id = await db.create_match(int(from_user), int(to_user))
        if match_id:
            return web.json_response({'success': True, 'match_id': match_id})
        return web.json_response({'success': False, 'error': 'Failed to create match'}, status=500)
    except Exception as e:
        logger.error(f"INITIATE CHAT API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def main():
    await db.init_db()
    logger.info("Bot ishga tushdi...")
    
    app = web.Application()
    app.middlewares.append(cors_middleware)
    
    app.router.add_post('/api/search', search_api)
    app.router.add_post('/api/profile', profile_api)
    app.router.add_post('/api/save_profile', save_profile_api)
    app.router.add_post('/api/admin/users', admin_users_api)
    app.router.add_post('/api/admin/analytics', admin_analytics_api)
    
    # Chat routes
    app.router.add_post('/api/likes/received', likes_received_api)
    app.router.add_post('/api/likes/accept', accept_like_api)
    app.router.add_post('/api/likes/reject', reject_like_api)
    app.router.add_post('/api/matches', matches_api)
    app.router.add_post('/api/chat/messages', chat_messages_api)
    app.router.add_post('/api/chat/send', send_chat_api)
    app.router.add_post('/api/can_write', can_write_api)
    app.router.add_post('/api/initiate_chat', initiate_chat_api)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.environ.get('PORT', 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"✅ HTTP API server started on port {port}")
    
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
