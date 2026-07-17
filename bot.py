import asyncio
import base64
import hashlib
import hmac
import io
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, parse_qsl
from PIL import Image, ImageDraw, ImageFont
from aiogram import Bot, Dispatcher, types, F
from aiogram.exceptions import TelegramForbiddenError
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    BufferedInputFile,
    InlineKeyboardMarkup, InlineKeyboardButton,
    WebAppInfo
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web
import database as db
import aiohttp
from config import BOT_TOKEN, WEBAPP_URL, ADMIN_PASSWORD, GROUP_CHAT_ID, GROUP_INVITE_LINK, OPENAI_API_KEY
try:
    from config import ADMIN_CHAT_ID
except ImportError:
    ADMIN_CHAT_ID = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
search_sessions = {}
pending_message_targets = {}

# ========== KO'P TILLI QO'LLAB-QUVVATLASH ==========
SUPPORTED_LANGUAGES = {
    'uz': {'name': "O'zbekcha", 'flag': '🇺🇿'},
    'ru': {'name': 'Русский', 'flag': '🇷🇺'},
    'kk': {'name': 'Қазақша', 'flag': '🇰🇿'},
    'ky': {'name': 'Кыргызча', 'flag': '🇰🇬'},
    'kaa': {'name': 'Qaraqalpaqsha', 'flag': '🇺🇿'},
    'tg': {'name': 'Тоҷикӣ', 'flag': '🇹🇯'},
    'en': {'name': 'English', 'flag': '🇬🇧'},
}

# Har bir interfeys tili uchun til nomlarining tarjimasi
# (masalan, ruscha interfeysda "O'zbekcha" -> "Узбекский" bo'lib ko'rinadi)
LANGUAGE_NAMES_TRANSLATED = {
    'uz': {'uz': "O'zbekcha", 'ru': 'Ruscha', 'kk': 'Qozoqcha', 'ky': "Qirg'izcha",
           'kaa': 'Qoraqalpoqcha', 'tg': 'Tojikcha', 'en': 'Inglizcha'},
    'ru': {'uz': 'Узбекский', 'ru': 'Русский', 'kk': 'Казахский', 'ky': 'Киргизский',
           'kaa': 'Каракалпакский', 'tg': 'Таджикский', 'en': 'Английский'},
    'kk': {'uz': 'Өзбекше', 'ru': 'Орысша', 'kk': 'Қазақша', 'ky': 'Қырғызша',
           'kaa': 'Қарақалпақша', 'tg': 'Тәжікше', 'en': 'Ағылшынша'},
    'ky': {'uz': 'Өзбекче', 'ru': 'Орусча', 'kk': 'Казакча', 'ky': 'Кыргызча',
           'kaa': 'Каракалпакча', 'tg': 'Тажикче', 'en': 'Англисче'},
    'kaa': {'uz': 'Ózbekshe', 'ru': 'Rússha', 'kk': 'Qazaqsha', 'ky': 'Qırgızsha',
            'kaa': 'Qaraqalpaqsha', 'tg': 'Tájikshe', 'en': 'Aǵılshınsha'},
    'tg': {'uz': 'Узбекӣ', 'ru': 'Русӣ', 'kk': 'Қазоқӣ', 'ky': 'Қирғизӣ',
           'kaa': 'Қароқалпоқӣ', 'tg': 'Тоҷикӣ', 'en': 'Англисӣ'},
    'en': {'uz': 'Uzbek', 'ru': 'Russian', 'kk': 'Kazakh', 'ky': 'Kyrgyz',
           'kaa': 'Karakalpak', 'tg': 'Tajik', 'en': 'English'},
}

# Barcha tarjimalar
T = {
    'uz': {
        'welcome': "👋 Assalomu alaykum, {name}!\n\n💙 *Do'stlik & Tanishuv Botiga xush kelibsiz!*\n\nBu yerda siz yangi do'stlar topishingiz, muloqot qilishingiz mumkin.",
        'select_language': "🌍 Iltimos, tilni tanlang:",
        'language_changed': "✅ Til o'zgartirildi: {language_name}",
        'limits_info': "\n\n📊 *Kunlik limitlar:*\n• Like: 25 ta\n• Xabar yuborish: 10 ta\n• Super Like: 10 ta\n\n🎁 *Limitni oshirish:*\nGuruhga 5 ta odam qo'shsangiz → 1 hafta limitsiz\nGuruhga 10 ta odam qo'shsangiz → 1 oy limitsiz",
        'btn_webapp': "🌐 Web App",
        'btn_my_profile': "👤 Mening anketam",
        'btn_search': "🔎 Qidirish",
        'btn_group': "👥 Guruhga qo'shilish",
        'btn_change_lang': "🌍 Tilni o'zgartirish",
        'no_profile': "❌ Siz hali anketa to'ldirmagansiz. Iltimos, avval anketangizni to'ldiring.",
        'fill_profile': "Anketa to'ldirish",
        'please_fill_profile': "Iltimos, avval anketa to'ldiring.",
        'search_who': "Qidirish uchun kimni izlayapsiz?\n\nErkak, ayol yoki barchasini tanlang.\nYoki burjingizga mos odamlarni qidiring! ⭐",
        'btn_male': "👨 Erkak",
        'btn_female': "👩 Ayol",
        'btn_all': "🔄 Barchasi",
        'btn_zodiac_compat': "⭐ Burjga mos qidirish",
        'btn_back': "⬅ Orqaga",
        'btn_skip': "❌ O'tkazib yuborish",
        'btn_write': "✉️ Yozish",
        'btn_like': "❤️ Like",
        'btn_super_like': "⭐ Super Like",
        'btn_block': "🚫 Blok",
        'btn_report': "⚠️ Shikoyat",
        'report_choose_category': "⚠️ Shikoyat sababini tanlang:",
        'report_cat_porn': "🔞 Pornografiya",
        'report_cat_drugs': "💊 Narkotik",
        'report_cat_violence': "⚔️ Zo'ravonlik",
        'report_cat_fraud': "💰 Firibgarlik",
        'report_cat_minor': "🚸 Kichik yoshdagi bola",
        'report_cat_other': "❗ Boshqa",
        'report_sent': "✅ Shikoyatingiz qabul qilindi. Tez orada tekshiriladi.",
        'report_error': "❌ Shikoyat yuborishda xatolik yuz berdi.",
        'ban_message': "🚫 Sizning akkauntingiz shikoyatlar asosida vaqtincha cheklangan.\n\n📌 Sabab: {reason}\n⏳ Cheklov tugash vaqti: {until}\n\nBu bot yoki Web App'dan foydalana olmaysiz.",
        'no_candidates': "😔 Hech qanday nomzod topilmadi.",
        'all_viewed': "✅ Barcha nomzodlar ko'rib chiqildi. Qayta qidirish uchun menyudan yana urinib ko'ring.",
        'search_counter': "\n\n🔎 {current}/{total} ta nomzoddan hozirgi",
        'no_zodiac': "❌ Burjingiz anketada ko'rsatilmagan.\nIltimos, avval anketangizni to'ldiring va burj tanlang.",
        'zodiac_not_recognized': "❌ Burjingiz tanib olinmadi. Anketani yangilang.",
        'your_zodiac': "⭐ Sizning burjingiz: *{sign}*\n\nSizga mos burjlar:\n{compat}\n\nQaysi jinsni qidirmoqchisiz?",
        'no_zodiac_match': "😔 Burjingizga mos hech kim topilmadi. Keyinroq qayta urinib ko'ring.",
        'no_results': "😔 Hech kim topilmadi. Keyinroq yana urinib ko'ring.",
        'searching': "Qidirilmoqda...",
        'like_sent': "💙 Like yuborildi!",
        'match': "🎉 Match! {name} ham sizni yoqtirdi!\n\nEndi muloqot boshlashingiz mumkin.",
        'like_notify': "💌 {name} sizni like qildi!\n\nWeb App'dagi Chat bo'limini tekshiring.",
        'super_like_sent': "⭐ Super Like yuborildi!",
        'super_like_match': "⭐ Super Like Match! {name} ham sizni yoqtirdi!\n\nEndi muloqot boshlashingiz mumkin.",
        'super_like_notify': "⭐ {name} sizga Super Like bosdi!\n\nWeb App'dagi Chat bo'limini tekshiring.",
        'blocked': "🚫 Foydalanuvchi bloklandi.",
        'need_like_first': "❌ Avval like yuborish kerak!",
        'send_message_text': "💬 Xabar matnini yozing. Bitta xabar yuboriladi.",
        'message_sent': "✅ Xabar yuborildi!",
        'empty_message': "❌ Bo'sh xabar jo'natib bo'lmaydi.",
        'new_message': "💬 {name} dan yangi xabar:\n{text}",
        'profile_saved': "✅ *Anketangiz muvaffaqiyatli saqlandi!*\n\nEndi qidirish orqali yangi do'stlar toping. 🔍",
        'save_error': "❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.",
        'limit_exceeded_likes': "❌ Kunlik like limitingiz tugadi!\n\n5 ta do'st qo'shganingizdan keyin 1 hafta, 10 ta bo'lsa 1 oy limitsiz bo'lasiz.",
        'limit_exceeded_messages': "❌ Kunlik xabar yuborish limitingiz tugadi!\n\n5 ta do'st qo'shganingizdan keyin 1 hafta, 10 ta bo'lsa 1 oy limitsiz bo'lasiz.",
        'limit_exceeded_super': "❌ Kunlik Super Like limitingiz tugadi!\n\n5 ta do'st qo'shganingizdan keyin 1 hafta, 10 ta bo'lsa 1 oy limitsiz bo'lasiz.",
        'limit_info_long': "❌ Kunlik limitingiz tugadi!\n\n📊 Kunlik limitlar:\n• Like: 25 ta\n• Xabar yuborish: 10 ta\n• Super Like: 10 ta\n\n🎁 Limitni oshirish:\nGuruhga 5 ta odam qo'shsangiz → 1 hafta limitsiz\nGuruhga 10 ta odam qo'shsangiz → 1 oy limitsiz\n\nYoki ertaga yangi limit bilan davom etasiz.",
        'unlimited_access': "\n✅ *Limitsiz foydalanish*",
        'daily_limits': "\n📊 *Kunlik limitlar:*\n• Like: {likes}/25\n• Xabar: {messages}/10\n• Super Like: {super_likes}/10",
        'gender_male': "Erkak",
        'gender_female': "Ayol",
        'age': "Yosh",
        'city': "Shahar",
        'zodiac': "Burj",
        'about': "Men haqimda",
        'spoken_language': "So'zlashuv tili",
        'goals': "Maqsad",
        'interests': "Qiziqishlar",
        'not_specified': "ko'rsatilmagan",
        'searching_zodiac': "Burjga mos qidirilmoqda...",
        'main_menu': "Asosiy menyu:",
        'group_invite_success': "🎉 *Tabriklaymiz!*\n\n*{name}* guruhga qo'shildi!\n\n{msg}",
        'like_accepted': "🎉 *{name}* sizning like-ingizni qabul qildi!\n\n💬 Endi Web App'dagi Chat bo'limidan suhbat boshlashingiz mumkin.",
        'chat_started': "✅ Siz *{name}* bilan muloqotni boshladingiz!",
        'rejected': "❌ *{name}* sizni rad qildi.\n\nKeyinroq yana sinab ko'ring.",
        'anon_reveal_request_notify': "🌙 Suhbatdoshingiz profilni ochishni so'ramoqda. Agar rozilik bersangiz, suhbat asosiy Chat bo'limiga ko'chiriladi.",
        'anon_reveal_declined_notify': "😔 Sizning profil ochish taklifingiz hozircha qabul qilinmadi. Anonim chat davom etmoqda.",
        'anon_disconnected_notify': "🚪 Suhbatdoshingiz anonim chatni tark etdi. Suhbat yakunlandi.",
        'anon_revealed_notify': "🎉 Ajoyib! Ikkalangiz ham profilni ochishga rozi bo'ldingiz. Endi asosiy Chat bo'limida suhbatni davom ettirishingiz mumkin.",
        'anon_match_found_notify': "🌙 *Anonim suhbatdosh topildi!*\n\nSizga mos suhbatdosh topildi va chat allaqachon boshlandi. Ismi va rasmi hozircha yashirin.\n\nWeb App'ni oching va \"Muloqot\" bo'limidan suhbatni davom ettiring 👇",
        'anon_evening_reminder_notify': "🌙 *Anonim suhbat vaqti keldi!*\n\nIstalgan vaqt anonim suhbatdosh topishingiz mumkin. Hoziroq urinib ko'rasizmi?\n\nWeb App'ni oching, \"Muloqot\" bo'limida \"🔍 Suhbatdosh topish\" tugmasini bosing 👇",
        'like_not_found': "Like topilmadi",
        'super_like_label': "⭐ *Super Like Match!* ",
        'match_label': "🎉 *Match!* ",
        'super_like_note': "\n\n{sticker} Sizga tanlangan emoji bilan Super Like yuborildi.",
        'super_like_note_default': "\n\nSizga Super Like yuborildi.",
        'pressed_super_like': "Super Like bosdi!",
        'pressed_like': "ham sizni yoqtirdi!",
        'write_username': "@{username} ga yozishingiz mumkin!",
        'no_username': "Bu foydalanuvchining username yo'q.",
        'like_notify_btn': "💌 *{name}* sizni yoqtirdi!\n\nQabul qilsangiz ikkalangiz chat orqali muloqot qila olasiz.",
        'super_like_notify_btn': "⭐ *{name}* sizga {sticker}Super Like yubordi!\n\nQabul qilsangiz ikkalangiz chat orqali muloqot qila olasiz.",
        'btn_accept_like': "✅ Qabul qilish",
        'btn_reject_like': "❌ Rad etish",
        'super_like_match_notify': "🎉⭐ *{name}* {sticker}Super Like yubordi va match bo'ldi!\n\nEndi muloqot boshlashingiz mumkin. 💬",
        'super_like_match_self': "🎉⭐ {sticker}Super Like qabul qilindi! *{name}* sizni ham yoqtirdi!\n\nEndi muloqot boshlashingiz mumkin. 💬",
        'super_like_sticker': "⭐ Super Like uchun stiker tanlang:",
    },
    'ru': {
        'welcome': "👋 Здравствуйте, {name}!\n\n💙 *Добро пожаловать в бот знакомств!*\n\nЗдесь вы можете найти новых друзей и общаться.",
        'select_language': "🌍 Пожалуйста, выберите язык:",
        'language_changed': "✅ Язык изменён: {language_name}",
        'limits_info': "\n\n📊 *Ежедневные лимиты:*\n• Лайк: 25\n• Сообщения: 10\n• Супер Лайк: 10\n\n🎁 *Увеличить лимит:*\nПригласите 5 человек → 1 неделя без лимитов\nПригласите 10 человек → 1 месяц без лимитов",
        'btn_webapp': "🌐 Веб-приложение",
        'btn_my_profile': "👤 Мой профиль",
        'btn_search': "🔎 Поиск",
        'btn_group': "👥 Присоединиться к группе",
        'btn_change_lang': "🌍 Изменить язык",
        'no_profile': "❌ Вы ещё не заполнили анкету. Пожалуйста, сначала заполните профиль.",
        'fill_profile': "Заполнить анкету",
        'please_fill_profile': "Пожалуйста, сначала заполните анкету.",
        'search_who': "Кого вы ищете?\n\nВыберите: мужчина, женщина или все.\nИли найдите людей по знаку зодиака! ⭐",
        'btn_male': "👨 Мужчина",
        'btn_female': "👩 Женщина",
        'btn_all': "🔄 Все",
        'btn_zodiac_compat': "⭐ Поиск по знаку зодиака",
        'btn_back': "⬅ Назад",
        'btn_skip': "❌ Пропустить",
        'btn_write': "✉️ Написать",
        'btn_like': "❤️ Лайк",
        'btn_super_like': "⭐ Супер Лайк",
        'btn_block': "🚫 Блок",
        'no_candidates': "😔 Кандидаты не найдены.",
        'all_viewed': "✅ Все кандидаты просмотрены. Попробуйте поискать ещё раз.",
        'search_counter': "\n\n🔎 Кандидат {current} из {total}",
        'no_zodiac': "❌ Ваш знак зодиака не указан.\nПожалуйста, заполните анкету и выберите знак зодиака.",
        'zodiac_not_recognized': "❌ Ваш знак зодиака не распознан. Обновите анкету.",
        'your_zodiac': "⭐ Ваш знак зодиака: *{sign}*\n\nСовместимые знаки:\n{compat}\n\nКого вы хотите найти?",
        'no_zodiac_match': "😔 По знаку зодиака никого не найдено. Попробуйте позже.",
        'no_results': "😔 Никого не найдено. Попробуйте позже.",
        'searching': "Поиск...",
        'like_sent': "💙 Лайк отправлен!",
        'match': "🎉 Совпадение! {name} тоже вас лайкнул(а)!\n\nТеперь вы можете общаться.",
        'like_notify': "💌 {name} лайкнул(а) вас!\n\nПроверьте раздел Чат в Веб-приложении.",
        'super_like_sent': "⭐ Супер Лайк отправлен!",
        'super_like_match': "⭐ Супер Лайк Совпадение! {name} тоже вас лайкнул(а)!\n\nТеперь вы можете общаться.",
        'super_like_notify': "⭐ {name} отправил(а) вам Супер Лайк!\n\nПроверьте раздел Чат в Веб-приложении.",
        'blocked': "🚫 Пользователь заблокирован.",
        'need_like_first': "❌ Сначала нужно отправить лайк!",
        'send_message_text': "💬 Напишите текст сообщения. Будет отправлено одно сообщение.",
        'message_sent': "✅ Сообщение отправлено!",
        'empty_message': "❌ Нельзя отправить пустое сообщение.",
        'new_message': "💬 Новое сообщение от {name}:\n{text}",
        'profile_saved': "✅ *Ваша анкета успешно сохранена!*\n\nТеперь найдите новых друзей через поиск. 🔍",
        'save_error': "❌ Произошла ошибка. Попробуйте ещё раз.",
        'limit_exceeded_likes': "❌ Ежедневный лимит лайков исчерпан!\n\nПригласите 5 друзей → 1 неделя без лимитов, 10 друзей → 1 месяц без лимитов.",
        'limit_exceeded_messages': "❌ Ежедневный лимит сообщений исчерпан!\n\nПригласите 5 друзей → 1 неделя без лимитов, 10 друзей → 1 месяц без лимитов.",
        'limit_exceeded_super': "❌ Ежедневный лимит Супер Лайков исчерпан!\n\nПригласите 5 друзей → 1 неделя без лимитов, 10 друзей → 1 месяц без лимитов.",
        'limit_info_long': "❌ Ежедневный лимит исчерпан!\n\n📊 Лимиты:\n• Лайк: 25\n• Сообщения: 10\n• Супер Лайк: 10\n\n🎁 Увеличить:\n5 приглашённых → 1 неделя без лимитов\n10 приглашённых → 1 месяц без лимитов\n\nИли завтра новый лимит.",
        'unlimited_access': "\n✅ *Безлимитный доступ*",
        'daily_limits': "\n📊 *Ежедневные лимиты:*\n• Лайк: {likes}/25\n• Сообщения: {messages}/10\n• Супер Лайк: {super_likes}/10",
        'gender_male': "Мужчина",
        'gender_female': "Женщина",
        'age': "Возраст",
        'city': "Город",
        'zodiac': "Знак зодиака",
        'about': "О себе",
        'spoken_language': "Язык общения",
        'goals': "Цели",
        'interests': "Интересы",
        'not_specified': "не указано",
        'searching_zodiac': "Поиск по знаку зодиака...",
        'main_menu': "Главное меню:",
        'group_invite_success': "🎉 *Поздравляем!*\n\n*{name}* присоединился к группе!\n\n{msg}",
        'like_accepted': "🎉 *{name}* принял(а) ваш лайк!\n\n💬 Теперь начните общение в Чате Веб-приложения.",
        'chat_started': "✅ Вы начали общение с *{name}*!",
        'rejected': "❌ *{name}* отклонил(а) вас.\n\nПопробуйте позже.",
        'like_not_found': "Лайк не найден",
        'super_like_label': "⭐ *Супер Лайк Совпадение!* ",
        'match_label': "🎉 *Совпадение!* ",
        'super_like_note': "\n\n{sticker} Вам отправлен Супер Лайк с выбранным эмодзи.",
        'super_like_note_default': "\n\nВам отправлен Супер Лайк.",
        'pressed_super_like': "отправил(а) Супер Лайк!",
        'pressed_like': "тоже вас лайкнул(а)!",
        'write_username': "Можете написать @{username}!",
        'no_username': "У этого пользователя нет username.",
        'like_notify_btn': "💌 *{name}* лайкнул(а) вас!\n\nЕсли вы примете — сможете общаться в чате.",
        'super_like_notify_btn': "⭐ *{name}* отправил(а) вам {sticker}Супер Лайк!\n\nЕсли вы примете — сможете общаться в чате.",
        'btn_accept_like': "✅ Принять",
        'btn_reject_like': "❌ Отклонить",
        'super_like_match_notify': "🎉⭐ *{name}* отправил(а) {sticker}Супер Лайк и это совпадение!\n\nТеперь вы можете начать общение. 💬",
        'super_like_match_self': "🎉⭐ {sticker}Супер Лайк принят! *{name}* тоже вас лайкнул(а)!\n\nТеперь вы можете начать общение. 💬",
        'anon_reveal_request_notify': "🌙 Ваш собеседник просит открыть профиль. Если вы согласитесь, чат переместится в основной раздел Чат.",
        'anon_reveal_declined_notify': "😔 Ваше предложение открыть профиль пока не принято. Анонимный чат продолжается.",
        'anon_disconnected_notify': "🚪 Ваш собеседник покинул анонимный чат. Чат завершён.",
        'anon_revealed_notify': "🎉 Отлично! Вы оба согласились открыть профили. Теперь вы можете продолжить общение в основном разделе Чат.",
        'anon_match_found_notify': "🌙 *Найден анонимный собеседник!*\n\nВам подобрали собеседника, и чат уже начался. Имя и фото пока скрыты.\n\nОткройте Web App и продолжите общение в разделе «Общение» 👇",
        'anon_evening_reminder_notify': "🌙 *Время для анонимного чата!*\n\nВы можете найти анонимного собеседника в любое время. Хотите попробовать прямо сейчас?\n\nОткройте Web App и нажмите «🔍 Найти собеседника» в разделе «Общение» 👇",
        'btn_report': "⚠️ Жалоба",
        'report_choose_category': "⚠️ Выберите причину жалобы:",
        'report_cat_porn': "🔞 Порнография",
        'report_cat_drugs': "💊 Наркотики",
        'report_cat_violence': "⚔️ Насилие",
        'report_cat_fraud': "💰 Мошенничество",
        'report_cat_minor': "🚸 Несовершеннолетний",
        'report_cat_other': "❗ Другое",
        'report_sent': "✅ Ваша жалоба принята. Скоро будет рассмотрена.",
        'report_error': "❌ Ошибка при отправке жалобы.",
        'ban_message': "🚫 Ваш аккаунт временно ограничен из-за жалоб.\n\n📌 Причина: {reason}\n⏳ Срок окончания ограничения: {until}\n\nВы не можете пользоваться этим ботом или Web App.",
        'super_like_sticker': "⭐ Выберите стикер для Супер Лайка:",
    },
    'kk': {
        'welcome': "👋 Сәлеметсіз бе, {name}!\n\n💙 *Танысу ботына қош келдіңіз!*\n\nМұнда жаңа достар тауып, сөйлесе аласыз.",
        'select_language': "🌍 Тілді таңдаңыз:",
        'language_changed': "✅ Тіл өзгертілді: {language_name}",
        'limits_info': "\n\n📊 *Күнделікті лимиттер:*\n• Лайк: 25\n• Хабар: 10\n• Супер Лайк: 10\n\n🎁 *Лимитті арттыру:*\n5 адам қосыңыз → 1 апта лимитсіз\n10 адам қосыңыз → 1 ай лимитсіз",
        'btn_webapp': "🌐 Веб-қосымша",
        'btn_my_profile': "👤 Менің профилім",
        'btn_search': "🔎 Іздеу",
        'btn_group': "👥 Топқа қосылу",
        'btn_change_lang': "🌍 Тілді өзгерту",
        'no_profile': "❌ Сіз әлі анкета толтырмадыңыз. Алдымен профиліңізді толтырыңыз.",
        'fill_profile': "Анкетаны толтырыңыз",
        'please_fill_profile': "Алдымен анкетаны толтырыңыз.",
        'search_who': "Кім іздеп жатырсыз?\n\nЕр адам, әйел немесе бәрін таңдаңыз.\nНемесе жұлдызнама бойынша іздеңіз! ⭐",
        'btn_male': "👨 Ер адам",
        'btn_female': "👩 Әйел",
        'btn_all': "🔄 Бәрі",
        'btn_zodiac_compat': "⭐ Жұлдызнама бойынша іздеу",
        'btn_back': "⬅ Артқа",
        'btn_skip': "❌ Өткізіп жіберу",
        'btn_write': "✉️ Жазу",
        'btn_like': "❤️ Лайк",
        'btn_super_like': "⭐ Супер Лайк",
        'btn_block': "🚫 Блок",
        'no_candidates': "😔 Ешкім табылмады.",
        'all_viewed': "✅ Барлық кандидаттар қаралды. Қайта іздеп көріңіз.",
        'search_counter': "\n\n🔎 {current}/{total} кандидат",
        'no_zodiac': "❌ Жұлдызнамаңыз көрсетілмеген.\nАлдымен анкетаны толтырыңыз.",
        'zodiac_not_recognized': "❌ Жұлдызнамаңыз танылмады. Анкетаны жаңартыңыз.",
        'your_zodiac': "⭐ Сіздің жұлдызнамаңыз: *{sign}*\n\nҮйлесімді жұлдызнамалар:\n{compat}\n\nКім іздегіңіз келеді?",
        'no_zodiac_match': "😔 Жұлдызнама бойынша ешкім табылмады.",
        'no_results': "😔 Ешкім табылмады. Кейінірек қайталаңыз.",
        'searching': "Ізделуде...",
        'like_sent': "💙 Лайк жіберілді!",
        'match': "🎉 Сәйкестік! {name} де сізді ұнатты!\n\nЕнді сөйлесе аласыз.",
        'like_notify': "💌 {name} сізді лайк етті!\n\nВеб-қосымшадағы Чат бөлімін тексеріңіз.",
        'super_like_sent': "⭐ Супер Лайк жіберілді!",
        'super_like_match': "⭐ Супер Лайк Сәйкестік! {name} де сізді ұнатты!\n\nЕнді сөйлесе аласыз.",
        'super_like_notify': "⭐ {name} сізге Супер Лайк жіберді!\n\nВеб-қосымшадағы Чат бөлімін тексеріңіз.",
        'blocked': "🚫 Пайдаланушы бұғатталды.",
        'need_like_first': "❌ Алдымен лайк жіберу керек!",
        'send_message_text': "💬 Хабар мәтінін жазыңыз.",
        'message_sent': "✅ Хабар жіберілді!",
        'empty_message': "❌ Бос хабар жіберуге болмайды.",
        'new_message': "💬 {name} жаңа хабар:\n{text}",
        'profile_saved': "✅ *Анкетаңыз сақталды!*\n\nЕнді іздеу арқылы жаңа достар табыңыз. 🔍",
        'save_error': "❌ Қате орын алды. Қайталап көріңіз.",
        'limit_exceeded_likes': "❌ Күнделікті лайк лимиті бітті!\n5 дос қосыңыз → 1 апта лимитсіз, 10 дос → 1 ай лимитсіз.",
        'limit_exceeded_messages': "❌ Күнделікті хабар лимиті бітті!\n5 дос қосыңыз → 1 апта лимитсіз, 10 дос → 1 ай лимитсіз.",
        'limit_exceeded_super': "❌ Күнделікті Супер Лайк лимиті бітті!\n5 дос қосыңыз → 1 апта лимитсіз, 10 дос → 1 ай лимитсіз.",
        'limit_info_long': "❌ Күнделікті лимит бітті!\n\n📊 Лимиттер:\n• Лайк: 25\n• Хабар: 10\n• Супер Лайк: 10\n\n🎁 Арттыру:\n5 адам → 1 апта лимитсіз\n10 адам → 1 ай лимитсіз\n\nНемесе ертең жаңа лимит.",
        'unlimited_access': "\n✅ *Лимитсіз қолдану*",
        'daily_limits': "\n📊 *Күнделікті лимиттер:*\n• Лайк: {likes}/25\n• Хабар: {messages}/10\n• Супер Лайк: {super_likes}/10",
        'gender_male': "Ер адам",
        'gender_female': "Әйел",
        'age': "Жас",
        'city': "Қала",
        'zodiac': "Жұлдызнама",
        'about': "Мен туралы",
        'spoken_language': "Сөйлесу тілі",
        'goals': "Мақсаттар",
        'interests': "Қызығушылықтар",
        'not_specified': "көрсетілмеген",
        'searching_zodiac': "Жұлдызнама бойынша ізделуде...",
        'main_menu': "Негізгі мәзір:",
        'group_invite_success': "🎉 *Құттықтаймыз!*\n\n*{name}* топқа қосылды!\n\n{msg}",
        'like_accepted': "🎉 *{name}* лайкіңізді қабылдады!\n\n💬 Енді Веб-қосымшадағы Чат арқылы сөйлесіңіз.",
        'chat_started': "✅ Сіз *{name}* бен сөйлесе бастадыңыз!",
        'rejected': "❌ *{name}* сізді қабылдамады.\n\nКейінірек қайталаңыз.",
        'like_not_found': "Лайк табылмады",
        'super_like_label': "⭐ *Супер Лайк Сәйкестік!* ",
        'match_label': "🎉 *Сәйкестік!* ",
        'super_like_note': "\n\n{sticker} Сізге Супер Лайк жіберілді.",
        'super_like_note_default': "\n\nСізге Супер Лайк жіберілді.",
        'pressed_super_like': "Супер Лайк жіберді!",
        'pressed_like': "де сізді ұнатты!",
        'write_username': "@{username} жазуға болады!",
        'no_username': "Бұл пайдаланушының username жоқ.",
        'like_notify_btn': "💌 *{name}* сізді лайк етті!\n\nҚабылдасаңыз чат арқылы сөйлесе аласыз.",
        'super_like_notify_btn': "⭐ *{name}* сізге {sticker}Супер Лайк жіберді!\n\nҚабылдасаңыз чат арқылы сөйлесе аласыз.",
        'btn_accept_like': "✅ Қабылдау",
        'btn_reject_like': "❌ Қабылдамау",
        'super_like_match_notify': "🎉⭐ *{name}* {sticker}Супер Лайк жіберді және сәйкестік болды!\n\nЕнді сөйлесе аласыз. 💬",
        'super_like_match_self': "🎉⭐ {sticker}Супер Лайк қабылданды! *{name}* де сізді ұнатты!\n\nЕнді сөйлесе аласыз. 💬",
        'anon_reveal_request_notify': "🌙 Әңгімелесушіңіз профильді ашуды сұрап жатыр. Егер келіссеңіз, чат негізгі Чат бөліміне көшіріледі.",
        'anon_reveal_declined_notify': "😔 Сіздің профильді ашу ұсынысыңыз әзірге қабылданбады. Анонимді чат жалғасуда.",
        'anon_disconnected_notify': "🚪 Әңгімелесушіңіз анонимді чаттан шықты. Чат аяқталды.",
        'anon_revealed_notify': "🎉 Тамаша! Екеуіңіз де профильді ашуға келістіңіз. Енді негізгі Чат бөлімінде сөйлесе аласыз.",
        'anon_match_found_notify': "🌙 *Анонимді әңгімелесуші табылды!*\n\nСізге сай әңгімелесуші табылды және чат басталды. Аты-жөні мен суреті әзірге жасырын.\n\nWeb App-ты ашып, «Сөйлесу» бөлімінен чатты жалғастырыңыз 👇",
        'anon_evening_reminder_notify': "🌙 *Анонимді чат уақыты келді!*\n\nСіз кез келген уақытта анонимді әңгімелесуші таба аласыз. Қазір көріп көресіз бе?\n\nWeb App-ты ашып, «Сөйлесу» бөлімінде «🔍 Әңгімелесуші табу» түймесін басыңыз 👇",
        'btn_report': "⚠️ Шағым",
        'report_choose_category': "⚠️ Шағым себебін таңдаңыз:",
        'report_cat_porn': "🔞 Порнография",
        'report_cat_drugs': "💊 Есірткі",
        'report_cat_violence': "⚔️ Зорлық-зомбылық",
        'report_cat_fraud': "💰 Алаяқтық",
        'report_cat_minor': "🚸 Кәмелетке толмаған",
        'report_cat_other': "❗ Басқа",
        'report_sent': "✅ Шағымыңыз қабылданды. Жақында тексеріледі.",
        'report_error': "❌ Шағымды жіберуде қате шықты.",
        'ban_message': "🚫 Аккаунтыңыз шағымдар негізінде уақытша шектелді.\n\n📌 Себебі: {reason}\n⏳ Шектеу аяқталу уақыты: {until}\n\nСіз бұл бот немесе Web App-ты пайдалана алмайсыз.",
        'super_like_sticker': "⭐ Супер Лайк үшін стикер таңдаңыз:",
    },
    'ky': {
        'welcome': "👋 Саламатсызбы, {name}!\n\n💙 *Таанышу ботуна кош келиңиз!*\n\nБул жерде жаңы досторду таап, баарлаша аласыз.",
        'select_language': "🌍 Тилди тандаңыз:",
        'language_changed': "✅ Тил өзгөртүлдү: {language_name}",
        'limits_info': "\n\n📊 *Күндөлүк лимиттер:*\n• Лайк: 25\n• Билдирүү: 10\n• Супер Лайк: 10\n\n🎁 *Лимитти көбөйтүү:*\n5 адам кошуңуз → 1 апта лимитсиз\n10 адам кошуңуз → 1 ай лимитсиз",
        'btn_webapp': "🌐 Веб-тиркеме",
        'btn_my_profile': "👤 Менин профилим",
        'btn_search': "🔎 Издөө",
        'btn_group': "👥 Топко кошулуу",
        'btn_change_lang': "🌍 Тилди өзгөртүү",
        'no_profile': "❌ Сиз али анкета толтура элексиз. Алгач профилиңизди толтуруңуз.",
        'fill_profile': "Анкетаны толтуруу",
        'please_fill_profile': "Сураныч, алдымен анкетаңызды толтуруңуз.",
        'search_who': "Кимди издеп жатасыз?\n\nЭркек, аял же баарын тандаңыз.\nЖе жылдызнама боюнча издеңиз! ⭐",
        'btn_male': "👨 Эркек",
        'btn_female': "👩 Аял",
        'btn_all': "🔄 Баары",
        'btn_zodiac_compat': "⭐ Жылдызнама боюнча издөө",
        'btn_back': "⬅ Артка",
        'btn_skip': "❌ Өткөрүп жиберүү",
        'btn_write': "✉️ Жазуу",
        'btn_like': "❤️ Лайк",
        'btn_super_like': "⭐ Супер Лайк",
        'btn_block': "🚫 Блок",
        'no_candidates': "😔 Эч ким табылбады.",
        'all_viewed': "✅ Бардык талапкерлер каралды. Кайра издеп көрүңүз.",
        'search_counter': "\n\n🔎 {current}/{total} талапкер",
        'no_zodiac': "❌ Жылдызнамаңыз көрсөтүлгөн эмес.\nАлгач анкетаны толтуруңуз.",
        'zodiac_not_recognized': "❌ Жылдызнамаңыз таанылбады. Анкетаны жаңыртыңыз.",
        'your_zodiac': "⭐ Сиздин жылдызнама: *{sign}*\n\nШайкеш жылдызнамалар:\n{compat}\n\nКимди издегиңиз келет?",
        'no_zodiac_match': "😔 Жылдызнама боюнча эч ким табылбады.",
        'no_results': "😔 Эч ким табылбады. Кийинчерээк кайталаңыз.",
        'searching': "Изделүүдө...",
        'like_sent': "💙 Лайк жөнөтүлдү!",
        'match': "🎉 Шайкештик! {name} да сизди жактырды!\n\nЭми баарлаша аласыз.",
        'like_notify': "💌 {name} сизди лайк кылды!\n\nВеб-тиркемедеги Чат бөлүмүн текшериңиз.",
        'super_like_sent': "⭐ Супер Лайк жөнөтүлдү!",
        'super_like_match': "⭐ Супер Лайк Шайкештик! {name} да сизди жактырды!\n\nЭми баарлаша аласыз.",
        'super_like_notify': "⭐ {name} сизге Супер Лайк жөнөттү!\n\nВеб-тиркемедеги Чат бөлүмүн текшериңиз.",
        'blocked': "🚫 Колдонуучу блоктолду.",
        'need_like_first': "❌ Алгач лайк жөнөтүү керек!",
        'send_message_text': "💬 Билдирүү текстин жазыңыз.",
        'message_sent': "✅ Билдирүү жөнөтүлдү!",
        'empty_message': "❌ Бош билдирүү жөнөтүүгө болбойт.",
        'new_message': "💬 {name} жаңы билдирүү:\n{text}",
        'profile_saved': "✅ *Анкетаңыз сакталды!*\n\nЭми издөө аркылуу жаңы досторду табыңыз. 🔍",
        'save_error': "❌ Ката кетти. Кайталап көрүңүз.",
        'limit_exceeded_likes': "❌ Күндөлүк лайк лимити бүттү!\n5 дос кошуңуз → 1 апта лимитсиз, 10 дос → 1 ай лимитсиз.",
        'limit_exceeded_messages': "❌ Күндөлүк билдирүү лимити бүттү!\n5 дос кошуңуз → 1 апта лимитсиз, 10 дос → 1 ай лимитсиз.",
        'limit_exceeded_super': "❌ Күндөлүк Супер Лайк лимити бүттү!\n5 дос кошуңуз → 1 апта лимитсиз, 10 дос → 1 ай лимитсиз.",
        'limit_info_long': "❌ Күндөлүк лимит бүттү!\n\n📊 Лимиттер:\n• Лайк: 25\n• Билдирүү: 10\n• Супер Лайк: 10\n\n🎁 Көбөйтүү:\n5 адам → 1 апта лимитсиз\n10 адам → 1 ай лимитсиз\n\nЖе эртең жаңы лимит.",
        'unlimited_access': "\n✅ *Лимитсиз колдонуу*",
        'daily_limits': "\n📊 *Күндөлүк лимиттер:*\n• Лайк: {likes}/25\n• Билдирүү: {messages}/10\n• Супер Лайк: {super_likes}/10",
        'gender_male': "Эркек",
        'gender_female': "Аял",
        'age': "Жаш",
        'city': "Шаар",
        'zodiac': "Жылдызнама",
        'about': "Мен жөнүндө",
        'spoken_language': "Баарлашуу тили",
        'goals': "Максаттар",
        'interests': "Кызыгуулар",
        'not_specified': "көрсөтүлгөн эмес",
        'searching_zodiac': "Жылдызнама боюнча изделүүдө...",
        'main_menu': "Негизги меню:",
        'group_invite_success': "🎉 *Куттуктайбыз!*\n\n*{name}* топко кошулду!\n\n{msg}",
        'like_accepted': "🎉 *{name}* лайкиңизди кабыл алды!\n\n💬 Эми Веб-тиркемедеги Чат аркылуу баарлашыңыз.",
        'chat_started': "✅ Сиз *{name}* менен баарлаша баштадыңыз!",
        'rejected': "❌ *{name}* сизди кабыл албады.\n\nКийинчерээк кайталаңыз.",
        'like_not_found': "Лайк табылбады",
        'super_like_label': "⭐ *Супер Лайк Шайкештик!* ",
        'match_label': "🎉 *Шайкештик!* ",
        'super_like_note': "\n\n{sticker} Сизге Супер Лайк жөнөтүлдү.",
        'super_like_note_default': "\n\nСизге Супер Лайк жөнөтүлдү.",
        'pressed_super_like': "Супер Лайк жөнөттү!",
        'pressed_like': "да сизди жактырды!",
        'write_username': "@{username} жазсаңыз болот!",
        'no_username': "Бул колдонуучунун username жок.",
        'like_notify_btn': "💌 *{name}* сизди жактырды!\n\nКабыл алсаңыз чат аркылуу баарлаша аласыз.",
        'super_like_notify_btn': "⭐ *{name}* сизге {sticker}Супер Лайк жөнөттү!\n\nКабыл алсаңыз чат аркылуу баарлаша аласыз.",
        'btn_accept_like': "✅ Кабыл алуу",
        'btn_reject_like': "❌ Баш тартуу",
        'super_like_match_notify': "🎉⭐ *{name}* {sticker}Супер Лайк жөнөттү жана шайкештик болду!\n\nЭми баарлаша аласыз. 💬",
        'super_like_match_self': "🎉⭐ {sticker}Супер Лайк кабыл алынды! *{name}* да сизди жактырды!\n\nЭми баарлаша аласыз. 💬",
        'anon_reveal_request_notify': "🌙 Маектешиңиз профильди ачууну сурап жатат. Эгер макул болсоңуз, маек негизги Маек бөлүмүнө которулат.",
        'anon_reveal_declined_notify': "😔 Сиздин профильди ачуу сунушуңуз азырынча кабыл алынган жок. Аноним маек уланууда.",
        'anon_disconnected_notify': "🚪 Маектешиңиз аноним маектен чыгып кетти. Маек аякталды.",
        'anon_revealed_notify': "🎉 Мыкты! Экөөңүз тең профильди ачууга макул болдуңуздар. Эми негизги Маек бөлүмүндө сүйлөшө аласыздар.",
        'anon_match_found_notify': "🌙 *Аноним маектеш табылды!*\n\nСизге ылайыктуу маектеш табылды жана маек башталды. Аты жана сүрөтү азырынча жашыруун.\n\nWeb App-ты ачып, «Баарлашуу» бөлүмүнөн маекти улантыңыз 👇",
        'anon_evening_reminder_notify': "🌙 *Аноним маек убактысы келди!*\n\nСиз каалаган убакта аноним маектеш таба аласыз. Азыр эле байкап көрөсүзбү?\n\nWeb App-ты ачып, «Баарлашуу» бөлүмүнөн маекти улантыңыз 👇",
        'btn_report': "⚠️ Даттануу",
        'report_choose_category': "⚠️ Даттануу себебин тандаңыз:",
        'report_cat_porn': "🔞 Порнография",
        'report_cat_drugs': "💊 Баңги зат",
        'report_cat_violence': "⚔️ Зомбулук",
        'report_cat_fraud': "💰 Алдамчылык",
        'report_cat_minor': "🚸 Кичине жаштагы бала",
        'report_cat_other': "❗ Башка",
        'report_sent': "✅ Даттанууңуз кабыл алынды. Жакында текшерилет.",
        'report_error': "❌ Даттанууну жөнөтүүдө ката кетти.",
        'ban_message': "🚫 Аккаунтуңуз даттануулардын негизинде убактылуу чектелди.\n\n📌 Себеби: {reason}\n⏳ Чектөө аяктоо убактысы: {until}\n\nСиз бул бот же Web App колдоно албайсыз.",
        'super_like_sticker': "⭐ Супер Лайк үчүн стикер тандаңыз:",
    },
    'kaa': {
        'welcome': "👋 Sálem, {name}!\n\n💙 *Tanısıw botına xosh kelipsiz!*\n\nBul jerde jańa dostlar tabıp, sóylesse alasız.",
        'select_language': "🌍 Tildi tańlań:",
        'language_changed': "✅ Til ózgeritildi: {language_name}",
        'limits_info': "\n\n📊 *Kúndelik limitler:*\n• Layk: 25\n• Xabar: 10\n• Super Layk: 10\n\n🎁 *Limitti arttırıw:*\n5 adam qosıń → 1 hápte limitsiz\n10 adam qosıń → 1 ay limitsiz",
        'btn_webapp': "🌐 Veb-qosımsha",
        'btn_my_profile': "👤 Meniń profilim",
        'btn_search': "🔎 Izlew",
        'btn_group': "👥 Topqa qosılıw",
        'btn_change_lang': "🌍 Tildi ózgertiw",
        'no_profile': "❌ Siz áli anketa toldırmagansız. Aldıńızdan profilińizdi toldırıń.",
        'fill_profile': "Anketa toldırıw",
        'please_fill_profile': "Iltimas, aldın ala anketa toldırıń.",
        'search_who': "Kimdi izlep atırsız?\n\nEr adam, hayal yamasa bárin tańlań.\nYamasa juldıznama boyınsha izleni! ⭐",
        'btn_male': "👨 Er adam",
        'btn_female': "👩 Hayal",
        'btn_all': "🔄 Bári",
        'btn_zodiac_compat': "⭐ Juldıznama boyınsha izlew",
        'btn_back': "⬅ Artqa",
        'btn_skip': "❌ Ótkizip jiberiw",
        'btn_write': "✉️ Jazıw",
        'btn_like': "❤️ Layk",
        'btn_super_like': "⭐ Super Layk",
        'btn_block': "🚫 Blok",
        'no_candidates': "😔 Eshkim tabılmadı.",
        'all_viewed': "✅ Barlıq kandidatlar qaraldı. Qayta izlep kóriń.",
        'search_counter': "\n\n🔎 {current}/{total} kandidat",
        'no_zodiac': "❌ Juldıznamańız kórsetilmegen.\nAldıńızdan anketani toldırıń.",
        'zodiac_not_recognized': "❌ Juldıznamańız tanılmadı. Anketani jańalań.",
        'your_zodiac': "⭐ Siziń juldıznamańız: *{sign}*\n\nSáykes juldıznamalar:\n{compat}\n\nKimdi izlegińiz keledi?",
        'no_zodiac_match': "😔 Juldıznama boyınsha eshkim tabılmadı.",
        'no_results': "😔 Eshkim tabılmadı. Keyinirek qaytalań.",
        'searching': "Izleniwde...",
        'like_sent': "💙 Layk jiberildi!",
        'match': "🎉 Sáykeslik! {name} de sizdi jaqtırdı!\n\nEndi sóylesse alasız.",
        'like_notify': "💌 {name} sizdi layk etti!\n\nVeb-qosımshadaǵı Chat bólimin tekseriń.",
        'super_like_sent': "⭐ Super Layk jiberildi!",
        'super_like_match': "⭐ Super Layk Sáykeslik! {name} de sizdi jaqtırdı!\n\nEndi sóylesse alasız.",
        'super_like_notify': "⭐ {name} sizge Super Layk jiberdi!\n\nVeb-qosımshadaǵı Chat bólimin tekseriń.",
        'blocked': "🚫 Paydalanıwşı bloklanǵan.",
        'need_like_first': "❌ Aldıńızdan layk jiberiw kerek!",
        'send_message_text': "💬 Xabar mátnin jazıń.",
        'message_sent': "✅ Xabar jiberildi!",
        'empty_message': "❌ Bos xabar jiberiwge bolmaydı.",
        'new_message': "💬 {name} jańa xabar:\n{text}",
        'profile_saved': "✅ *Anketańız saqlandı!*\n\nEndi izlew arqalı jańa dostlar tabıń. 🔍",
        'save_error': "❌ Qátelik boldı. Qaytalap kóriń.",
        'limit_exceeded_likes': "❌ Kúndelik layk limiti túgedi!\n5 dos qosıń → 1 hápte limitsiz, 10 dos → 1 ay limitsiz.",
        'limit_exceeded_messages': "❌ Kúndelik xabar limiti túgedi!\n5 dos qosıń → 1 hápte limitsiz, 10 dos → 1 ay limitsiz.",
        'limit_exceeded_super': "❌ Kúndelik Super Layk limiti túgedi!\n5 dos qosıń → 1 hápte limitsiz, 10 dos → 1 ay limitsiz.",
        'limit_info_long': "❌ Kúndelik limiti túgedi!\n\n📊 Limitler:\n• Layk: 25\n• Xabar: 10\n• Super Layk: 10\n\n🎁 Arttırıw:\n5 adam → 1 hápte limitsiz\n10 adam → 1 ay limitsiz\n\nYamasa erteń jańa limit.",
        'unlimited_access': "\n✅ *Limitsiz paydalanıw*",
        'daily_limits': "\n📊 *Kúndelik limitler:*\n• Layk: {likes}/25\n• Xabar: {messages}/10\n• Super Layk: {super_likes}/10",
        'gender_male': "Er adam",
        'gender_female': "Hayal",
        'age': "Jas",
        'city': "Qala",
        'zodiac': "Juldıznama",
        'about': "Men haqqımda",
        'spoken_language': "Sóylesiw tili",
        'goals': "Maqsetler",
        'interests': "Qızıǵıwshılıqlar",
        'not_specified': "kórsetilmegen",
        'searching_zodiac': "Juldıznama boyınsha izleniwde...",
        'main_menu': "Tiykarǵı menyu:",
        'group_invite_success': "🎉 *Qutlıqlaymız!*\n\n*{name}* topqa qosıldı!\n\n{msg}",
        'like_accepted': "🎉 *{name}* laykińizdi qabıl aldı!\n\n💬 Endi Veb-qosımshadaǵı Chat arqalı sólesiń.",
        'chat_started': "✅ Siz *{name}* menen sóylesiw basladıńız!",
        'rejected': "❌ *{name}* sizdi qabıl almadı.\n\nKeyinirek qaytalań.",
        'like_not_found': "Layk tabılmadı",
        'super_like_label': "⭐ *Super Layk Sáykeslik!* ",
        'match_label': "🎉 *Sáykeslik!* ",
        'super_like_note': "\n\n{sticker} Sizge Super Layk jiberildi.",
        'super_like_note_default': "\n\nSizge Super Layk jiberildi.",
        'pressed_super_like': "Super Layk jiberdi!",
        'pressed_like': "de sizdi jaqtırdı!",
        'write_username': "@{username} jazsańız boladı!",
        'no_username': "Bul paydalanıwshınıń username joq.",
        'like_notify_btn': "💌 *{name}* sizdi jaqtırdı!\n\nQabıl alsańız chat arqalı sólese alasız.",
        'super_like_notify_btn': "⭐ *{name}* sizge {sticker}Super Layk jiberdi!\n\nQabıl alsańız chat arqalı sólese alasız.",
        'btn_accept_like': "✅ Qabıl alıw",
        'btn_reject_like': "❌ Qabıl almaslik",
        'super_like_match_notify': "🎉⭐ *{name}* {sticker}Super Layk jiberdi hám sáykeslik boldı!\n\nEndi sólese alasız. 💬",
        'super_like_match_self': "🎉⭐ {sticker}Super Layk qabıl alındı! *{name}* de sizdi jaqtırdı!\n\nEndi sólese alasız. 💬",
        'anon_reveal_request_notify': "🌙 Sáwbetlesiwshiñiz profildi ashıwdı sorap atır. Eger razılıq berseñiz, sáwbet tiykarǵı Sáwbet bólimine kóshiriledi.",
        'anon_reveal_declined_notify': "😔 Sizdiń profildi ashıw usınısıńız házirshe qabıl etilmedi. Anonim sáwbet dawam etpekte.",
        'anon_disconnected_notify': "🚪 Sáwbetlesiwshiñiz anonim sáwbetten shıqtı. Sáwbet juwmaqlandı.",
        'anon_revealed_notify': "🎉 Ajayıp! Ekewiñiz de profildi ashıwǵa razı boldıńız. Endi tiykarǵı Sáwbet bóliminde sóylesiwdi dawam etesiz.",
        'anon_match_found_notify': "🌙 *Anonim sáwbetlesiwshi tabıldı!*\n\nSizge sáykes sáwbetlesiwshi tabıldı hám sáwbet baslandı. Atı hám súwreti házirshe jasırın.\n\nWeb App-tı ashıp, «Sóylesiw» bóliminen sáwbetti dawam etiń 👇",
        'anon_evening_reminder_notify': "🌙 *Anonim sáwbet waqtı keldi!*\n\nSiz qálegen waqıtta anonim sáwbetlesiwshi taba alasız. Házir sınap kóresizbe?\n\nWeb App-tı ashıp, «Sóylesiw» bóliminde «🔍 Sáwbetlesiwshi tabıw» knopkasın basıń 👇",
        'btn_report': "⚠️ Shikayat",
        'report_choose_category': "⚠️ Shikayat sebebin tańlań:",
        'report_cat_porn': "🔞 Pornografiya",
        'report_cat_drugs': "💊 Nasha",
        'report_cat_violence': "⚔️ Zorlıq",
        'report_cat_fraud': "💰 Aldawshılıq",
        'report_cat_minor': "🚸 Kishi jastaǵı bala",
        'report_cat_other': "❗ Basqa",
        'report_sent': "✅ Shikayatıńız qabıl etildi. Jaqında tekseriledi.",
        'report_error': "❌ Shikayat jiberiwde qátelik boldı.",
        'ban_message': "🚫 Akkauntıńız shikayatlar tiykarında waqtınsha sheklendi.\n\n📌 Sebebi: {reason}\n⏳ Sheklew tamamlanıw waqtı: {until}\n\nSiz bul bot yamasa Web App-tı paydalana almaysız.",
        'super_like_sticker': "⭐ Super Layk ushın stiker tańlań:",
    },
    'tg': {
        'welcome': "👋 Салом, {name}!\n\n💙 *Ба боти шиносоӣ хуш омадед!*\n\nДар ин ҷо шумо метавонед дӯстони нав пайдо кунед ва гуфтугӯ кунед.",
        'select_language': "🌍 Лутфан забонро интихоб кунед:",
        'language_changed': "✅ Забон иваз шуд: {language_name}",
        'limits_info': "\n\n📊 *Лимитҳои ҳаррӯза:*\n• Лайк: 25\n• Паём: 10\n• Супер Лайк: 10\n\n🎁 *Лимитро зиёд кардан:*\n5 нафар даъват кунед → 1 ҳафта бе лимит\n10 нафар даъват кунед → 1 моҳ бе лимит",
        'btn_webapp': "🌐 Веб-барнома",
        'btn_my_profile': "👤 Профили ман",
        'btn_search': "🔎 Ҷустуҷӯ",
        'btn_group': "👥 Ба гурӯҳ ҳамроҳ шудан",
        'btn_change_lang': "🌍 Забонро иваз кардан",
        'no_profile': "❌ Шумо ҳанӯз анкета пур накардаед. Лутфан аввал профилатонро пур кунед.",
        'fill_profile': "Анкетаро пур кунед",
        'please_fill_profile': "Лутфан, аввал анкетаатонро пур кунед.",
        'search_who': "Киро ҷустуҷӯ мекунед?\n\nМард, зан ё ҳамаро интихоб кунед.\nЁ аз рӯи бурҷ ҷустуҷӯ кунед! ⭐",
        'btn_male': "👨 Мард",
        'btn_female': "👩 Зан",
        'btn_all': "🔄 Ҳама",
        'btn_zodiac_compat': "⭐ Ҷустуҷӯ аз рӯи бурҷ",
        'btn_back': "⬅ Бозгашт",
        'btn_skip': "❌ Гузаронидан",
        'btn_write': "✉️ Навиштан",
        'btn_like': "❤️ Лайк",
        'btn_super_like': "⭐ Супер Лайк",
        'btn_block': "🚫 Блок",
        'no_candidates': "😔 Ҳеҷ кас ёфт нашуд.",
        'all_viewed': "✅ Ҳама номзадҳо дида шуданд. Боз ҷустуҷӯ кунед.",
        'search_counter': "\n\n🔎 Номзади {current} аз {total}",
        'no_zodiac': "❌ Бурҷатон нишон дода нашудааст.\nЛутфан аввал анкета пур кунед.",
        'zodiac_not_recognized': "❌ Бурҷатон шинохта нашуд. Анкетаро нав кунед.",
        'your_zodiac': "⭐ Бурҷи шумо: *{sign}*\n\nБурҷҳои мувофиқ:\n{compat}\n\nКиро ҷустуҷӯ кардан мехоҳед?",
        'no_zodiac_match': "😔 Аз рӯи бурҷ ҳеҷ кас ёфт нашуд.",
        'no_results': "😔 Ҳеҷ кас ёфт нашуд. Баъдтар боз кӯшиш кунед.",
        'searching': "Ҷустуҷӯ...",
        'like_sent': "💙 Лайк фиристода шуд!",
        'match': "🎉 Мувофиқат! {name} ҳам шуморо лайк кард!\n\nАкнун метавонед гуфтугӯ кунед.",
        'like_notify': "💌 {name} шуморо лайк кард!\n\nБахши Чат дар Веб-барномаро санҷед.",
        'super_like_sent': "⭐ Супер Лайк фиристода шуд!",
        'super_like_match': "⭐ Супер Лайк Мувофиқат! {name} ҳам шуморо лайк кард!\n\nАкнун метавонед гуфтугӯ кунед.",
        'super_like_notify': "⭐ {name} ба шумо Супер Лайк фиристод!\n\nБахши Чат дар Веб-барномаро санҷед.",
        'blocked': "🚫 Истифодабаранда блок карда шуд.",
        'need_like_first': "❌ Аввал лайк фиристодан лозим аст!",
        'send_message_text': "💬 Матни паёмро нависед.",
        'message_sent': "✅ Паём фиристода шуд!",
        'empty_message': "❌ Паёми холӣ фиристодан мумкин нест.",
        'new_message': "💬 {name} паёми нав:\n{text}",
        'profile_saved': "✅ *Анкетатон нигоҳ дошта шуд!*\n\nАкнун тавассути ҷустуҷӯ дӯстони нав пайдо кунед. 🔍",
        'save_error': "❌ Хатогӣ рӯй дод. Боз кӯшиш кунед.",
        'limit_exceeded_likes': "❌ Лимити лайки ҳаррӯза тамом шуд!\n5 дӯст даъват кунед → 1 ҳафта бе лимит, 10 дӯст → 1 моҳ бе лимит.",
        'limit_exceeded_messages': "❌ Лимити паёми ҳаррӯза тамом шуд!\n5 дӯст даъват кунед → 1 ҳафта бе лимит, 10 дӯст → 1 моҳ бе лимит.",
        'limit_exceeded_super': "❌ Лимити Супер Лайки ҳаррӯза тамом шуд!\n5 дӯст даъват кунед → 1 ҳафта бе лимит, 10 дӯст → 1 моҳ бе лимит.",
        'limit_info_long': "❌ Лимити ҳаррӯза тамом шуд!\n\n📊 Лимитҳо:\n• Лайк: 25\n• Паём: 10\n• Супер Лайк: 10\n\n🎁 Зиёд кардан:\n5 нафар → 1 ҳафта бе лимит\n10 нафар → 1 моҳ бе лимит\n\nЁ фардо лимити нав.",
        'unlimited_access': "\n✅ *Дастрасии бе лимит*",
        'daily_limits': "\n📊 *Лимитҳои ҳаррӯза:*\n• Лайк: {likes}/25\n• Паём: {messages}/10\n• Супер Лайк: {super_likes}/10",
        'gender_male': "Мард",
        'gender_female': "Зан",
        'age': "Син",
        'city': "Шаҳр",
        'zodiac': "Бурҷ",
        'about': "Дар бораи ман",
        'spoken_language': "Забони муошират",
        'goals': "Мақсадҳо",
        'interests': "Шавқҳо",
        'not_specified': "нишон дода нашудааст",
        'searching_zodiac': "Ҷустуҷӯ аз рӯи бурҷ...",
        'main_menu': "Менюи асосӣ:",
        'group_invite_success': "🎉 *Табрик!*\n\n*{name}* ба гурӯҳ ҳамроҳ шуд!\n\n{msg}",
        'like_accepted': "🎉 *{name}* лайки шуморо қабул кард!\n\n💬 Акнун тавассути Чати Веб-барнома гуфтугӯ кунед.",
        'chat_started': "✅ Шумо бо *{name}* гуфтугӯ оғоз кардед!",
        'rejected': "❌ *{name}* шуморо рад кард.\n\nБаъдтар боз кӯшиш кунед.",
        'like_not_found': "Лайк ёфт нашуд",
        'super_like_label': "⭐ *Супер Лайк Мувофиқат!* ",
        'match_label': "🎉 *Мувофиқат!* ",
        'super_like_note': "\n\n{sticker} Ба шумо Супер Лайк фиристода шуд.",
        'super_like_note_default': "\n\nБа шумо Супер Лайк фиристода шуд.",
        'pressed_super_like': "Супер Лайк фиристод!",
        'pressed_like': "ҳам шуморо лайк кард!",
        'write_username': "Метавонед ба @{username} нависед!",
        'no_username': "Ин истифодабаранда username надорад.",
        'like_notify_btn': "💌 *{name}* шуморо лайк кард!\n\nАгар қабул кунед — тавассути чат гуфтугӯ карда метавонед.",
        'super_like_notify_btn': "⭐ *{name}* ба шумо {sticker}Супер Лайк фиристод!\n\nАгар қабул кунед — тавассути чат гуфтугӯ карда метавонед.",
        'btn_accept_like': "✅ Қабул кардан",
        'btn_reject_like': "❌ Рад кардан",
        'super_like_match_notify': "🎉⭐ *{name}* {sticker}Супер Лайк фиристод ва мувофиқат шуд!\n\nАкнун метавонед гуфтугӯ кунед. 💬",
        'super_like_match_self': "🎉⭐ {sticker}Супер Лайк қабул шуд! *{name}* ҳам шуморо лайк кард!\n\nАкнун метавонед гуфтугӯ кунед. 💬",
        'anon_reveal_request_notify': "🌙 Ҳамсуҳбататон дархости кушодани профилро дорад. Агар розӣ шавед, чат ба бахши асосии Чат гузаронида мешавад.",
        'anon_reveal_declined_notify': "😔 Пешниҳоди кушодани профили шумо ҳоло қабул нашуд. Чати ношинос идома дорад.",
        'anon_disconnected_notify': "🚪 Ҳамсуҳбататон чати ношиносро тарк кард. Чат хотима ёфт.",
        'anon_revealed_notify': "🎉 Аҷоиб! Ҳар дуятон ба кушодани профил розӣ шудед. Ҳоло метавонед дар бахши асосии Чат гуфтугӯро идома диҳед.",
        'anon_match_found_notify': "🌙 *Ҳамсуҳбати ношинос ёфт шуд!*\n\nБарои шумо ҳамсуҳбат ёфт шуд ва чат аллакай оғоз шудааст. Ном ва акс ҳанӯз пинҳон аст.\n\nWeb App-ро кушоед ва дар бахши «Гуфтугӯ» чатро идома диҳед 👇",
        'anon_evening_reminder_notify': "🌙 *Вақти чати ношинос расид!*\n\nШумо метавонед дар ҳар вақт ҳамсуҳбати ношинос пайдо кунед. Ҳоло озмоиш мекунед?\n\nWeb App-ро кушоед ва дар бахши «Гуфтугӯ» тугмаи «🔍 Ёфтани ҳамсуҳбат»-ро пахш кунед 👇",
        'btn_report': "⚠️ Шикоят",
        'report_choose_category': "⚠️ Сабаби шикоятро интихоб кунед:",
        'report_cat_porn': "🔞 Порнография",
        'report_cat_drugs': "💊 Маводи мухаддир",
        'report_cat_violence': "⚔️ Зӯроварӣ",
        'report_cat_fraud': "💰 Фиреб",
        'report_cat_minor': "🚸 Кӯдаки ноболиғ",
        'report_cat_other': "❗ Дигар",
        'report_sent': "✅ Шикояти шумо қабул шуд. Ба зудӣ баррасӣ мешавад.",
        'report_error': "❌ Хатогӣ ҳангоми фиристодани шикоят.",
        'ban_message': "🚫 Ҳисоби шумо дар асоси шикоятҳо муваққатан маҳдуд шудааст.\n\n📌 Сабаб: {reason}\n⏳ Вақти анҷоми маҳдудият: {until}\n\nШумо аз ин бот ё Web App истифода карда наметавонед.",
        'super_like_sticker': "⭐ Барои Супер Лайк стикер интихоб кунед:",
    },
    'en': {
        'welcome': "👋 Hello, {name}!\n\n💙 *Welcome to the Friendship & Dating Bot!*\n\nHere you can find new friends and chat.",
        'select_language': "🌍 Please select your language:",
        'language_changed': "✅ Language changed: {language_name}",
        'limits_info': "\n\n📊 *Daily limits:*\n• Likes: 25\n• Messages: 10\n• Super Likes: 10\n\n🎁 *Increase your limit:*\nInvite 5 people to the group → 1 week unlimited\nInvite 10 people to the group → 1 month unlimited",
        'btn_webapp': "🌐 Web App",
        'btn_my_profile': "👤 My profile",
        'btn_search': "🔎 Search",
        'btn_group': "👥 Join the group",
        'btn_change_lang': "🌍 Change language",
        'no_profile': "❌ You haven't filled out a profile yet. Please fill out your profile first.",
        'fill_profile': "Fill profile",
        'please_fill_profile': "Please fill your profile first.",
        'search_who': "Who are you looking for?\n\nChoose male, female, or everyone.\nOr search for people matching your zodiac sign! ⭐",
        'btn_male': "👨 Male",
        'btn_female': "👩 Female",
        'btn_all': "🔄 Everyone",
        'btn_zodiac_compat': "⭐ Search by zodiac match",
        'btn_back': "⬅ Back",
        'btn_skip': "❌ Skip",
        'btn_write': "✉️ Write",
        'btn_like': "❤️ Like",
        'btn_super_like': "⭐ Super Like",
        'btn_block': "🚫 Block",
        'no_candidates': "😔 No candidates found.",
        'all_viewed': "✅ You've viewed all candidates. Try searching again from the menu.",
        'search_counter': "\n\n🔎 {current}/{total} candidates",
        'no_zodiac': "❌ Your zodiac sign isn't set in your profile.\nPlease fill out your profile and select your zodiac sign first.",
        'zodiac_not_recognized': "❌ Your zodiac sign wasn't recognized. Please update your profile.",
        'your_zodiac': "⭐ Your zodiac sign: *{sign}*\n\nCompatible signs for you:\n{compat}\n\nWhich gender would you like to search for?",
        'no_zodiac_match': "😔 No one matching your zodiac sign was found. Try again later.",
        'no_results': "😔 No one was found. Try again later.",
        'searching': "Searching...",
        'like_sent': "💙 Like sent!",
        'match': "🎉 Match! {name} liked you too!\n\nYou can start chatting now.",
        'like_notify': "💌 {name} liked you!\n\nCheck the Chat section in the Web App.",
        'super_like_sent': "⭐ Super Like sent!",
        'super_like_match': "⭐ Super Like Match! {name} liked you too!\n\nYou can start chatting now.",
        'super_like_notify': "⭐ {name} sent you a Super Like!\n\nCheck the Chat section in the Web App.",
        'blocked': "🚫 User blocked.",
        'need_like_first': "❌ You need to send a like first!",
        'send_message_text': "💬 Write your message text. Only one message will be sent.",
        'message_sent': "✅ Message sent!",
        'empty_message': "❌ You can't send an empty message.",
        'new_message': "💬 New message from {name}:\n{text}",
        'profile_saved': "✅ *Your profile was saved successfully!*\n\nNow find new friends through search. 🔍",
        'save_error': "❌ An error occurred. Please try again.",
        'limit_exceeded_likes': "❌ Your daily like limit is over!\n\nInvite 5 friends for 1 week unlimited, or 10 friends for 1 month unlimited.",
        'limit_exceeded_messages': "❌ Your daily message limit is over!\n\nInvite 5 friends for 1 week unlimited, or 10 friends for 1 month unlimited.",
        'limit_exceeded_super': "❌ Your daily Super Like limit is over!\n\nInvite 5 friends for 1 week unlimited, or 10 friends for 1 month unlimited.",
        'limit_info_long': "❌ Your daily limit is over!\n\n📊 Daily limits:\n• Likes: 25\n• Messages: 10\n• Super Likes: 10\n\n🎁 Increase your limit:\nInvite 5 people to the group → 1 week unlimited\nInvite 10 people to the group → 1 month unlimited\n\nOr continue tomorrow with a new limit.",
        'unlimited_access': "\n✅ *Unlimited access*",
        'daily_limits': "\n📊 *Daily limits:*\n• Likes: {likes}/25\n• Messages: {messages}/10\n• Super Likes: {super_likes}/10",
        'gender_male': "Male",
        'gender_female': "Female",
        'age': "Age",
        'city': "City",
        'zodiac': "Zodiac sign",
        'about': "About me",
        'spoken_language': "Spoken language",
        'goals': "Goal",
        'interests': "Interests",
        'not_specified': "not specified",
        'searching_zodiac': "Searching by zodiac sign...",
        'main_menu': "Main menu:",
        'group_invite_success': "🎉 *Congratulations!*\n\n*{name}* joined the group!\n\n{msg}",
        'like_accepted': "🎉 *{name}* accepted your like!\n\n💬 You can now start a conversation in the Chat section of the Web App.",
        'chat_started': "✅ You started a conversation with *{name}*!",
        'rejected': "❌ *{name}* rejected you.\n\nTry again later.",
        'like_not_found': "Like not found",
        'super_like_label': "⭐ *Super Like Match!* ",
        'match_label': "🎉 *Match!* ",
        'super_like_note': "\n\n{sticker} A Super Like was sent to you with the chosen emoji.",
        'super_like_note_default': "\n\nA Super Like was sent to you.",
        'pressed_super_like': "Sent a Super Like!",
        'pressed_like': "liked you too!",
        'write_username': "You can message @{username}!",
        'no_username': "This user doesn't have a username.",
        'like_notify_btn': "💌 *{name}* liked you!\n\nIf you accept, you can chat together.",
        'super_like_notify_btn': "⭐ *{name}* sent you a {sticker}Super Like!\n\nIf you accept, you can chat together.",
        'btn_accept_like': "✅ Accept",
        'btn_reject_like': "❌ Decline",
        'super_like_match_notify': "🎉⭐ *{name}* sent a {sticker}Super Like and it's a match!\n\nYou can start chatting now. 💬",
        'super_like_match_self': "🎉⭐ {sticker}Super Like accepted! *{name}* liked you back!\n\nYou can start chatting now. 💬",
        'anon_reveal_request_notify': "🌙 Your chat partner wants to reveal their profile. If you agree, the chat will move to the main Chat section.",
        'anon_reveal_declined_notify': "😔 Your request to reveal profiles wasn't accepted yet. The anonymous chat continues.",
        'anon_disconnected_notify': "🚪 Your chat partner left the anonymous chat. The chat has ended.",
        'anon_revealed_notify': "🎉 Great! You both agreed to reveal your profiles. You can now continue chatting in the main Chat section.",
        'anon_match_found_notify': "🌙 *Anonymous chat partner found!*\n\nWe found you a match and the chat has already started. Name and photo are still hidden.\n\nOpen the Web App and continue the chat in the \"Chat\" section 👇",
        'anon_evening_reminder_notify': "🌙 *Time for anonymous chat!*\n\nYou can find an anonymous chat partner anytime. Want to try now?\n\nOpen the Web App and tap \"🔍 Find a partner\" in the \"Chat\" section 👇",
        'btn_report': "⚠️ Report",
        'report_choose_category': "⚠️ Choose a reason for the report:",
        'report_cat_porn': "🔞 Pornography",
        'report_cat_drugs': "💊 Drugs",
        'report_cat_violence': "⚔️ Violence",
        'report_cat_fraud': "💰 Fraud",
        'report_cat_minor': "🚸 Underage user",
        'report_cat_other': "❗ Other",
        'report_sent': "✅ Your report has been received. It will be reviewed soon.",
        'report_error': "❌ Error sending the report.",
        'ban_message': "🚫 Your account has been temporarily restricted due to reports.\n\n📌 Reason: {reason}\n⏳ Restriction ends: {until}\n\nYou cannot use this bot or the Web App.",
        'super_like_sticker': "⭐ Choose a sticker for your Super Like:",
    },
}


def t(lang, key, **kwargs):
    """Tarjima olish"""
    if lang not in T:
        lang = 'uz'
    text = T[lang].get(key, T['uz'].get(key, key))
    if kwargs:
        try:
            safe = {k: (escape_md(v) if k in ('name', 'full_name') and isinstance(v, str) else v)
                    for k, v in kwargs.items()}
            text = text.format(**safe)
        except Exception:
            try:
                text = text.format(**kwargs)
            except Exception:
                pass
    return text


# ========== SUPER LIKE STIKERLARI ==========
# Web App'dagi STICKERS ro'yxati bilan bir xil (app.js)
STICKERS = ['😇', '😅', '😳', '😎', '🤔', '👋', '🥰', '❤️', '😍', '🤫',
            '😜', '🫣', '👍', '👏', '😡', '🫦', '🔥', '💔', '🌹', '😉']


def build_candidate_keyboard(lang, telegram_id):
    """Qidiruv natijasidagi anketa ostidagi standart tugmalar (Like/Super Like/Skip/Write/Back)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=t(lang, 'btn_like'), callback_data=f"search_like:{telegram_id}"),
        InlineKeyboardButton(text=t(lang, 'btn_super_like'), callback_data=f"search_super_like_pick:{telegram_id}")
    )
    builder.row(
        InlineKeyboardButton(text=t(lang, 'btn_skip'), callback_data="search_skip"),
        InlineKeyboardButton(text=t(lang, 'btn_write'), callback_data=f"search_message:{telegram_id}")
    )
    builder.row(
        InlineKeyboardButton(text=t(lang, 'btn_report'), callback_data=f"report_pick:{telegram_id}")
    )
    builder.row(
        InlineKeyboardButton(text=t(lang, 'btn_back'), callback_data="show_main_menu")
    )
    return builder.as_markup()


def build_report_category_keyboard(reported_id):
    """Shikoyat toifasini tanlash klaviaturasi."""
    builder = InlineKeyboardBuilder()
    for cat_key, label_key in (
        ('porn', 'report_cat_porn'),
        ('drugs', 'report_cat_drugs'),
        ('violence', 'report_cat_violence'),
        ('fraud', 'report_cat_fraud'),
        ('minor', 'report_cat_minor'),
        ('other', 'report_cat_other'),
    ):
        builder.row(InlineKeyboardButton(
            text=t('uz', label_key),
            callback_data=f"report_cat:{reported_id}:{cat_key}"
        ))
    return builder.as_markup()


@dp.callback_query(F.data.startswith("report_pick:"))
async def report_pick_callback(callback: types.CallbackQuery):
    reported_id = int(callback.data.split(":", 1)[1])
    lang = await get_user_lang(callback.from_user.id)
    await callback.answer()
    await callback.message.answer(
        t(lang, 'report_choose_category'),
        reply_markup=build_report_category_keyboard(reported_id)
    )


@dp.callback_query(F.data.startswith("report_cat:"))
async def report_category_callback(callback: types.CallbackQuery):
    _, reported_id_str, category = callback.data.split(":", 2)
    reported_id = int(reported_id_str)
    reporter_id = callback.from_user.id
    lang = await get_user_lang(reporter_id)

    if reporter_id == reported_id:
        await callback.answer()
        return

    existing = await db.get_recent_reports_for_pair(reporter_id, reported_id, hours=24)
    if existing:
        await callback.answer(t(lang, 'report_sent'), show_alert=True)
        return

    reported_user = await db.get_user(reported_id)
    photo_base64 = reported_user.get('photo_base64') if reported_user else None

    context_snapshot = {'messages': [], 'has_photo': bool(photo_base64)}
    report_id = await db.create_report(reporter_id, reported_id, category, '', 'bot_search', context_snapshot)
    asyncio.create_task(
        process_report_background(report_id, reporter_id, reported_id, category, [], photo_base64)
    )

    await callback.answer(t(lang, 'report_sent'), show_alert=True)


def build_sticker_picker_keyboard(lang, telegram_id):
    """Super Like uchun stikerlar klaviaturasi (5 ustunli grid + bekor qilish tugmasi)."""
    builder = InlineKeyboardBuilder()
    row = []
    for idx, sticker in enumerate(STICKERS):
        row.append(InlineKeyboardButton(text=sticker, callback_data=f"search_super_like_send:{telegram_id}:{idx}"))
        if len(row) == 5:
            builder.row(*row)
            row = []
    if row:
        builder.row(*row)
    builder.row(InlineKeyboardButton(text=t(lang, 'btn_skip'), callback_data=f"search_super_like_cancel:{telegram_id}"))
    return builder.as_markup()



ZODIAC_SIGNS = {
    "qoy": ("Qo'y", "♈"),
    "buzoq": ("Buzoq", "♉"),
    "egizak": ("Egizak", "♊"),
    "qisqichbaqa": ("Qisqichbaqa", "♋"),
    "arslon": ("Arslon", "♌"),
    "sunbula": ("Sunbula", "♍"),
    "tarozi": ("Tarozi", "♎"),
    "chayon": ("Chayon", "♏"),
    "oqotar": ("O'qotar", "♐"),
    "tog_echkisi": ("Tog' echkisi", "♑"),
    "qovga": ("Qovg'a", "♒"),
    "baliq": ("Baliq", "♓"),
}

ZODIAC_COMPATIBILITY = {
    "qoy": {"mos": ["arslon", "egizak", "oqotar"], "qiyin": ["qisqichbaqa", "chayon", "baliq"]},
    "buzoq": {"mos": ["sunbula", "qisqichbaqa", "tog_echkisi"], "qiyin": ["egizak", "oqotar", "qovga"]},
    "egizak": {"mos": ["qoy", "tarozi", "qovga"], "qiyin": ["buzoq", "chayon", "tog_echkisi"]},
    "qisqichbaqa": {"mos": ["buzoq", "baliq", "chayon"], "qiyin": ["qoy", "egizak", "oqotar"]},
    "arslon": {"mos": ["qoy", "egizak", "tarozi"], "qiyin": ["buzoq", "tog_echkisi", "baliq"]},
    "sunbula": {"mos": ["buzoq", "tog_echkisi", "chayon"], "qiyin": ["egizak", "arslon", "oqotar"]},
    "tarozi": {"mos": ["egizak", "arslon", "qovga"], "qiyin": ["chayon", "qisqichbaqa", "tog_echkisi"]},
    "chayon": {"mos": ["qisqichbaqa", "baliq", "buzoq"], "qiyin": ["egizak", "qoy", "tarozi"]},
    "oqotar": {"mos": ["qoy", "arslon", "qovga"], "qiyin": ["buzoq", "qisqichbaqa", "tog_echkisi"]},
    "tog_echkisi": {"mos": ["buzoq", "sunbula", "chayon"], "qiyin": ["egizak", "tarozi", "oqotar"]},
    "qovga": {"mos": ["oqotar", "egizak", "tarozi"], "qiyin": ["buzoq", "chayon", "qisqichbaqa"]},
    "baliq": {"mos": ["buzoq", "qisqichbaqa", "chayon"], "qiyin": ["qoy", "egizak", "arslon"]},
}

ZODIAC_NAME_TO_KEY = {
    "qoy": "qoy", "qo'y": "qoy", "qo`y": "qoy", "qoy (aries)": "qoy", "aries": "qoy",
    "buzoq": "buzoq", "buqa": "buzoq", "buzoq (taurus)": "buzoq", "taurus": "buzoq",
    "egizak": "egizak", "egizaklar": "egizak", "egizaklar (gemini)": "egizak", "gemini": "egizak",
    "qisqichbaqa": "qisqichbaqa", "qisqichbaqa (cancer)": "qisqichbaqa", "cancer": "qisqichbaqa",
    "arslon": "arslon", "sher": "arslon", "sher (leo)": "arslon", "leo": "arslon",
    "sunbula": "sunbula", "qiz": "sunbula", "qiz (virgo)": "sunbula", "virgo": "sunbula",
    "tarozi": "tarozi", "tarozi (libra)": "tarozi", "libra": "tarozi",
    "chayon": "chayon", "chayonlar": "chayon", "chayonlar (scorpio)": "chayon", "scorpio": "chayon",
    "oqotar": "oqotar", "o'qotar": "oqotar", "yoy": "oqotar", "yoy (sagittarius)": "oqotar", "sagittarius": "oqotar",
    "tog echkisi": "tog_echkisi", "tog' echkisi": "tog_echkisi", "togʻ echkisi": "tog_echkisi",
    "tog echkisi (capricorn)": "tog_echkisi", "capricorn": "tog_echkisi",
    "qovga": "qovga", "qovg'a": "qovga", "qovgʻa": "qovga", "qovunchi": "qovga",
    "qovunchi (aquarius)": "qovga", "aquarius": "qovga",
    "baliq": "baliq", "baliq (pisces)": "baliq", "pisces": "baliq",
}


def normalize_zodiac_key(value: str) -> str | None:
    if not value:
        return None
    text = str(value)
    text = text.replace('’', "'").replace('`', "'").replace('ʻ', "'")
    text = text.replace('♈', '').replace('♉', '').replace('♊', '')
    text = text.replace('♋', '').replace('♌', '').replace('♍', '')
    text = text.replace('♎', '').replace('♏', '').replace('♐', '')
    text = text.replace('♑', '').replace('♒', '').replace('♓', '')
    text = text.replace('(', ' ').replace(')', ' ')
    text = text.lower()
    text = ' '.join(text.split())

    direct = ZODIAC_NAME_TO_KEY.get(text)
    if direct:
        return direct

    alias = ZODIAC_NAME_TO_KEY.get(text.replace("'", ""))
    if alias:
        return alias

    for name, key in ZODIAC_NAME_TO_KEY.items():
        if text == name or text.startswith(name) or name.startswith(text):
            return key

    return None


def get_zodiac_key(zodiac_value: str) -> str | None:
    return normalize_zodiac_key(zodiac_value)


def build_zodiac_compat_filters(zodiac_compat_list, searcher_zodiac=None):
    """zodiac_compat_list (mos burjlar) + qidiruvchining o'z burjini birlashtirib,
    qidiruv uchun kerakli zodiac_keys va zodiac_names ro'yxatlarini tuzadi."""
    mos_keys = []
    mos_names = []
    for name in zodiac_compat_list:
        key = get_zodiac_key(name)
        if key:
            mos_keys.append(key)
            mos_names.append(name)

    # Qidiruvchining o'z burjini ham qo'shamiz (masalan Qo'y -> mos: Arslon, Egizak, O'qotar + Qo'y)
    own_key = get_zodiac_key(searcher_zodiac) if searcher_zodiac else None
    if own_key and own_key not in mos_keys:
        mos_keys.append(own_key)
        mos_names.append(own_key)

    for key in mos_keys:
        for name, name_key in ZODIAC_NAME_TO_KEY.items():
            if name_key == key and name not in mos_names:
                mos_names.append(name)

    return mos_keys, mos_names


# ========== QIZIQISHLAR TARJIMASI ==========
INTERESTS_LABELS = {
    'uz': {
        'int_kino': '🍿 Kino', 'int_musiqa': '🎵 Musiqa', 'int_kitob': "📚 Kitob o'qish",
        'int_oyinlar': "🎮 O'yinlar", 'int_teatr': '🎭 Teatr', 'int_muzey': '🏛️ Muzeylar',
        'int_sanat': "🎨 San'at", 'int_foto': '📸 Foto', 'int_sheeriyat': "📜 She'riyat",
        'int_raqs': '💃 Raqs', 'int_sport': '⚽ Sport', 'int_yoga': '🧘 Yoga',
        'int_sayr': '🚶 Sayr', 'int_tennis': '🏓 Tennis', 'int_sayohat': '✈️ Sayohat',
        'int_plyaj': '🏖️ Plyaj', 'int_shopping': '🛍️ Shopping', 'int_moda': '👗 Moda',
        'int_qahva': '☕ Qahva', 'int_vino': '🍷 Vino', 'int_pivo': '🍺 Pivo', 'int_blog': '✍️ Blog', 'int_dasturlash': '💻 Dasturlash',
        'int_shaxmat': '♟️ Shaxmat', 'int_rasm': '🎨 Rasm', 'int_tillar': "🗣️ Tillar",
    },
    'ru': {
        'int_kino': '🍿 Кино', 'int_musiqa': '🎵 Музыка', 'int_kitob': '📚 Чтение',
        'int_oyinlar': '🎮 Игры', 'int_teatr': '🎭 Театр', 'int_muzey': '🏛️ Музеи',
        'int_sanat': '🎨 Искусство', 'int_foto': '📸 Фото', 'int_sheeriyat': '📜 Поэзия',
        'int_raqs': '💃 Танцы', 'int_sport': '⚽ Спорт', 'int_yoga': '🧘 Йога',
        'int_sayr': '🚶 Прогулки', 'int_tennis': '🏓 Теннис', 'int_sayohat': '✈️ Путешествия',
        'int_plyaj': '🏖️ Пляж', 'int_shopping': '🛍️ Шоппинг', 'int_moda': '👗 Мода',
        'int_qahva': '☕ Кофе', 'int_vino': '🍷 Вино', 'int_pivo': '🍺 Пиво', 'int_blog': '✍️ Блог', 'int_dasturlash': '💻 Программирование',
        'int_shaxmat': '♟️ Шахматы', 'int_rasm': '🎨 Рисование', 'int_tillar': '🗣️ Языки',
    },
    'en': {
        'int_kino': '🍿 Movies', 'int_musiqa': '🎵 Music', 'int_kitob': '📚 Reading',
        'int_oyinlar': '🎮 Gaming', 'int_teatr': '🎭 Theatre', 'int_muzey': '🏛️ Museums',
        'int_sanat': '🎨 Art', 'int_foto': '📸 Photo', 'int_sheeriyat': '📜 Poetry',
        'int_raqs': '💃 Dancing', 'int_sport': '⚽ Sport', 'int_yoga': '🧘 Yoga',
        'int_sayr': '🚶 Walking', 'int_tennis': '🏓 Tennis', 'int_sayohat': '✈️ Travel',
        'int_plyaj': '🏖️ Beach', 'int_shopping': '🛍️ Shopping', 'int_moda': '👗 Fashion',
        'int_qahva': '☕ Coffee', 'int_vino': '🍷 Wine', 'int_pivo': '🍺 Beer', 'int_blog': '✍️ Blogging', 'int_dasturlash': '💻 Coding',
        'int_shaxmat': '♟️ Chess', 'int_rasm': '🎨 Drawing', 'int_tillar': '🗣️ Languages',
    },
}
# Qolgan tillar uchun uz dan foydalaniladi

GOALS_LABELS = {
    'uz': {
        'goal_jiddiy': '💍 Jiddiy (Oila)', 'goal_dostlik_suhbat': "💬 Do'stlik",
        'goal_hamroh': '🧳 Hamroh', 'goal_dostlik': "Do'stlik",
        'goal_tanishuv': 'Tanishuv', 'goal_oila': 'Oila',
        'goal_sevgi': 'Sevgi', 'goal_romantika': 'Romantika',
        'goal_uchrashuv': 'Uchrashuv', 'goal_virtual': 'Virtual muloqot',
        'goal_boshqa': 'Boshqa',
    },
    'ru': {
        'goal_jiddiy': '💍 Серьёзно', 'goal_dostlik_suhbat': '💬 Дружба',
        'goal_hamroh': '🧳 Компаньон', 'goal_dostlik': 'Дружба',
        'goal_tanishuv': 'Знакомство', 'goal_oila': 'Семья',
        'goal_sevgi': 'Любовь', 'goal_romantika': 'Романтика',
        'goal_uchrashuv': 'Свидание', 'goal_virtual': 'Виртуальное общение',
        'goal_boshqa': 'Другое',
    },
    'en': {
        'goal_jiddiy': '💍 Serious', 'goal_dostlik_suhbat': '💬 Friendship',
        'goal_hamroh': '🧳 Companion', 'goal_dostlik': 'Friendship',
        'goal_tanishuv': 'Dating', 'goal_oila': 'Family',
        'goal_sevgi': 'Love', 'goal_romantika': 'Romance',
        'goal_uchrashuv': 'Meeting', 'goal_virtual': 'Virtual',
        'goal_boshqa': 'Other',
    },
}

# Burj nomlari tillarga ko'ra
ZODIAC_DISPLAY = {
    'uz': {
        'qoy': "♈ Qo'y", 'buzoq': '♉ Buzoq', 'egizak': '♊ Egizak',
        'qisqichbaqa': '♋ Qisqichbaqa', 'arslon': '♌ Arslon', 'sunbula': '♍ Sunbula',
        'tarozi': '♎ Tarozi', 'chayon': '♏ Chayon', 'oqotar': "♐ O'qotar",
        'tog_echkisi': "♑ Tog' echkisi", 'qovga': "♒ Qovg'a", 'baliq': '♓ Baliq',
    },
    'ru': {
        'qoy': '♈ Овен', 'buzoq': '♉ Телец', 'egizak': '♊ Близнецы',
        'qisqichbaqa': '♋ Рак', 'arslon': '♌ Лев', 'sunbula': '♍ Дева',
        'tarozi': '♎ Весы', 'chayon': '♏ Скорпион', 'oqotar': '♐ Стрелец',
        'tog_echkisi': '♑ Козерог', 'qovga': '♒ Водолей', 'baliq': '♓ Рыбы',
    },
    'kk': {
        'qoy': '♈ Қой', 'buzoq': '♉ Бұқа', 'egizak': '♊ Егіздер',
        'qisqichbaqa': '♋ Шаян', 'arslon': '♌ Арыстан', 'sunbula': '♍ Бикеш',
        'tarozi': '♎ Таразы', 'chayon': '♏ Скорпион', 'oqotar': '♐ Мерген',
        'tog_echkisi': '♑ Ешкімүйіз', 'qovga': '♒ Құнан', 'baliq': '♓ Балық',
    },
    'en': {
        'qoy': '♈ Aries', 'buzoq': '♉ Taurus', 'egizak': '♊ Gemini',
        'qisqichbaqa': '♋ Cancer', 'arslon': '♌ Leo', 'sunbula': '♍ Virgo',
        'tarozi': '♎ Libra', 'chayon': '♏ Scorpio', 'oqotar': '♐ Sagittarius',
        'tog_echkisi': '♑ Capricorn', 'qovga': '♒ Aquarius', 'baliq': '♓ Pisces',
    },
}

# Burj moslik foizi — SI asosida
ZODIAC_COMPAT_PERCENT = {
    ('qoy', 'arslon'): 98, ('arslon', 'qoy'): 98,
    ('qoy', 'egizak'): 91, ('egizak', 'qoy'): 91,
    ('qoy', 'oqotar'): 95, ('oqotar', 'qoy'): 95,
    ('qoy', 'tarozi'): 78, ('tarozi', 'qoy'): 78,
    ('qoy', 'qovga'): 82, ('qovga', 'qoy'): 82,
    ('qoy', 'qoy'): 72,
    ('buzoq', 'sunbula'): 98, ('sunbula', 'buzoq'): 98,
    ('buzoq', 'qisqichbaqa'): 95, ('qisqichbaqa', 'buzoq'): 95,
    ('buzoq', 'tog_echkisi'): 92, ('tog_echkisi', 'buzoq'): 92,
    ('buzoq', 'baliq'): 85, ('baliq', 'buzoq'): 85,
    ('buzoq', 'buzoq'): 70,
    ('egizak', 'tarozi'): 97, ('tarozi', 'egizak'): 97,
    ('egizak', 'qovga'): 93, ('qovga', 'egizak'): 93,
    ('egizak', 'arslon'): 88, ('arslon', 'egizak'): 88,
    ('egizak', 'egizak'): 68,
    ('qisqichbaqa', 'chayon'): 98, ('chayon', 'qisqichbaqa'): 98,
    ('qisqichbaqa', 'baliq'): 96, ('baliq', 'qisqichbaqa'): 96,
    ('qisqichbaqa', 'sunbula'): 80, ('sunbula', 'qisqichbaqa'): 80,
    ('qisqichbaqa', 'qisqichbaqa'): 73,
    ('arslon', 'oqotar'): 96, ('oqotar', 'arslon'): 96,
    ('arslon', 'tarozi'): 85, ('tarozi', 'arslon'): 85,
    ('arslon', 'arslon'): 65,
    ('sunbula', 'tog_echkisi'): 97, ('tog_echkisi', 'sunbula'): 97,
    ('sunbula', 'chayon'): 88, ('chayon', 'sunbula'): 88,
    ('sunbula', 'sunbula'): 71,
    ('tarozi', 'qovga'): 95, ('qovga', 'tarozi'): 95,
    ('tarozi', 'tarozi'): 69,
    ('chayon', 'baliq'): 97, ('baliq', 'chayon'): 97,
    ('chayon', 'tog_echkisi'): 84, ('tog_echkisi', 'chayon'): 84,
    ('chayon', 'chayon'): 74,
    ('oqotar', 'qovga'): 90, ('qovga', 'oqotar'): 90,
    ('oqotar', 'oqotar'): 67,
    ('tog_echkisi', 'baliq'): 86, ('baliq', 'tog_echkisi'): 86,
    ('tog_echkisi', 'tog_echkisi'): 72,
    ('qovga', 'qovga'): 66,
    ('baliq', 'baliq'): 75,
}

def zodiac_compat_percent(key1, key2):
    """Ikki burj o'rtasidagi moslik foizini qaytaradi."""
    if not key1 or not key2:
        return None
    pct = ZODIAC_COMPAT_PERCENT.get((key1, key2)) or ZODIAC_COMPAT_PERCENT.get((key2, key1))
    return pct if pct else 50  # mos kelmasa 50%


# Burj moslik foizini tushunarli darajaga (emoji + so'z) aylantirish
ZODIAC_COMPAT_TIERS = (
    (90, 'excellent', '🔥'),
    (80, 'good', '💚'),
    (70, 'average', '🙂'),
    (0,  'difficult', '⚡'),
)

ZODIAC_COMPAT_TIER_LABELS = {
    'uz':  {'excellent': "Ajoyib moslik",       'good': "Yaxshi moslik",       'average': "O'rtacha moslik",   'difficult': "Murakkab moslik"},
    'ru':  {'excellent': "Отличная совместимость", 'good': "Хорошая совместимость", 'average': "Средняя совместимость", 'difficult': "Сложная совместимость"},
    'kk':  {'excellent': "Тамаша сәйкестік",     'good': "Жақсы сәйкестік",      'average': "Орташа сәйкестік",   'difficult': "Қиын сәйкестік"},
    'ky':  {'excellent': "Мыкты шайкештик",      'good': "Жакшы шайкештик",      'average': "Орточо шайкештик",   'difficult': "Кыйын шайкештик"},
    'kaa': {'excellent': "Ajayıp sáykeslik",     'good': "Jaqsı sáykeslik",      'average': "Ortasha sáykeslik",  'difficult': "Qıyın sáykeslik"},
    'tg':  {'excellent': "Мувофиқати аъло",      'good': "Мувофиқати хуб",       'average': "Мувофиқати миёна",   'difficult': "Мувофиқати душвор"},
    'en':  {'excellent': "Excellent match",      'good': "Good match",           'average': "Average match",      'difficult': "Difficult match"},
}


def get_zodiac_compat_tier(pct):
    """Foizga qarab daraja kaliti va emojisini qaytaradi: (tier_key, emoji)."""
    if pct is None:
        return None, ''
    for threshold, tier_key, emoji in ZODIAC_COMPAT_TIERS:
        if pct >= threshold:
            return tier_key, emoji
    return 'difficult', '⚡'


def get_zodiac_compat_tier_label(pct, lang='uz'):
    """Foizga mos tushunarli so'zni (masalan, 'Yaxshi moslik') qaytaradi."""
    tier_key, emoji = get_zodiac_compat_tier(pct)
    if tier_key is None:
        return '', ''
    labels = ZODIAC_COMPAT_TIER_LABELS.get(lang, ZODIAC_COMPAT_TIER_LABELS['uz'])
    return labels.get(tier_key, ''), emoji


def get_zodiac_display(zodiac_raw, lang='uz'):
    """Burj nomini joriy tilda ko'rsatadi."""
    key = normalize_zodiac_key(zodiac_raw)
    if not key:
        return zodiac_raw or ''
    display = ZODIAC_DISPLAY.get(lang, ZODIAC_DISPLAY['uz'])
    return display.get(key, zodiac_raw or '')


def translate_interest(key, lang='uz'):
    """Interest key ni ko'rsatiladigan nomga aylantiradi."""
    labels = INTERESTS_LABELS.get(lang) or INTERESTS_LABELS.get('uz', {})
    return labels.get(key, key)


def translate_goal(key, lang='uz'):
    labels = GOALS_LABELS.get(lang) or GOALS_LABELS.get('uz', {})
    return labels.get(key, key)


def escape_md(text):
    """Markdown V1 uchun maxsus belgilarni escape qilish."""
    if not text:
        return ''
    for ch in ('*', '_', '`', '['):
        text = str(text).replace(ch, '\\' + ch)
    return text


@dp.update.outer_middleware()
async def ban_guard_middleware(handler, event, data):
    """Banlangan foydalanuvchi botdan MUTLAQO foydalana olmasligi uchun barcha
    update turlarini (shu jumladan /start) ushbu middleware'dan o'tkazamiz."""
    telegram_user = None
    if event.message:
        telegram_user = event.message.from_user
    elif event.callback_query:
        telegram_user = event.callback_query.from_user

    if telegram_user:
        try:
            ban_info, is_banned = await check_user_ban(telegram_user.id)
        except Exception:
            ban_info, is_banned = None, False

        if is_banned:
            try:
                lang = await get_user_lang(telegram_user.id)
                text = t(lang, 'ban_message',
                         reason=ban_info.get('ban_reason'),
                         until=ban_info.get('banned_until'))
                if event.message:
                    await event.message.answer(text)
                elif event.callback_query:
                    await event.callback_query.answer(text, show_alert=True)
            except Exception:
                pass
            return  # handler ishga tushirilmaydi

    return await handler(event, data)


def _normalize_base64(photo_base64: str) -> str:
    if photo_base64 and "," in photo_base64 and photo_base64.startswith("data:"):
        return photo_base64.split(",", 1)[1]
    return photo_base64


def watermark_image_base64(photo_base64: str, watermark_text: str) -> str:
    """
    Rasm ustiga diagonal, takrorlanuvchi, shaffof watermark (masalan @username yoki ID)
    qo'shadi. Watermark rasmning piksellariga "kuydiriladi" - shuning uchun uni
    skrinshot olib tashlab bo'lmaydi va frontendda hech qanday usul bilan olib
    tashlanmaydi. Bu skrinshot/screen-record qilingan taqdirda ham, rasm kimning
    ekanini va kimga ko'rsatilganini izlash imkonini beradi.
    """
    try:
        clean_b64 = _normalize_base64(photo_base64)
        raw = base64.b64decode(clean_b64)
        img = Image.open(io.BytesIO(raw)).convert("RGBA")

        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        font_size = max(14, img.width // 22)
        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size
            )
        except Exception:
            font = ImageFont.load_default()

        text = f" {watermark_text} "
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        step_x = text_w + 60
        step_y = text_h + 60

        for y in range(-step_y, img.height + step_y, step_y):
            offset = 0 if (y // step_y) % 2 == 0 else step_x // 2
            for x in range(-step_x, img.width + step_x, step_x):
                draw.text((x + offset, y), text, font=font, fill=(255, 255, 255, 90))

        rotated = overlay.rotate(30, expand=False)
        watermarked = Image.alpha_composite(img, rotated)
        watermarked = watermarked.convert("RGB")

        buf = io.BytesIO()
        watermarked.save(buf, format="JPEG", quality=88)
        encoded = base64.b64encode(buf.getvalue()).decode("utf-8")
        return f"data:image/jpeg;base64,{encoded}"
    except Exception as exc:
        logger.error("Watermark qo'yishda xatolik: %s", exc, exc_info=True)
        # Watermark qo'yib bo'lmasa ham, original rasmni saqlashda davom etamiz
        # (prefiks yo'q bo'lsa qo'shib qo'yamiz, bo'lmasa <img> ishlamaydi)
        if photo_base64 and not photo_base64.startswith("data:"):
            return f"data:image/jpeg;base64,{_normalize_base64(photo_base64)}"
        return photo_base64


async def moderate_image_base64(photo_base64: str):
    """
    OpenAI Moderation API (omni-moderation-latest) orqali rasmni tekshiradi.
    Pornografiya yoki qurol-yarog' aniqlansa -> (False, sabab) qaytaradi.
    Tekshirib bo'lmasa (API xato, key yo'q) -> xavfsizlik uchun (False, 'check_failed').
    Rasm toza bo'lsa -> (True, None).
    """
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY sozlanmagan - rasm moderatsiyasi o'tkazib bo'lmaydi")
        return False, "moderation_not_configured"

    clean_b64 = _normalize_base64(photo_base64)
    if not clean_b64:
        return False, "invalid_image"

    data_url = f"data:image/jpeg;base64,{clean_b64}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/moderations",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "omni-moderation-latest",
                    "input": [
                        {"type": "image_url", "image_url": {"url": data_url}}
                    ],
                },
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.error("OpenAI moderation API xatolik: %s %s", resp.status, body)
                    return False, "moderation_api_error"
                result = await resp.json()
    except Exception as exc:
        logger.error("OpenAI moderation so'rovida xatolik: %s", exc, exc_info=True)
        return False, "moderation_api_error"

    try:
        item = result["results"][0]
        flagged = item.get("flagged", False)
        categories = item.get("categories", {}) or {}

        # Pornografiya / jinsiy kontent
        is_sexual = bool(categories.get("sexual")) or bool(categories.get("sexual/minors"))
        # Qurol-yarog' (zo'ravonlik bilan bog'liq kategoriya)
        is_weapon = bool(categories.get("violence")) or bool(categories.get("violence/graphic"))

        if is_sexual:
            return False, "sexual_content"
        if is_weapon:
            return False, "weapon_content"
        if flagged:
            return False, "policy_violation"

        return True, None
    except Exception as exc:
        logger.error("Moderation javobini tahlil qilishda xatolik: %s", exc, exc_info=True)
        return False, "moderation_parse_error"


# Shikoyat toifalari: kategoriya kaliti -> (moderation kategoriyalari ro'yxati, og'ir-yengilligi)
# severe=True bo'lgan toifalar birinchi tasdiqlangan holatdayoq eng qattiq (doimiy) chorani oladi.
REPORT_CATEGORIES = {
    'porn': {'moderation_keys': ['sexual', 'sexual/minors'], 'severe': False},
    'minor': {'moderation_keys': ['sexual/minors'], 'severe': True},
    'violence': {'moderation_keys': ['violence', 'violence/graphic'], 'severe': False},
    'drugs': {'moderation_keys': [], 'severe': False},   # OpenAI moderation'da alohida narkotik toifasi yo'q -> GPT tekshiruviga tayanamiz
    'fraud': {'moderation_keys': [], 'severe': False},
    'other': {'moderation_keys': [], 'severe': False},
}


async def _gpt_classify_report(category: str, texts: list, has_image: bool):
    """OpenAI Moderation API kontekstga bog'liq holatlarni (narkotik tarqatish,
    tahdid, firibgarlik kabi mahalliy so'zlashuv/kod so'zlarda bo'lishi mumkin
    bo'lgan holatlarni) to'liq qamrab olmasligi mumkin. Shu sabab qo'shimcha
    bosqich sifatida GPT'dan qat'iy JSON formatida xulosa so'raymiz."""
    if not OPENAI_API_KEY:
        return None
    if not texts and not has_image:
        return None

    joined_text = "\n".join(f"- {t}" for t in texts[-20:]) if texts else "(matn yo'q)"
    prompt = (
        "Sen ushbu tanishuv ilovasida moderatsiya yordamchisisan. Foydalanuvchi boshqa "
        f"foydalanuvchini quyidagi toifada shikoyat qildi: '{category}'.\n"
        "Quyida shu foydalanuvchining so'nggi xabarlari (o'zbek/rus tilida, "
        "shevaga xos so'zlar yoki kod so'zlar bo'lishi mumkin):\n"
        f"{joined_text}\n\n"
        "Ushbu kontent haqiqatan ham ko'rsatilgan toifaga (pornografiya, narkotik "
        "tarqatish/sotish, zo'ravonlik/tahdid, firibgarlik) mos keladimi, tahlil qil. "
        "FAQAT quyidagi formatda JSON qaytar, boshqa hech qanday matn yozma:\n"
        '{"violation": true yoki false, "confidence": 0-1 oralig\'ida son, "explanation": "qisqa izoh"}'
    )
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0,
                    "max_tokens": 200,
                },
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.error("GPT report classify xatolik: %s %s", resp.status, body)
                    return None
                result = await resp.json()
        content = result["choices"][0]["message"]["content"].strip()
        content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:].strip()
        return json.loads(content)
    except Exception as exc:
        logger.error("GPT report classify parse xatolik: %s", exc, exc_info=True)
        return None


async def moderate_report_content(category: str, texts: list, image_base64: str = None):
    """Shikoyat qilingan kontentni (matn + ixtiyoriy rasm) tekshiradi.
    Qaytaradi: (confirmed: bool, verdict: dict) - verdict audit uchun saqlanadi."""
    cat_conf = REPORT_CATEGORIES.get(category, REPORT_CATEGORIES['other'])
    verdict = {'category': category, 'moderation': None, 'gpt': None}
    confirmed = False

    # 1-bosqich: OpenAI Moderation API (rasm va matn uchun)
    if OPENAI_API_KEY:
        inputs = []
        for txt in (texts or [])[-20:]:
            if txt:
                inputs.append({"type": "text", "text": txt[:2000]})
        if image_base64:
            clean_b64 = _normalize_base64(image_base64)
            if clean_b64:
                inputs.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{clean_b64}"}})

        if inputs:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        "https://api.openai.com/v1/moderations",
                        headers={
                            "Authorization": f"Bearer {OPENAI_API_KEY}",
                            "Content-Type": "application/json",
                        },
                        json={"model": "omni-moderation-latest", "input": inputs},
                        timeout=aiohttp.ClientTimeout(total=20),
                    ) as resp:
                        if resp.status == 200:
                            mod_result = await resp.json()
                            verdict['moderation'] = mod_result
                            for item in mod_result.get('results', []):
                                cats = item.get('categories', {}) or {}
                                if item.get('flagged') and cat_conf['moderation_keys']:
                                    if any(cats.get(k) for k in cat_conf['moderation_keys']):
                                        confirmed = True
                        else:
                            logger.error("Moderation API xatolik (report): %s", resp.status)
            except Exception as exc:
                logger.error("Moderation so'rovida xatolik (report): %s", exc, exc_info=True)

    # 2-bosqich: kontekstga bog'liq toifalar (narkotik, firibgarlik, zo'ravonlik) uchun GPT tahlili
    if not confirmed:
        gpt_verdict = await _gpt_classify_report(category, texts or [], bool(image_base64))
        verdict['gpt'] = gpt_verdict
        if gpt_verdict and gpt_verdict.get('violation') and float(gpt_verdict.get('confidence', 0)) >= 0.6:
            confirmed = True

    return confirmed, verdict


async def process_report_background(report_id, reporter_id, reported_id, category, texts, image_base64):
    """Shikoyatni fon rejimida tekshiradi va tasdiqlansa progressiv ban qo'llaydi."""
    try:
        confirmed, verdict = await moderate_report_content(category, texts, image_base64)
        status = 'confirmed' if confirmed else 'rejected'
        await db.set_report_result(report_id, status, verdict)

        if confirmed:
            cat_conf = REPORT_CATEGORIES.get(category, REPORT_CATEGORIES['other'])
            ban_info = await db.register_violation_and_ban(reported_id, category, severe=cat_conf['severe'])
            try:
                lang = await get_user_lang(reported_id)
                until_str = ban_info['banned_until']
                await bot.send_message(
                    reported_id,
                    t(lang, 'ban_message', reason=ban_info['ban_reason'], until=until_str)
                )
            except Exception:
                pass
            logger.info(
                "Report #%s confirmed: user %s banned for %s days (category=%s)",
                report_id, reported_id, ban_info['days'], category
            )
    except Exception as exc:
        logger.error("Report tekshiruvida xatolik (report_id=%s): %s", report_id, exc, exc_info=True)


async def check_user_ban(telegram_id):
    """Foydalanuvchi banlanganmi tekshiradi. Ban bo'lsa (dict, True), aks holda (None, False)."""
    try:
        ban_info = await db.get_ban_info(telegram_id)
        if ban_info.get('is_banned'):
            return ban_info, True
        return None, False
    except Exception:
        return None, False


def get_photo_input(user):
    photo_file_id = user.get("photo_file_id")
    if photo_file_id:
        return photo_file_id

    photo_base64 = user.get("photo_base64")
    if not photo_base64:
        return None

    try:
        photo_base64 = _normalize_base64(photo_base64)
        image_bytes = base64.b64decode(photo_base64)
        return BufferedInputFile(image_bytes, filename="profile_photo.jpg")
    except Exception as exc:
        logger.warning("Photo decode error: %s", exc)
        return None


async def get_user_lang(user_id):
    """Foydalanuvchi tilini olish"""
    lang = await db.get_user_language(user_id)
    return lang if lang in T else 'uz'


async def language_keyboard():
    """Til tanlash klaviaturasi"""
    builder = InlineKeyboardBuilder()
    for code, info in SUPPORTED_LANGUAGES.items():
        builder.row(
            InlineKeyboardButton(
                text=f"{info['flag']} {info['name']}",
                callback_data=f"set_lang:{code}"
            )
        )
    return builder.as_markup()


def _is_profile_complete(user: dict) -> bool:
    """Basic completeness check for a user's profile.
    Require fullname, age and gender to be present. Adjust fields if needed.
    """
    if not user:
        return False
    if not user.get('full_name'):
        return False
    if not user.get('age'):
        return False
    if not user.get('gender'):
        return False
    return True


def _validate_profile_payload(profile: dict):
    """Anketa saqlashdan oldin serverda tekshirish.
    Frontend validatsiyasi bo'lsa ham, to'g'ridan-to'g'ri API'ga yuborilgan
    yoki nosoz so'rovlar natijasida bazaga bo'sh/"null" qiymatli anketalar
    saqlanib qolmasligi uchun serverda ham majburiy tekshiruv qilinadi.
    Returns (is_valid: bool, error_message: str | None)
    """
    if not isinstance(profile, dict):
        return False, "Profile data is not valid."

    full_name = (profile.get('full_name') or '').strip() if isinstance(profile.get('full_name'), str) else profile.get('full_name')
    if not full_name:
        return False, "full_name is required."

    age = profile.get('age')
    try:
        age = int(age)
    except (TypeError, ValueError):
        return False, "age is required and must be a number."
    if age < 16 or age > 80:
        return False, "age must be between 16 and 80."

    gender = db.normalize_gender(profile.get('gender'))
    if not gender:
        return False, "gender is required."

    city = (profile.get('city') or '').strip() if isinstance(profile.get('city'), str) else profile.get('city')
    if not city:
        return False, "city is required."

    spoken_language = profile.get('spoken_language')
    if not spoken_language:
        return False, "spoken_language is required."

    return True, None


async def get_or_create_group_invite_link(telegram_id):
    """
    Har bir foydalanuvchi uchun shaxsiy (unikal) guruh taklifnoma havolasini
    qaytaradi. Bu — "guruhga qo'shishda mening nomimdan hisoblanmayapti"
    muammosining yechimi: agar hamma bitta umumiy GROUP_INVITE_LINK'ni
    ulashsa, Telegram kim orqali qo'shilganini bilolmaydi. Shu sabab har bir
    foydalanuvchiga bot orqali maxsus havola yaratiladi (nomi = telegram_id),
    va shu havola bazada shu foydalanuvchiga bog'lanadi.
    """
    if not GROUP_CHAT_ID:
        return GROUP_INVITE_LINK if GROUP_INVITE_LINK else f"https://t.me/{(await bot.me()).username}"

    existing = await db.get_user_invite_link(telegram_id)
    if existing:
        return existing

    try:
        link_obj = await bot.create_chat_invite_link(
            chat_id=GROUP_CHAT_ID,
            name=str(telegram_id)
        )
        await db.save_user_invite_link(telegram_id, link_obj.invite_link)
        return link_obj.invite_link
    except Exception as e:
        logger.error(f"Shaxsiy guruh havolasini yaratishda xatolik: {e}")
        # Bot guruhda admin bo'lmasa yoki huquq bo'lmasa - statik havolaga qaytamiz
        return GROUP_INVITE_LINK if GROUP_INVITE_LINK else f"https://t.me/{(await bot.me()).username}"


async def main_menu_keyboard(lang='uz', telegram_id=None):
    """Asosiy menyu klaviaturasi"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=t(lang, 'btn_webapp'), web_app=WebAppInfo(url=f"{WEBAPP_URL}/index.html")))
    builder.row(InlineKeyboardButton(text=t(lang, 'btn_my_profile'), callback_data="show_profile"))
    builder.row(InlineKeyboardButton(text=t(lang, 'btn_search'), callback_data="start_search"))
    builder.row(InlineKeyboardButton(text=t(lang, 'btn_change_lang'), callback_data="change_language"))

    # Guruhga qo'shilish tugmasi faqat erkak foydalanuvchilar uchun chiqadi
    is_male = await db.is_male_user(telegram_id) if telegram_id else False
    if is_male:
        group_link = await get_or_create_group_invite_link(telegram_id) if telegram_id else (GROUP_INVITE_LINK if GROUP_INVITE_LINK else f"https://t.me/{(await bot.me()).username}")
        builder.row(InlineKeyboardButton(text=t(lang, 'btn_group'), url=group_link))

    return builder.as_markup()


# ========== REGIONS.JSON DAN DINAMIK YUKLASH ==========
_regions_data = None

def _load_regions():
    """regions.json faylni bir marta yuklab kesh qiladi."""
    global _regions_data
    if _regions_data is not None:
        return _regions_data
    regions_path = os.path.join(os.path.dirname(__file__), 'regions.json')
    try:
        with open(regions_path, encoding='utf-8') as f:
            _regions_data = json.load(f)
        logger.info("regions.json muvaffaqiyatli yuklandi.")
    except Exception as e:
        logger.error(f"regions.json yuklanmadi: {e}")
        _regions_data = {}
    return _regions_data

def _build_region_rules_from_json():
    """
    regions.json → get_city_region uchun rules ro'yxatini yaratadi.
    uzbekCitiesML barcha tillardagi viloyat → tumanlar ma'lumotini birlashtiradi.
    """
    data = _load_regions()
    uzbek_ml = data.get('uzbekCitiesML', {})

    # viloyat_nomi (uz) → barcha tillardagi tuman/shahar nomlari
    region_terms: dict[str, list[str]] = {}

    # uzbekCitiesML['uz'] → canonical viloyat nomlar
    uz_data = uzbek_ml.get('uz', {})
    for region_uz, districts in uz_data.items():
        key = region_uz  # canonical nom (uz tilida)
        if key not in region_terms:
            region_terms[key] = []
        # uz tumanlarini qo'shamiz
        for d in districts:
            region_terms[key].append(d.lower())
        # viloyatning o'zini ham qo'shamiz
        region_terms[key].append(region_uz.lower())

    # Boshqa tillardagi nomlarni ham qo'shamiz (positional moslik orqali)
    uz_regions_list = list(uz_data.keys())
    for lang, lang_data in uzbek_ml.items():
        if lang == 'uz':
            continue
        lang_regions_list = list(lang_data.keys())
        for i, (region_lang, districts_lang) in enumerate(lang_data.items()):
            # Positional mos kelish: i-chi viloyat → uz_regions_list[i]
            if i < len(uz_regions_list):
                canonical = uz_regions_list[i]
            else:
                canonical = region_lang  # fallback
            if canonical not in region_terms:
                region_terms[canonical] = []
            region_terms[canonical].append(region_lang.lower())
            for d in districts_lang:
                region_terms[canonical].append(d.lower())

    # rules formatiga o'tkazamiz
    rules = [{'region': region, 'terms': list(set(terms))}
             for region, terms in region_terms.items()]
    return rules


_city_region_rules = None

def _get_city_region_rules():
    global _city_region_rules
    if _city_region_rules is None:
        _city_region_rules = _build_region_rules_from_json()
    return _city_region_rules


def get_city_region(city=''):
    # Ko'p tilli shahar/tuman → viloyat mos kelishi
    # Barcha tillardagi nomlar regions.json dan o'qiladi
    value = str(city or '').lower().strip()
    
    # Toshkent shahri — alohida viloyat emas
    toshkent_city_terms = (
        'toshkent shahri', 'tashkent city', 'город ташкент',
        'ташкент қаласы', 'шаҳри тошканд', 'ташкент шаары', 'tashkent qalasy'
    )
    if value in toshkent_city_terms:
        return ''

    rules = _get_city_region_rules() + [
        # ========== QOZOG'ISTON VILOYATLARI (regions.json da yo'q) ==========
        {'region': 'Astana shahri', 'terms': ['astana', 'nura', 'yesil', 'sariorqa', 'bayqoʻngʻir', 'almaty tumani', 'астана', 'нуринский', 'есильский', 'сарыаркинский', 'байконурский', 'алматинский']},
        {'region': 'Olmati shahri', 'terms': ['olmati', 'almaty', 'alatau', 'bostandiq', 'jetisu', 'medeu', 'navoiy tumani', 'turgʻisun', 'olmali', 'алматы', 'алатауский', 'бостандык', 'жетісу', 'медеу', 'наурызбай', 'турксиб', 'алмалинский']},
        {'region': 'Chimkent shahri', 'terms': ['chimkent', 'shymkent', 'qaratau', 'turon', 'yassaviy', 'al-farobiy', 'шымкент', 'чымкент', 'караатау', 'туран', 'яссави', 'аль-фарабийский', 'абайский', 'енбекшинский']},
        {'region': 'Abay viloyati', 'terms': ['abay', 'semey', 'kurchatov', 'ayagoz', 'besqoragay', 'borodulixa', 'jarma', 'kokpekti', 'urjar', 'oqsuat', 'абай', 'семей', 'курчатов', 'аягоз', 'бескарагай', 'бородулиха', 'жарма', 'кокпекти', 'урджар', 'аксуат']},
        {'region': 'Oqmo\'la viloyati', 'terms': ['aqmola', 'aqmo\'la', 'kokshetau', 'kokchatov', 'stepnogorsk', 'akkol', 'arshali', 'atbasar', 'birjan sal', 'bulandy', 'burabay', 'egindykol', 'enbekshilder', 'ereymentau', 'jaqsi', 'jarqayin', 'qorgaljin', 'sandaqtau', 'shotandi', 'selonograd', 'tselinograd', 'акмола', 'акмолинская', 'кокшетау', 'степногорск', 'акколь', 'аршалы', 'атбасар', 'буланды', 'бурабай', 'егиндыколь', 'енбекшилдер', 'ерейментау', 'есіль', 'жақсы', 'жарқаин', 'коргалжын', 'сандыктау', 'шортанды', 'целиноград']},
        {'region': 'Oqto\'ba viloyati', 'terms': ['aktobe', 'aqto\'ba', 'alga', 'bayganin', 'uyil', 'irgiz', 'martuk', 'mugalzhar', 'temir', 'xromtau', 'xobda', 'shalkar', 'qargali', 'актобе', 'актюбинская', 'алга', 'байганин', 'уил', 'иргиз', 'мартук', 'мугалжар', 'темир', 'хромтау', 'хобда', 'шалкар', 'каргали']},
        {'region': 'Olmati viloyati', 'terms': ['almaty region', 'olmati viloyati', 'qonayev', 'konaev', 'balxash', 'enbekshiqozoq', 'ili', 'qarasay', 'kelgen', 'rayimbek', 'talgar', 'uygur', 'jambul tumani', 'oqsu', 'алматинская', 'алматы облысы', 'конаев', 'балхаш', 'енбекшиказах', 'или', 'карасай', 'кеген', 'райымбек', 'талгар', 'уйгур', 'жамбыл', 'аксу']},
        {'region': 'Atirau viloyati', 'terms': ['atyrau', 'atirau', 'inder', 'isatay', 'qizilqoga', 'qurmangazi', 'maqat', 'maxambet', 'jilioy', 'атырау', 'атырауская', 'индер', 'исатай', 'кызылкога', 'курмангазы', 'макат', 'махамбет', 'жылыой']},
        {'region': 'G\'arbiy Qozog\'iston viloyati', 'terms': ['west kazakhstan', 'g\'arbiy qozog\'iston', 'oral', 'uralsk', 'aqjoyiq', 'boreli', 'janagala', 'janibek', 'bayterek', 'kaztalov', 'qaratobe', 'taqqala', 'tasqala', 'terekti', 'shingirlau', 'bokey ordasy', 'западно-казахстанская', 'западный казахстан', 'уральск', 'орал', 'акжаик', 'бурлин', 'жангала', 'жанибек', 'байтерек', 'казталов', 'каратобе', 'таскала', 'теректи', 'шингирлау', 'бокейординский']},
        {'region': 'Jambul viloyati', 'terms': ['jambyl', 'jambul', 'taraz', 'bayzaq', 'qorday', 'merki', 'moynqum', 'sarysu', 'talas', 'turar rysqulov', 'shu', 'juvali', 'жамбыл', 'жамбылская', 'тараз', 'байзак', 'кордай', 'мерке', 'мойынкум', 'сарысу', 'талас', 'турар рыскулов', 'шу', 'жуалы']},
        {'region': 'Jetisu viloyati', 'terms': ['zhetysu', 'jetisu', 'taldiqorgan', 'taldiforgon', 'tekeli', 'alakol', 'eskeldi', 'qaratal', 'kerbuloq', 'koksu', 'panfilov', 'sarqand', 'жетісу', 'жетисуская', 'талдыкорган', 'текелі', 'алаколь', 'ескелді', 'каратал', 'кербулак', 'коксу', 'панфилов', 'сарканд']},
        {'region': 'Qarag\'andi viloyati', 'terms': ['karaganda', 'qaragandi', 'balxash', 'temirtau', 'saran', 'shaxtinsk', 'abay tumani', 'aktogay', 'buqar jirau', 'qarqarali', 'nura tumani', 'osakarov', 'shet', 'караганда', 'карагандинская', 'балхаш', 'темиртау', 'сарань', 'шахтинск', 'актогай', 'бухар-жырау', 'каркаралинский', 'нура', 'осакаров', 'шет']},
        {'region': 'Qostanay viloyati', 'terms': ['kostanay', 'qostanay', 'arkalyk', 'rudniy', 'lisakovsk', 'alvinsar', 'amangeldi', 'avliyo kol', 'denisov', 'jangeldi', 'jitiqora', 'qamistu', 'qorabaliq', 'qorasu', 'mendigara', 'navruzim', 'suvliqol', 'uzunkol', 'fedorov', 'костанай', 'костанайская', 'аркалык', 'рудный', 'лисаковск', 'алтынсарин', 'амангельды', 'аулиеколь', 'денисов', 'джангельды', 'житикара', 'камысты', 'карабалык', 'карасу', 'мендыкара', 'наурзум', 'сарыколь', 'узунколь', 'федоров']},
        {'region': 'Qizilo\'rda viloyati', 'terms': ['kyzylorda', 'qizilorada', 'baykonur', 'aral', 'qazali', 'qarmaqshi', 'jalagash', 'sirdaryo tumani', 'shiyli', 'janaqorgan', 'кызылорда', 'кызылординская', 'байконур', 'аральский', 'казалинский', 'кармакшинский', 'жалагашский', 'сырдарьинский', 'шиелийский', 'жанакурганский']},
        {'region': 'Mangistau viloyati', 'terms': ['mangystau', 'mangistau', 'aqtau', 'janaorzen', 'beyneu', 'qaraqia', 'munaily', 'tupqaragan', 'мангистау', 'мангыстауская', 'актау', 'жанаозен', 'бейнеу', 'каракия', 'мунайлы', 'тупкараган']},
        {'region': 'Pavlodar viloyati', 'terms': ['pavlodar', 'yekibastuz', 'oqsu shahri', 'aqquly', 'bayanaul', 'jelezin', 'ertis', 'terenkul', 'may tumani', 'sarqamar', 'sharbaqty', 'uspen', 'павлодар', 'павлодарская', 'экибастуз', 'аксу', 'аккулы', 'баянаул', 'железин', 'иртыш', 'теренколь', 'май', 'самарканд', 'щербактин', 'успен']},
        {'region': 'Shimoliy Qozog\'iston viloyati', 'terms': ['north kazakhstan', 'shimoliy qozogiston', 'petropavl', 'ayirtau', 'aqjar', 'aqqayin', 'gabit musirepov', 'esil tumani', 'magjan jumabayev', 'mamlyut', 'shal aqin', 'tayinsha', 'timiryazev', 'ualixanov', 'qiziljar', 'северо-казахстанская', 'северный казахстан', 'петропавловск', 'айыртауский', 'акжарский', 'аккайынский', 'габита мусрепова', 'магжана жумабаева', 'мамлютский', 'шал акына', 'тайыншинский', 'тимирязев', 'уалиханов', 'кызылжарский']},
        {'region': 'Turkiston viloyati', 'terms': ['turkistan', 'turkestan', 'aris', 'kentau', 'baydibek', 'jetisay', 'qazigurt', 'keles', 'maktaaral', 'ordabasy', 'otrar', 'sayram', 'sariagash', 'sauran', 'sozaq', 'tole bi', 'tyulkubas', 'shardara', 'туркестан', 'туркестанская', 'арыс', 'кентау', 'байдибек', 'жетисай', 'казыгурт', 'келес', 'мактаарал', 'ордабасы', 'отрар', 'сайрам', 'сарыагаш', 'сауран', 'созак', 'толе би', 'тюлькубас', 'шардара']},
        {'region': 'Ulitau viloyati', 'terms': ['ulytau', 'ulitau', 'jezkazgan', 'jezqazg\'on', 'satpayev', 'qarajal', 'janaarqa', 'улытау', 'улытауская', 'жезказган', 'сатпаев', 'каражал', 'жанаарка']},
        {'region': 'Sharqiy Qozog\'iston viloyati', 'terms': ['east kazakhstan', 'sharqiy qozogiston', 'oskemen', 'ust-kamenogorsk', 'ridder', 'altay', 'glubokoye', 'kurshim', 'markakol', 'samarka', 'tarbagatay', 'ulan', 'shemonaixa', 'katonqaragay', 'zaysan', 'восточно-казахстанская', 'восточный казахстан', 'усть-каменогорск', 'өскемен', 'риддер', 'алтай', 'глибокое', 'курчум', 'маркаколь', 'самар', 'тарбагатай', 'улан', 'шемонаиха', 'катон-карагай', 'зайсан']},
    ]

    for item in rules:
        if any(term in value for term in item['terms']):
            return item['region']
    return ''


def format_location_label(city='', lang='uz'):
    """
    Shahar nomini formatlaydi.
    Yangi format: "district||region||country" → faqat shahar va viloyat ko'rsatiladi.
    Eski format: oddiy matn → get_city_region orqali viloyat aniqlanadi.
    """
    city_text = str(city or '').strip()
    if not city_text:
        return 'Joy ko\'rsatilmagan'

    # Yangi "district||region||country" format
    if '||' in city_text:
        parts = [p.strip() for p in city_text.split('||')]
        district = parts[0] if len(parts) > 0 else ''
        region   = parts[1] if len(parts) > 1 else ''
        country  = parts[2] if len(parts) > 2 else ''

        # regions.json dan tarjima qilishga urinib ko'ramiz
        data = _load_regions()
        translated_district = district
        translated_region   = region

        # uzbekCitiesML dan joriy til bo'yicha nom topamiz
        ml = data.get('uzbekCitiesML', {})
        uz_data  = ml.get('uz', {})
        tgt_data = ml.get(lang, {})

        uz_regions_list  = list(uz_data.keys())
        tgt_regions_list = list(tgt_data.keys())

        for i, uz_region in enumerate(uz_regions_list):
            # Viloyat mos kelishini tekshiramiz (ham uz, ham boshqa tillarda)
            region_matches = (
                region.lower() == uz_region.lower() or
                region.lower() in uz_region.lower() or
                uz_region.lower() in region.lower()
            )
            if not region_matches:
                # Boshqa tillardagi viloyat nomini ham tekshiramiz
                for lang_code, lang_data in ml.items():
                    lang_regions = list(lang_data.keys())
                    if i < len(lang_regions):
                        lr = lang_regions[i]
                        if region.lower() == lr.lower() or region.lower() in lr.lower():
                            region_matches = True
                            break

            if region_matches and i < len(tgt_regions_list):
                translated_region = tgt_regions_list[i]
                # Tumanlar/shaharlarni ham tarjima qilamiz
                uz_districts = uz_data.get(uz_region, [])
                tgt_districts = tgt_data.get(tgt_regions_list[i], [])
                for j, d_uz in enumerate(uz_districts):
                    if district.lower() == d_uz.lower() or d_uz.lower() in district.lower():
                        if j < len(tgt_districts):
                            translated_district = tgt_districts[j]
                        break
                    # Boshqa tillardagi mos kelishni ham tekshiramiz
                    for lang_code2, lang_data2 in ml.items():
                        lang_regions2 = list(lang_data2.keys())
                        if i < len(lang_regions2):
                            d_list = lang_data2.get(lang_regions2[i], [])
                            if j < len(d_list) and (district.lower() == d_list[j].lower() or d_list[j].lower() in district.lower()):
                                if j < len(tgt_districts):
                                    translated_district = tgt_districts[j]
                                break
                break

        # Chiroyli ko'rinish: "Shahar • Viloyat" yoki faqat "Viloyat"
        if translated_district and translated_region:
            return f"{translated_district} • {translated_region}"
        elif translated_district:
            return translated_district
        elif translated_region:
            return translated_region
        return district or region or city_text

    # Eski format: oddiy matn
    region = get_city_region(city_text)
    if region and city_text and region.lower() not in city_text.lower():
        return f"{city_text} • {region}"
    return city_text


def spoken_language_display(codes, lang='uz'):
    """Foydalanuvchi tanlagan so'zlashuv til(lar)i kodini bayroq+nom ko'rinishida qaytaradi.
    Endi bir nechta til bo'lishi mumkin (list); eski bitta til (string) bilan ham ishlaydi.
    Nom ko'ruvchi (viewer)ning joriy interfeys tiliga tarjima qilinadi."""
    if not codes:
        return ''
    code_list = codes if isinstance(codes, (list, tuple)) else [codes]
    names = LANGUAGE_NAMES_TRANSLATED.get(lang) or LANGUAGE_NAMES_TRANSLATED['uz']
    parts = []
    for code in code_list:
        if not code:
            continue
        info = SUPPORTED_LANGUAGES.get(code)
        if not info:
            continue
        name = names.get(code, info['name'])
        parts.append(f"{info['flag']} {name}")
    return ', '.join(parts)


def format_user_card(user, lang='uz', searcher_zodiac_key=None):
    gender_icon = "👨" if user.get("gender") == "erkak" else "👩"

    # Burj — tilga mos ko'rsatish
    zodiac_raw = user.get("zodiac") or ''
    zodiac_display = get_zodiac_display(zodiac_raw, lang) if zodiac_raw else t(lang, 'not_specified')

    # Burj moslik foizi — foiz + tushunarli daraja (masalan, "87% — Yaxshi moslik 💚")
    compat_line = ''
    if searcher_zodiac_key and zodiac_raw:
        candidate_key = normalize_zodiac_key(zodiac_raw)
        pct = zodiac_compat_percent(searcher_zodiac_key, candidate_key)
        if pct is not None:
            tier_label, tier_emoji = get_zodiac_compat_tier_label(pct, lang)
            compat_line = f"\n{tier_emoji} {pct}% — {tier_label}"

    # Qiziqishlar — key → chiroyli nom
    interests_raw = (user.get('interests') or [])[:5]
    if interests_raw:
        interests_text = ', '.join(translate_interest(i, lang) for i in interests_raw)
    else:
        interests_text = t(lang, 'not_specified')

    # Maqsad
    goals_raw = (user.get('goals') or [])[:3]
    goals_text = ', '.join(translate_goal(g, lang) for g in goals_raw) if goals_raw else ''

    # Joy
    city_text = escape_md(format_location_label(user.get('city'), lang))

    # Ism va about escape
    full_name = escape_md(user.get('full_name') or 'Anonim')
    about_text = escape_md((user.get('about') or '').strip())

    lines = [
        f"{gender_icon} *{full_name}*",
        f"🎂 {t(lang, 'age')}: {user.get('age', '—')}",
        f"📍 {t(lang, 'city')}: {city_text}",
        f"⭐ {t(lang, 'zodiac')}: {escape_md(zodiac_display)}{compat_line}",
    ]
    if goals_text:
        lines.append(f"🎯 {t(lang, 'goals')}: {escape_md(goals_text)}")
    spoken_lang_display = spoken_language_display(user.get('spoken_language'), lang)
    if spoken_lang_display:
        lines.append(f"🗣 {t(lang, 'spoken_language')}: {escape_md(spoken_lang_display)}")
    if interests_text:
        lines.append(f"✨ {t(lang, 'interests')}: {escape_md(interests_text)}")
    if about_text:
        lines.append('')
        lines.append(f"📝 {t(lang, 'about')}:")
        lines.append(about_text)

    return "\n".join(lines)


async def send_candidate_card(message, user, lang='uz'):
    text = format_user_card(user, lang)
    photo = get_photo_input(user)
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=t(lang, 'btn_like'), callback_data=f"like_{user['telegram_id']}"),
        InlineKeyboardButton(text=t(lang, 'btn_block'), callback_data=f"block_{user['telegram_id']}")
    )
    builder.row(
        InlineKeyboardButton(text=t(lang, 'btn_write'), callback_data=f"write_{user['telegram_id']}")
    )

    if photo:
        await message.answer_photo(
            photo,
            caption=text,
            parse_mode="Markdown",
            reply_markup=builder.as_markup()
        )
    else:
        await message.answer(text, parse_mode="Markdown", reply_markup=builder.as_markup())


async def show_search_candidate(chat, user_id, index, lang='uz'):
    session = search_sessions.get(user_id, {})
    users = session.get('users', [])
    if not users:
        await chat.answer(t(lang, 'no_candidates'))
        return
    if index >= len(users):
        await chat.answer(t(lang, 'all_viewed'))
        search_sessions.pop(user_id, None)
        return

    user = users[index]
    # Qidirayotgan foydalanuvchining burj key-ini olamiz
    searcher_zodiac_key = session.get('searcher_zodiac_key')
    text = format_user_card(user, lang, searcher_zodiac_key=searcher_zodiac_key)
    text += t(lang, 'search_counter', current=index + 1, total=len(users))

    reply_markup = build_candidate_keyboard(lang, user['telegram_id'])

    photo = get_photo_input(user)
    if photo:
        try:
            await chat.answer_photo(
                photo=photo,
                caption=text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Photo send error: {e}")
            await chat.answer(text, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await chat.answer(text, parse_mode='Markdown', reply_markup=reply_markup)


@dp.my_chat_member()
async def handle_bot_join_group(update: types.ChatMemberUpdated):
    if update.new_chat_member.user.id == (await bot.me()).id:
        if update.new_chat_member.status in ['member', 'administrator']:
            logger.info(f"Bot guruhga qo'shildi: {update.chat.id} - {update.chat.title}")
            if GROUP_CHAT_ID and update.chat.id == GROUP_CHAT_ID:
                logger.info("Asosiy guruh topildi!")
        elif update.new_chat_member.status == 'left':
            logger.info(f"Bot guruhdan chiqarildi: {update.chat.id}")


@dp.chat_member()
async def handle_new_group_member(update: types.ChatMemberUpdated):
    if GROUP_CHAT_ID and update.chat.id != GROUP_CHAT_ID:
        return
    new_member = update.new_chat_member
    old_member = update.old_chat_member

    if old_member.status in ['left', 'kicked'] and new_member.status in ['member', 'administrator']:
        invited_id = new_member.user.id
        inviter_id = None

        # 1-ustuvorlik: foydalanuvchi shaxsiy taklifnoma havolasi orqali qo'shilgan bo'lsa,
        # Telegram bu havolani update.invite_link ichida beradi - bu eng ishonchli usul,
        # chunki umumiy/statik havolada kim taklif qilganini Telegram bilmaydi.
        if update.invite_link and update.invite_link.invite_link:
            try:
                inviter_id = await db.get_inviter_by_link(update.invite_link.invite_link)
            except Exception as e:
                logger.error(f"Invite link orqali inviter aniqlashda xatolik: {e}")

        # 2-ustuvorlik: foydalanuvchi guruhga qo'lda (Add Members) qo'shilgan bo'lsa,
        # from_user - qo'shgan odam bo'ladi.
        if not inviter_id and update.from_user and update.from_user.id != invited_id:
            inviter_id = update.from_user.id

        if inviter_id and inviter_id != invited_id:
            # Eslatma: qo'shilgan odam botdan foydalangan/ro'yxatdan o'tgan bo'lishi
            # SHART EMAS - guruhga kirgan istalgan Telegram foydalanuvchisi hisoblanadi.
            # Ism/username Telegramning o'zidan olinadi, botda ro'yxatdan o'tmagan
            # bo'lsa ham Web App'da ko'rinishi uchun saqlab qo'yamiz.
            success, msg = await db.record_group_invite(
                inviter_id, invited_id,
                invited_full_name=new_member.user.full_name,
                invited_username=new_member.user.username
            )
            if success:
                try:
                    inviter_data = await db.get_user(inviter_id)
                    if inviter_data:
                        inviter_lang = await get_user_lang(inviter_id)
                        await bot.send_message(
                            inviter_id,
                            t(inviter_lang, 'group_invite_success',
                              name=new_member.user.first_name, msg=msg),
                            parse_mode="Markdown"
                        )
                except Exception as e:
                    logger.error(f"Inviter notify error: {e}")

        await db.record_group_join(invited_id, inviter_id)


@dp.message(CommandStart())
async def start_handler(message: types.Message):
    args = message.text.split()
    telegram_id = message.from_user.id

    # Referral tekshirish
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referrer_id = int(args[1].replace("ref_", ""))
            if referrer_id != telegram_id:
                pass
        except Exception as e:
            logger.error(f"Referral error: {e}")

    # Foydalanuvchi tilini tekshirish
    lang = await get_user_lang(telegram_id)
    user = await db.get_user(telegram_id)

# Agar til tanlanmagan bo'lsa (faqat yangi foydalanuvchi)
    if not user or not user.get('language'):
        await message.answer(
            t('uz', 'select_language'),
            reply_markup=await language_keyboard()
        )
        return

    # Til tanlangan, lekin anketa hali to'ldirilmagan bo'lsa —
    # faqat salomlashish va anketa to'ldirish tugmasini ko'rsatamiz
    if not _is_profile_complete(user):
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text=t(lang, 'fill_profile'), web_app=WebAppInfo(url=f"{WEBAPP_URL}/index.html")))
        greeting_text = t(lang, 'welcome', name=message.from_user.first_name) + "\n\n" + t(lang, 'please_fill_profile')
        await message.answer(
            greeting_text,
            parse_mode="Markdown",
            reply_markup=builder.as_markup()
        )
        return

    # Til tanlangan va anketa to'ldirilgan bo'lsa, asosiy menyu ko'rsatish
    keyboard = await main_menu_keyboard(lang, telegram_id)
    is_female = await db.is_female_user(telegram_id)
    welcome_text = t(lang, 'welcome', name=message.from_user.first_name)
    if not is_female:
        welcome_text += t(lang, 'limits_info')
    await message.answer(
        welcome_text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )


@dp.callback_query(F.data.startswith("set_lang:"))
async def set_language_callback(callback: types.CallbackQuery):
    lang_code = callback.data.split(":", 1)[1]
    if lang_code not in SUPPORTED_LANGUAGES:
        await callback.answer("❌", show_alert=True)
        return

    await db.set_user_language(callback.from_user.id, lang_code)
    lang_name = SUPPORTED_LANGUAGES[lang_code]['name']

    await callback.answer(t(lang_code, 'language_changed', language_name=lang_name), show_alert=True)

    user = await db.get_user(callback.from_user.id)

    # Anketa hali to'ldirilmagan bo'lsa — faqat salomlashish va
    # anketa to'ldirish tugmasini ko'rsatamiz (asosiy menyu emas)
    if not _is_profile_complete(user):
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text=t(lang_code, 'fill_profile'), web_app=WebAppInfo(url=f"{WEBAPP_URL}/index.html")))
        greeting_text = t(lang_code, 'welcome', name=callback.from_user.first_name) + "\n\n" + t(lang_code, 'please_fill_profile')
        await callback.message.edit_text(
            greeting_text,
            parse_mode="Markdown",
            reply_markup=builder.as_markup()
        )
        return

    # Anketa to'ldirilgan bo'lsa, asosiy menyu ko'rsatish
    keyboard = await main_menu_keyboard(lang_code, callback.from_user.id)
    is_female = await db.is_female_user(callback.from_user.id)
    welcome_text = t(lang_code, 'welcome', name=callback.from_user.first_name)
    if not is_female:
        welcome_text += t(lang_code, 'limits_info')
    await callback.message.edit_text(
        welcome_text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )


@dp.callback_query(F.data == "change_language")
async def change_language_callback(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        t(await get_user_lang(callback.from_user.id), 'select_language'),
        reply_markup=await language_keyboard()
    )


@dp.message(F.text.in_([
    "🌐 Web App", "🌐 Веб-приложение", "🌐 Veb-qosımsha", "🌐 Veb-qo'shımsha", "🌐 Veb-qosımsha", "🌐 Веб-барнома"
]))
async def webapp_button(message: types.Message):
    lang = await get_user_lang(message.from_user.id)
    await message.answer(
        t(lang, 'btn_webapp'),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, 'btn_webapp'), web_app=WebAppInfo(url=f"{WEBAPP_URL}/index.html"))]
        ])
    )


@dp.message(F.text.in_([
    "👤 Mening anketam", "👤 Мой профиль", "👤 Meniń profilim", "👤 Meniń profilim", "👤 Meniń profilim", "👤 Профили ман"
]))
async def my_profile(message: types.Message):
    await show_profile_handler(message)


async def show_profile_handler(message_or_callback):
    if isinstance(message_or_callback, types.CallbackQuery):
        user_id = message_or_callback.from_user.id
        send_func = message_or_callback.message.answer
        send_photo = message_or_callback.message.answer_photo
        await message_or_callback.answer()
    else:
        user_id = message_or_callback.from_user.id
        send_func = message_or_callback.answer
        send_photo = message_or_callback.answer_photo

    lang = await get_user_lang(user_id)
    user = await db.get_user(user_id)
    if not _is_profile_complete(user):
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text=t(lang, 'fill_profile'), web_app=WebAppInfo(url=f"{WEBAPP_URL}/index.html")))
        await send_func(t(lang, 'no_profile'), reply_markup=builder.as_markup())
        return

    gender_icon = "👨" if user["gender"] == "erkak" else "👩"
    goals_raw = user.get("goals") or []
    goals_text = escape_md(", ".join(translate_goal(g, lang) for g in goals_raw) if goals_raw else t(lang, 'not_specified'))
    interests_raw = (user.get("interests") or [])[:5]
    interests_text = escape_md(", ".join(translate_interest(i, lang) for i in interests_raw) if interests_raw else t(lang, 'not_specified'))
    about_text = escape_md((user.get("about") or "").strip() or t(lang, 'not_specified'))
    zodiac_raw = user.get("zodiac") or ''
    zodiac_text = escape_md(get_zodiac_display(zodiac_raw, lang) if zodiac_raw else t(lang, 'not_specified'))
    spoken_lang_text = escape_md(spoken_language_display(user.get('spoken_language'), lang) or t(lang, 'not_specified'))
    full_name = escape_md(user.get('full_name') or 'Anonim')
    city_text = escape_md(format_location_label(user.get('city'), lang))

    limit_status = await db.get_limit_status(user_id)
    if limit_status['unlimited']:
        limit_text = t(lang, 'unlimited_access')
    else:
        limit_text = t(lang, 'daily_limits',
                       likes=limit_status['likes_used'],
                       messages=limit_status['messages_used'],
                       super_likes=limit_status['super_likes_used'])

    text = (
        f"{gender_icon} *{full_name}*\n"
        f"🎂 {t(lang, 'age')}: {user['age']}\n"
        f"📍 {t(lang, 'city')}: {city_text}\n"
        f"⭐ {t(lang, 'zodiac')}: {zodiac_text}\n"
        f"🗣 {t(lang, 'spoken_language')}: {spoken_lang_text}\n"
        f"📝 {t(lang, 'about')}: {about_text}\n"
        f"❤️ {t(lang, 'goals')}: {goals_text}\n"
        f"🎯 {t(lang, 'interests')}: {interests_text}"
        f"{limit_text}"
    )

    photo = get_photo_input(user)
    try:
        if photo:
            await send_photo(photo, caption=text, parse_mode="Markdown")
        else:
            await send_func(text, parse_mode="Markdown")
    except Exception as e:
        # Markdown xato bo'lsa ham (masalan escape qilinmagan kutilmagan belgi),
        # profil ko'rsatilmay qolmasligi va callback "query too old" holatiga
        # tushib ketmasligi uchun parse_mode'siz zaxira urinish qilamiz.
        logger.error(f"show_profile_handler Markdown xatolik, zaxira rejimda yuborilmoqda: {e}")
        try:
            if photo:
                await send_photo(photo, caption=text)
            else:
                await send_func(text)
        except Exception as e2:
            logger.error(f"show_profile_handler zaxira urinish ham muvaffaqiyatsiz: {e2}")


@dp.message(F.text.in_([
    "🔎 Qidirish", "🔎 Поиск", "🔎 Izlew", "🔎 Іздеу", "🔎 Izlew", "🔎 Ҷустуҷӯ"
]))
async def search_button(message: types.Message):
    lang = await get_user_lang(message.from_user.id)
    await start_search(message, lang)


async def start_search(message_or_callback, lang='uz'):
    if isinstance(message_or_callback, types.CallbackQuery):
        await message_or_callback.answer()
        send_func = message_or_callback.message.answer
        user_id = message_or_callback.from_user.id
    else:
        send_func = message_or_callback.answer
        user_id = message_or_callback.from_user.id

    # Require completed profile before allowing search
    user = await db.get_user(user_id)
    if not _is_profile_complete(user):
        # Prompt to fill profile via Web App (use builder for consistent rendering)
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text=t(lang, 'fill_profile'), web_app=WebAppInfo(url=f"{WEBAPP_URL}/index.html")))
        kb = builder.as_markup()
        await send_func(t(lang, 'no_profile'), reply_markup=kb)
        return

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text=t(lang, 'btn_male'), callback_data="search_gender:erkak"))
    builder.add(InlineKeyboardButton(text=t(lang, 'btn_female'), callback_data="search_gender:ayol"))
    builder.add(InlineKeyboardButton(text=t(lang, 'btn_all'), callback_data="search_gender:all"))
    builder.row(InlineKeyboardButton(text=t(lang, 'btn_zodiac_compat'), callback_data="search_zodiac_compat"))
    builder.row(InlineKeyboardButton(text=t(lang, 'btn_back'), callback_data="show_main_menu"))

    await send_func(
        t(lang, 'search_who'),
        reply_markup=builder.as_markup()
    )


@dp.callback_query(F.data == "start_search")
async def start_search_callback(callback: types.CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)
    await start_search(callback, lang)


@dp.callback_query(F.data == "search_zodiac_compat")
async def search_zodiac_compat_callback(callback: types.CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)
    await callback.answer()
    user = await db.get_user(callback.from_user.id)
    if not user or not user.get("zodiac"):
        await callback.message.answer(t(lang, 'no_zodiac'))
        return
    my_zodiac = user.get("zodiac")
    my_key = get_zodiac_key(my_zodiac)
    if not my_key or my_key not in ZODIAC_COMPATIBILITY:
        await callback.message.answer(t(lang, 'zodiac_not_recognized'))
        return

    compat = ZODIAC_COMPATIBILITY[my_key]
    mos_keys = compat["mos"]

    mos_names = []
    for k in mos_keys:
        sign = ZODIAC_SIGNS.get(k)
        if sign:
            mos_names.append(f"{sign[1]} {sign[0]}")

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text=t(lang, 'btn_male'), callback_data="search_zodiac_compat_gender:erkak"))
    builder.add(InlineKeyboardButton(text=t(lang, 'btn_female'), callback_data="search_zodiac_compat_gender:ayol"))
    builder.row(InlineKeyboardButton(text=t(lang, 'btn_all'), callback_data="search_zodiac_compat_gender:all"))
    builder.row(InlineKeyboardButton(text=t(lang, 'btn_back'), callback_data="start_search"))

    sign_info = ZODIAC_SIGNS.get(my_key, (my_zodiac, "⭐"))
    await callback.message.answer(
        t(lang, 'your_zodiac', sign=f"{sign_info[1]} {sign_info[0]}", compat=chr(10).join(mos_names)),
        parse_mode="Markdown",
        reply_markup=builder.as_markup()
    )


@dp.callback_query(F.data.startswith("search_zodiac_compat_gender:"))
async def search_zodiac_compat_gender_callback(callback: types.CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)
    await callback.answer(t(lang, 'searching_zodiac'))
    gender_value = callback.data.split(":", 1)[1]
    user = await db.get_user(callback.from_user.id)
    if not user or not user.get("zodiac"):
        await callback.message.answer(t(lang, 'no_zodiac'))
        return

    my_key = get_zodiac_key(user.get("zodiac"))
    if not my_key:
        await callback.message.answer(t(lang, 'zodiac_not_recognized'))
        return

    compat = ZODIAC_COMPATIBILITY.get(my_key, {})
    mos_keys_only = compat.get("mos", [])

    # O'z burjini ham qo'shib, to'liq ro'yxatni tuzamiz
    # (mendagi burj + menga mos burjlar)
    mos_keys, mos_zodiac_names = build_zodiac_compat_filters(mos_keys_only, searcher_zodiac=user.get("zodiac"))

    filters = {"zodiac_keys": mos_keys, "zodiac_names": mos_zodiac_names}
    if gender_value != "all":
        filters["gender"] = gender_value

    # Xuddi yuqoridagi kabi - "faqat jiddiy niyatli erkaklar" filtri to'g'ri
    # ishlashi uchun qidiruvchining maqsadlarini yuboramiz.
    filters["searcher_goals"] = user.get("goals") or []

    users = await db.search_users_by_zodiac(callback.from_user.id, filters)
    if not users:
        await callback.message.answer(t(lang, 'no_zodiac_match'))
        return

    search_sessions[callback.from_user.id] = {'users': users, 'index': 0, 'lang': lang}
    await show_search_candidate(callback.message, callback.from_user.id, 0, lang)


@dp.callback_query(F.data.startswith("search_gender:"))
async def search_gender_callback(callback: types.CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)
    await callback.answer(t(lang, 'searching'))
    gender_value = callback.data.split(":", 1)[1]

    # Qidirayotgan foydalanuvchining ma'lumotlarini olamiz
    me = await db.get_user(callback.from_user.id)
    if not _is_profile_complete(me):
        await callback.message.answer(t(lang, 'no_profile'))
        return
    my_gender = me.get('gender') if me else None
    my_zodiac_key = normalize_zodiac_key(me.get('zodiac') or '') if me else None

    filters = {}

    if gender_value == "all":
        # Barchasi: faqat o'zining jinsidagilarni chiqarmaslik
        if my_gender:
            filters["exclude_gender"] = my_gender
    else:
        # Foydalanuvchi qaysi jinsni tanlagan bo'lsa, o'sha jinsni qidiradi
        filters["gender"] = gender_value

    # Burj moslik foizi uchun
    filters["searcher_zodiac_key"] = my_zodiac_key

    # Qidiruvchining o'z maqsadlarini yuboramiz — aks holda "faqat jiddiy
    # niyatli erkaklar ko'rsin" (only_serious_men) sozlamasi yoqilgan
    # profillar hech qachon bot ichidan chiqmay qoladi (Web App'da esa
    # bu maydon to'g'ri yuborilgani uchun chiqadi).
    filters["searcher_goals"] = (me.get("goals") if me else None) or []

    users = await db.search_users(callback.from_user.id, filters)
    if not users:
        await callback.message.answer(t(lang, 'no_results'))
        return

    search_sessions[callback.from_user.id] = {
        'users': users, 'index': 0, 'lang': lang,
        'searcher_zodiac_key': my_zodiac_key,
    }
    await show_search_candidate(callback.message, callback.from_user.id, 0, lang)


@dp.callback_query(F.data == 'search_skip')
async def search_skip_callback(callback: types.CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)
    await callback.answer()
    session = search_sessions.get(callback.from_user.id)
    if not session:
        await callback.message.answer(t(lang, 'no_results'))
        return
    index = session.get('index', 0) + 1
    session['index'] = index
    search_sessions[callback.from_user.id] = session
    await show_search_candidate(callback.message, callback.from_user.id, index, lang)


@dp.callback_query(F.data.startswith('search_like:'))
async def search_like_callback(callback: types.CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)
    to_user = int(callback.data.split(':', 1)[1])
    can_like = await db.check_and_increment_limit(callback.from_user.id, 'likes')
    if not can_like:
        await callback.answer(t(lang, 'limit_exceeded_likes'), show_alert=True)
        return

    is_match = await db.add_like(callback.from_user.id, to_user)
    to_user_data = await db.get_user(to_user)
    my_data = await db.get_user(callback.from_user.id)

    if is_match and to_user_data and my_data:
        try:
            to_lang = await get_user_lang(to_user)
            await bot.send_message(to_user, t(to_lang, 'match', name=my_data['full_name']))
            await callback.message.answer(t(lang, 'match', name=to_user_data['full_name']))
        except Exception:
            pass
    else:
        try:
            if to_user_data and my_data:
                to_lang = await get_user_lang(to_user)
                await bot.send_message(to_user, t(to_lang, 'like_notify', name=my_data['full_name']))
        except Exception:
            pass
        await callback.answer(t(lang, 'like_sent'), show_alert=False)

    await _advance_search(callback, lang)


@dp.callback_query(F.data.startswith('search_super_like_pick:'))
async def search_super_like_pick_callback(callback: types.CallbackQuery):
    """Super Like bosilganda — avval stiker tanlash klaviaturasini ko'rsatamiz."""
    lang = await get_user_lang(callback.from_user.id)
    to_user = int(callback.data.split(':', 1)[1])
    await callback.answer()
    try:
        await callback.message.edit_reply_markup(reply_markup=build_sticker_picker_keyboard(lang, to_user))
    except Exception:
        # edit muvaffaqiyatsiz bo'lsa (masalan rasm captioni o'zgarmadi), yangi xabar bilan ko'rsatamiz
        await callback.message.answer(t(lang, 'super_like_sticker'), reply_markup=build_sticker_picker_keyboard(lang, to_user))


@dp.callback_query(F.data.startswith('search_super_like_cancel:'))
async def search_super_like_cancel_callback(callback: types.CallbackQuery):
    """Stiker tanlashni bekor qilish — odatdagi tugmalarga qaytaramiz."""
    lang = await get_user_lang(callback.from_user.id)
    to_user = int(callback.data.split(':', 1)[1])
    await callback.answer()
    try:
        await callback.message.edit_reply_markup(reply_markup=build_candidate_keyboard(lang, to_user))
    except Exception:
        pass


@dp.callback_query(F.data.startswith('search_super_like_send:'))
async def search_super_like_send_callback(callback: types.CallbackQuery):
    """Foydalanuvchi stikerni tanlagandan so'ng — Super Like jo'natiladi va tanlangan stiker bilan xabar beriladi."""
    lang = await get_user_lang(callback.from_user.id)
    parts = callback.data.split(':')
    to_user = int(parts[1])
    try:
        sticker_idx = int(parts[2])
        sticker = STICKERS[sticker_idx]
    except (IndexError, ValueError):
        sticker = '⭐'

    can_super = await db.check_and_increment_limit(callback.from_user.id, 'super_likes')
    if not can_super:
        await callback.answer(t(lang, 'limit_exceeded_super'), show_alert=True)
        try:
            await callback.message.edit_reply_markup(reply_markup=build_candidate_keyboard(lang, to_user))
        except Exception:
            pass
        return

    is_match = await db.add_like(callback.from_user.id, to_user, is_super=True)
    await db.increment_super_like_usage(callback.from_user.id)
    to_user_data = await db.get_user(to_user)
    my_data = await db.get_user(callback.from_user.id)
    sticker_part = f"{sticker} "

    if is_match and to_user_data and my_data:
        try:
            to_lang = await get_user_lang(to_user)
            await bot.send_message(
                to_user,
                t(to_lang, 'super_like_match_notify', sticker=sticker_part, name=my_data['full_name']),
                parse_mode="Markdown"
            )
            await callback.message.answer(
                t(lang, 'super_like_match_self', sticker=sticker_part, name=to_user_data['full_name']),
                parse_mode="Markdown"
            )
        except Exception:
            pass
    else:
        try:
            if to_user_data and my_data:
                to_lang = await get_user_lang(to_user)
                await bot.send_message(
                    to_user,
                    t(to_lang, 'super_like_notify_btn', sticker=sticker_part, name=my_data['full_name']),
                    parse_mode="Markdown"
                )
        except Exception:
            pass

    await callback.answer(f"{sticker} " + t(lang, 'super_like_sent'), show_alert=False)
    await _advance_search(callback, lang)



@dp.callback_query(F.data.startswith('search_message:'))
async def search_message_callback(callback: types.CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)
    to_user = int(callback.data.split(':', 1)[1])
    can_write = await db.can_write(callback.from_user.id, to_user)
    if not can_write:
        await callback.answer(t(lang, 'need_like_first'), show_alert=True)
        return
    pending_message_targets[callback.from_user.id] = to_user
    await callback.answer(t(lang, 'send_message_text'), show_alert=True)
    await callback.message.answer(t(lang, 'send_message_text'))


async def _advance_search(callback, lang='uz'):
    session = search_sessions.get(callback.from_user.id)
    if not session:
        return
    index = session.get('index', 0) + 1
    session['index'] = index
    search_sessions[callback.from_user.id] = session
    await show_search_candidate(callback.message, callback.from_user.id, index, lang)


@dp.callback_query(F.data == "show_main_menu")
async def show_main_menu_callback(callback: types.CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)
    await callback.answer()
    keyboard = await main_menu_keyboard(lang, callback.from_user.id)
    await callback.message.answer(t(lang, 'main_menu'), reply_markup=keyboard)


@dp.callback_query(F.data == "show_profile")
async def show_profile_callback(callback: types.CallbackQuery):
    await show_profile_handler(callback)


@dp.message()
async def handle_pending_message(message: types.Message):
    to_user = pending_message_targets.get(message.from_user.id)
    if not to_user:
        return
    lang = await get_user_lang(message.from_user.id)
    text = message.text or ''
    if not text.strip():
        await message.answer(t(lang, 'empty_message'))
        pending_message_targets.pop(message.from_user.id, None)
        return

    can_write = await db.can_write(message.from_user.id, to_user)
    if not can_write:
        await message.answer(t(lang, 'need_like_first'))
        pending_message_targets.pop(message.from_user.id, None)
        return

    can_msg = await db.check_and_increment_limit(message.from_user.id, 'messages')
    if not can_msg:
        await message.answer(t(lang, 'limit_exceeded_messages'))
        pending_message_targets.pop(message.from_user.id, None)
        return

    match_id = await db.get_match_id(message.from_user.id, to_user)
    if not match_id:
        await message.answer(t(lang, 'need_like_first'))
        pending_message_targets.pop(message.from_user.id, None)
        return

    await db.send_chat_message(match_id, message.from_user.id, text.strip())
    await message.answer(t(lang, 'message_sent'))

    to_user_data = await db.get_user(to_user)
    if to_user_data:
        try:
            to_lang = await get_user_lang(to_user)
            await bot.send_message(to_user, t(to_lang, 'new_message',
                                              name=message.from_user.first_name,
                                              text=text.strip()[:100]))
        except Exception:
            pass

    pending_message_targets.pop(message.from_user.id, None)


@dp.message(F.web_app_data)
async def web_app_data_handler(message: types.Message):
    try:
        data = json.loads(message.web_app_data.data)
        action = data.get("action")
        lang = await get_user_lang(message.from_user.id)

        if action == "save_profile":
            profile_data = data.get("profile", {})
            profile_data["username"] = message.from_user.username
            profile_data["telegram_id"] = message.from_user.id

            is_valid, validation_error = _validate_profile_payload(profile_data)
            if not is_valid:
                logger.warning(f"Anketa saqlanmadi (validatsiya): telegram_id={message.from_user.id}, sabab={validation_error}")
                await message.answer(t(lang, 'save_error'))
                return

            success = await db.save_user(message.from_user.id, profile_data)
            if success:
                keyboard = await main_menu_keyboard(lang, message.from_user.id)
                is_female = await db.is_female_user(message.from_user.id)
                text = t(lang, 'profile_saved') + "\n\n" + t(lang, 'welcome', name=message.from_user.first_name)
                if not is_female:
                    text += t(lang, 'limits_info')
                await message.answer(
                    text,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
            else:
                await message.answer(t(lang, 'save_error'))

        elif action == "like_user":
            to_user = int(data.get("to_user"))

            can_like = await db.check_and_increment_limit(message.from_user.id, 'likes')
            if not can_like:
                await message.answer(t(lang, 'limit_info_long'))
                return

            logger.info(f"Like action from {message.from_user.id} to {to_user}")
            is_match = await db.add_like(message.from_user.id, to_user)
            to_user_data = await db.get_user(to_user)
            my_data = await db.get_user(message.from_user.id)

            if is_match:
                if to_user_data and my_data:
                    await message.answer(
                        t(lang, 'match', name=to_user_data['full_name']),
                        parse_mode="Markdown"
                    )
                    try:
                        to_lang = await get_user_lang(to_user)
                        await bot.send_message(
                            to_user,
                            t(to_lang, 'match', name=my_data['full_name']),
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.error(f"Match notify error: {e}")
                else:
                    await message.answer(t(lang, 'match', name=''))
            else:
                await message.answer(t(lang, 'like_sent'))
                if to_user_data and my_data:
                    try:
                        to_lang = await get_user_lang(to_user)
                        await bot.send_message(
                            to_user,
                            t(to_lang, 'like_notify', name=my_data['full_name']),
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.error(f"Like notification error: {e}")

        elif action == "super_like_user":
            to_user = int(data.get("to_user"))
            sticker = data.get("sticker", '')

            can_super = await db.check_and_increment_limit(message.from_user.id, 'super_likes')
            if not can_super:
                await message.answer(t(lang, 'limit_info_long'))
                return

            is_match = await db.add_like(message.from_user.id, to_user)
            to_user_data = await db.get_user(to_user)
            my_data = await db.get_user(message.from_user.id)

            if is_match:
                if to_user_data and my_data:
                    try:
                        to_lang = await get_user_lang(to_user)
                        await bot.send_message(
                            to_user,
                            t(to_lang, 'super_like_match', name=my_data['full_name']),
                            parse_mode="Markdown"
                        )
                        await message.answer(
                            t(lang, 'super_like_match', name=to_user_data['full_name']),
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.error(f"Super Like Match notify error: {e}")
            else:
                if to_user_data and my_data:
                    try:
                        to_lang = await get_user_lang(to_user)
                        await bot.send_message(
                            to_user,
                            t(to_lang, 'super_like_notify', name=my_data['full_name']),
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.error(f"Super Like notify error: {e}")
                await message.answer(t(lang, 'super_like_sent'))

        elif action == "block_user":
            blocked_id = int(data.get("blocked_id"))
            await db.block_user(message.from_user.id, blocked_id)
            await message.answer(t(lang, 'blocked'))

        elif action == "send_message":
            to_user = int(data.get("to_user"))
            message_text = data.get("message", '').strip()

            can_msg = await db.check_and_increment_limit(message.from_user.id, 'messages')
            if not can_msg:
                await message.answer(t(lang, 'limit_info_long'))
                return

            match_id = await db.get_match_id(message.from_user.id, to_user)
            if match_id:
                await db.send_chat_message(match_id, message.from_user.id, message_text)
                await message.answer(t(lang, 'message_sent'))
                to_user_data = await db.get_user(to_user)
                if to_user_data:
                    try:
                        to_lang = await get_user_lang(to_user)
                        await bot.send_message(
                            to_user,
                            t(to_lang, 'new_message',
                              name=message.from_user.first_name,
                              text=message_text[:100]),
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.error(f"Message notify error: {e}")
            else:
                await message.answer(t(lang, 'need_like_first'))

        elif action == "search":
            filters = data.get("filters", {})

            # Ensure profile is complete before allowing WebApp-triggered search
            profile_user = await db.get_user(message.from_user.id)
            if not _is_profile_complete(profile_user):
                await message.answer(t(lang, 'please_fill_profile'))
                return

            zodiac_compat_list = filters.pop('zodiac_compat_list', None)
            if zodiac_compat_list:
                searcher = await db.get_user(message.from_user.id)
                searcher_zodiac = searcher.get('zodiac') if searcher else None
                mos_keys, mos_names = build_zodiac_compat_filters(zodiac_compat_list, searcher_zodiac)

                zodiac_filters = dict(filters)
                zodiac_filters['zodiac_keys'] = mos_keys
                zodiac_filters['zodiac_names'] = mos_names
                users = await db.search_users_by_zodiac(message.from_user.id, zodiac_filters)
            else:
                users = await db.search_users(message.from_user.id, filters)

            if not users:
                await message.answer(t(lang, 'no_results'))
                return

            for u in users[:5]:
                text = format_user_card(u, lang)

                builder = InlineKeyboardBuilder()
                builder.add(InlineKeyboardButton(text=t(lang, 'btn_like'), callback_data=f"like_{u['telegram_id']}"))
                builder.add(InlineKeyboardButton(text=t(lang, 'btn_block'), callback_data=f"block_{u['telegram_id']}"))
                builder.add(InlineKeyboardButton(text=t(lang, 'btn_write'), callback_data=f"write_{u['telegram_id']}"))

                photo = get_photo_input(u)
                if photo:
                    await message.answer_photo(
                        photo,
                        caption=text,
                        parse_mode="Markdown",
                        reply_markup=builder.as_markup()
                    )
                else:
                    await message.answer(text, parse_mode="Markdown", reply_markup=builder.as_markup())

        elif action == "change_language":
            # Web App dan til o'zgartirish
            new_lang = data.get("language", "uz")
            if new_lang in SUPPORTED_LANGUAGES:
                await db.set_user_language(message.from_user.id, new_lang)
                await message.answer(t(new_lang, 'language_changed', lang=SUPPORTED_LANGUAGES[new_lang]['name']))

    except Exception as e:
        logger.error(f"WebApp data error: {e}")
        await message.answer(t(await get_user_lang(message.from_user.id), 'save_error'))


@dp.callback_query(F.data.startswith("accept_like_"))
async def accept_like_callback(callback: types.CallbackQuery):
    """Foydalanuvchi botdan like-ni qabul qilganda"""
    lang = await get_user_lang(callback.from_user.id)
    try:
        from_user = int(callback.data.replace("accept_like_", ""))
    except ValueError:
        await callback.answer("Xatolik", show_alert=True)
        return

    match_id = await db.accept_like(callback.from_user.id, from_user)
    if match_id:
        to_data = await db.get_user(callback.from_user.id)
        from_data = await db.get_user(from_user)
        # Pending xabarlarni chat ga o'tkazish
        try:
            await db.deliver_pending_messages_to_match(from_user, callback.from_user.id)
        except Exception as e:
            logger.error(f"Deliver pending messages error: {e}")
        if to_data and from_data:
            try:
                from_lang = await get_user_lang(from_user)
                await bot.send_message(
                    from_user,
                    t(from_lang, 'like_accepted', name=to_data['full_name']),
                    parse_mode="Markdown"
                )
                # Muloqotni darhol boshlash uchun tugma qo'shamiz
                write_builder = InlineKeyboardBuilder()
                write_builder.row(
                    InlineKeyboardButton(text=t(lang, 'btn_write'), callback_data=f"search_message:{from_user}")
                )
                await callback.message.edit_text(
                    t(lang, 'chat_started', name=from_data['full_name']),
                    parse_mode="Markdown",
                    reply_markup=write_builder.as_markup()
                )
            except Exception as e:
                logger.error(f"Accept like notify error: {e}")
        await callback.answer(t(lang, 'chat_started', name=(from_data or {}).get('full_name', '')), show_alert=False)
    else:
        await callback.answer(t(lang, 'like_not_found'), show_alert=True)


@dp.callback_query(F.data.startswith("reject_like_"))
async def reject_like_callback(callback: types.CallbackQuery):
    """Foydalanuvchi botdan like-ni rad etganda"""
    lang = await get_user_lang(callback.from_user.id)
    try:
        from_user = int(callback.data.replace("reject_like_", ""))
    except ValueError:
        await callback.answer("Xatolik", show_alert=True)
        return

    rejected = await db.reject_like(callback.from_user.id, from_user)
    if rejected:
        from_data = await db.get_user(from_user)
        to_data = await db.get_user(callback.from_user.id)
        if from_data and to_data:
            try:
                from_lang = await get_user_lang(from_user)
                await bot.send_message(
                    from_user,
                    t(from_lang, 'rejected', name=to_data['full_name']),
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Reject like notify error: {e}")
        try:
            await callback.message.edit_text(t(lang, 'rejected', name=(from_data or {}).get('full_name', '')))
        except Exception:
            pass
    await callback.answer()


@dp.callback_query(F.data.startswith("like_"))
async def like_callback(callback: types.CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)
    to_user = int(callback.data.replace("like_", ""))
    can_like = await db.check_and_increment_limit(callback.from_user.id, 'likes')
    if not can_like:
        await callback.answer(t(lang, 'limit_exceeded_likes'), show_alert=True)
        return

    is_match = await db.add_like(callback.from_user.id, to_user)
    if is_match:
        to_user_data = await db.get_user(to_user)
        my_data = await db.get_user(callback.from_user.id)
        await callback.message.answer(t(lang, 'match', name=to_user_data['full_name']))
        try:
            to_lang = await get_user_lang(to_user)
            await bot.send_message(to_user, t(to_lang, 'match', name=my_data['full_name']))
        except Exception:
            pass
    else:
        await callback.answer(t(lang, 'like_sent'), show_alert=False)


@dp.callback_query(F.data.startswith("block_"))
async def block_callback(callback: types.CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)
    blocked_id = int(callback.data.replace("block_", ""))
    await db.block_user(callback.from_user.id, blocked_id)
    await callback.answer(t(lang, 'blocked'), show_alert=True)


@dp.callback_query(F.data.startswith("write_"))
async def write_callback(callback: types.CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)
    to_user = int(callback.data.replace("write_", ""))
    can = await db.can_write(callback.from_user.id, to_user)
    if can:
        to_user_data = await db.get_user(to_user)
        username = to_user_data.get("username")
        if username:
            await callback.answer(t(lang, 'write_username', username=username), show_alert=True)
        else:
            await callback.answer(t(lang, 'no_username'), show_alert=True)
    else:
        await callback.answer(t(lang, 'need_like_first'), show_alert=True)


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
    if 'gender' in clean_user:
        clean_user['gender'] = db.normalize_gender(clean_user.get('gender'))
    # Eski yozuvlarda photo_base64 "data:image/...;base64," prefiksisiz
    # saqlangan bo'lishi mumkin (watermark bug tufayli) - bunday hollarda
    # <img src="..."> ishlamaydi, shuning uchun bu yerda tuzatib qo'yamiz.
    photo_b64 = clean_user.get('photo_base64')
    if photo_b64 and isinstance(photo_b64, str) and not photo_b64.startswith('data:'):
        clean_user['photo_base64'] = f"data:image/jpeg;base64,{photo_b64}"
    return clean_user


# ========== REAL TIME (WEBSOCKET) ==========
# Chat bo'limida xabarlar va yangi-xabar belgisi (badge) darhol - 3-15 soniyalik
# so'rovlarni kutmasdan - yangilanishi uchun WebSocket ulanishlar registri.
# Bir foydalanuvchi bir nechta qurilma/tabda ochgan bo'lishi mumkin, shuning
# uchun har bir telegram_id uchun ulanishlar to'plami (set) saqlanadi.
ws_connections: dict = {}


def ws_register(telegram_id, ws):
    ws_connections.setdefault(int(telegram_id), set()).add(ws)


def ws_unregister(telegram_id, ws):
    conns = ws_connections.get(int(telegram_id))
    if conns is not None:
        conns.discard(ws)
        if not conns:
            ws_connections.pop(int(telegram_id), None)


async def ws_push(telegram_id, payload: dict):
    """Berilgan foydalanuvchining barcha ochiq WebSocket ulanishlariga real-time xabar yuboradi."""
    conns = ws_connections.get(int(telegram_id))
    if not conns:
        return
    data = json.dumps(payload, default=str)
    dead = []
    for ws in list(conns):
        try:
            if ws.closed:
                dead.append(ws)
                continue
            await ws.send_str(data)
        except Exception as e:
            logger.warning(f"WS push xatolik ({telegram_id}): {e}")
            dead.append(ws)
    for ws in dead:
        conns.discard(ws)


async def chat_ws_handler(request):
    """Web App'ning chat bo'limi uchun real-time WebSocket ulanishi.
    Ulanish: /ws/chat?telegram_id=123456789"""
    ws = web.WebSocketResponse(heartbeat=25)
    await ws.prepare(request)

    telegram_id = None
    try:
        telegram_id = int(request.query.get('telegram_id', 0))
    except (TypeError, ValueError):
        telegram_id = None

    if not telegram_id or telegram_id <= 0:
        await ws.close(code=4001, message=b'telegram_id required')
        return ws

    ws_register(telegram_id, ws)
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.ERROR:
                logger.warning(f"WS xatolik {telegram_id}: {ws.exception()}")
            # Frontend'dan boshqa ma'lumot kutilmaydi - ulanish faqat
            # push-xabarlarni real-time yetkazish uchun ochiq turadi.
    finally:
        ws_unregister(telegram_id, ws)

    return ws


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
    if request.path.startswith('/ws/'):
        return response
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response


# Ban tekshiruvidan chiqarib qo'yiladigan yo'llar:
# /api/profile - ban ma'lumoti javob ichida (ban maydonida) qaytariladi, shu orqali
#   frontend "siz banlangansiz" ekranini muddati bilan ko'rsata oladi (blank 403 emas).
# /api/report - banlangan foydalanuvchi ham shikoyat topshira olishi kerak bo'lishi mumkin.
BAN_CHECK_EXCLUDED_PATHS = {'/api/profile', '/api/report'}
BAN_ID_FIELDS = ('telegram_id', 'blocker', 'from_user', 'sender_id', 'reporter_id')


@web.middleware
async def ban_check_middleware(request, handler):
    """Barcha (deyarli) POST API so'rovlarida foydalanuvchi banlanganmi tekshiradi.
    Banlangan bo'lsa - so'rov bajarilmasdan, ban ma'lumoti bilan 403 qaytariladi."""
    if request.method != 'POST' or request.path in BAN_CHECK_EXCLUDED_PATHS or request.path.endswith('/webhook'):
        return await handler(request)

    try:
        data = await request.json()
    except Exception:
        return await handler(request)

    if not isinstance(data, dict):
        return await handler(request)

    telegram_id = None
    for field in BAN_ID_FIELDS:
        val = data.get(field)
        if val is not None:
            try:
                telegram_id = int(val)
                break
            except (TypeError, ValueError):
                continue

    if telegram_id is None:
        return await handler(request)

    try:
        ban_info = await db.get_ban_info(telegram_id)
    except Exception:
        return await handler(request)

    if ban_info.get('is_banned'):
        return web.json_response({
            'success': False,
            'banned': True,
            'banned_until': ban_info.get('banned_until'),
            'ban_reason': ban_info.get('ban_reason'),
        }, status=403)

    return await handler(request)


async def telegram_webhook_handler(request: web.Request):
    try:
        update_data = await request.json()
        update = types.Update(**update_data)
        await dp.feed_update(bot, update)
        return web.Response(text="OK", status=200)
    except TelegramForbiddenError:
        # Foydalanuvchi botni bloklagan — bu normal holat, 200 qaytaramiz
        # Telegram qayta urinishni to'xtatadi
        return web.Response(text="OK", status=200)
    except Exception as exc:
        logger.error("Webhook update error: %s", exc, exc_info=True)
        return web.Response(text="Bad Request", status=400)


async def search_api(request):
    try:
        data = await request.json()
        telegram_id = data.get('telegram_id')
        filters = data.get('filters', {})
        if telegram_id is None:
            telegram_id = 0

        # Qidirayotgan foydalanuvchining ma'lumotlarini olish (maqsadlar va burj uchun)
        searcher = None
        if telegram_id and 'searcher_goals' not in filters:
            try:
                searcher = await db.get_user(int(telegram_id))
                if searcher:
                    filters['searcher_goals'] = searcher.get('goals') or []
            except Exception:
                pass

        # Burj moslik foizini hisoblash uchun qidiruvchining burjini kalitga aylantiramiz
        if searcher and searcher.get('zodiac'):
            filters['searcher_zodiac_key'] = normalize_zodiac_key(searcher.get('zodiac'))

        zodiac_compat_list = filters.pop('zodiac_compat_list', None)
        if zodiac_compat_list:
            searcher_zodiac = searcher.get('zodiac') if searcher else None
            mos_keys, mos_names = build_zodiac_compat_filters(zodiac_compat_list, searcher_zodiac)

            zodiac_filters = dict(filters)
            zodiac_filters['zodiac_keys'] = mos_keys
            zodiac_filters['zodiac_names'] = mos_names
            users = await db.search_users_by_zodiac(int(telegram_id), zodiac_filters)
        else:
            users = await db.search_users(int(telegram_id), filters)

        clean_users = [serialize_user(u) for u in users]
        return web.json_response({'success': True, 'users': clean_users})
    except Exception as e:
        logger.error(f"SEARCH API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def search_count_api(request):
    """Filtrlar bo'yicha foydalanuvchilar sonini qaytaradi (statistika ko'rsatish uchun)."""
    try:
        data = await request.json()
        telegram_id = data.get('telegram_id')
        filters = data.get('filters', {})
        if telegram_id is None:
            telegram_id = 0

        if telegram_id:
            try:
                searcher = await db.get_user(int(telegram_id))
                if searcher:
                    filters['searcher_goals'] = searcher.get('goals') or []
                    filters['searcher_zodiac'] = searcher.get('zodiac')
            except Exception:
                pass

        count = await db.count_search_users(int(telegram_id) if telegram_id else 0, filters)
        return web.json_response({'success': True, 'count': count})
    except Exception as e:
        logger.error(f"SEARCH COUNT API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'count': 0, 'error': str(e)}, status=500)



async def profile_api(request):
    try:
        data = await request.json()
        telegram_id = data.get('telegram_id')
        if telegram_id is None:
            return web.json_response({'success': False, 'error': 'telegram_id required'}, status=400)

        telegram_id = int(telegram_id)
        ban_info = await db.get_ban_info(telegram_id)
        ban_payload = None
        if ban_info.get('is_banned'):
            ban_payload = {
                'banned': True,
                'banned_until': ban_info.get('banned_until'),
                'ban_reason': ban_info.get('ban_reason'),
            }

        user = await db.get_user(telegram_id)
        if user:
            return web.json_response({'success': True, 'user': serialize_user(user), 'ban': ban_payload})
        return web.json_response({'success': True, 'user': None, 'ban': ban_payload})
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

        is_valid, validation_error = _validate_profile_payload(profile)
        if not is_valid:
            logger.warning(f"SAVE PROFILE API validatsiya xatolik: telegram_id={telegram_id}, sabab={validation_error}")
            return web.json_response({'success': False, 'error': validation_error}, status=400)


        profile['telegram_id'] = int(telegram_id)
        profile['username'] = profile.get('username')

        # === AI Filter: rasm yuklanayotgan bo'lsa, avtomatik tekshirish ===
        photo_base64 = profile.get('photo_base64')
        if photo_base64:
            is_safe, reason = await moderate_image_base64(photo_base64)
            if not is_safe:
                error_messages = {
                    "sexual_content": "Rasmda nomaqbul (pornografik) kontent aniqlandi. Iltimos, boshqa rasm yuklang.",
                    "weapon_content": "Rasmda qurol-yarog' aniqlandi. Iltimos, boshqa rasm yuklang.",
                    "policy_violation": "Rasm qoidalarga mos kelmadi. Iltimos, boshqa rasm yuklang.",
                    "invalid_image": "Rasm formati noto'g'ri. Iltimos, qaytadan urinib ko'ring.",
                    "moderation_not_configured": "Rasm tekshiruv xizmati sozlanmagan. Administratorga murojaat qiling.",
                    "moderation_api_error": "Rasmni tekshirishda xatolik yuz berdi. Birozdan so'ng qayta urinib ko'ring.",
                    "moderation_parse_error": "Rasmni tekshirishda xatolik yuz berdi. Birozdan so'ng qayta urinib ko'ring.",
                }
                logger.warning(
                    "Profil rasmi AI filterdan o'tmadi: telegram_id=%s, sabab=%s",
                    telegram_id, reason
                )
                return web.json_response({
                    'success': False,
                    'error': error_messages.get(reason, "Rasm tekshiruvidan o'tmadi."),
                    'reason': reason,
                }, status=400)

        # === Watermark o'chirildi: foydalanuvchilar so'roviga ko'ra rasmga
        # endi diagonal ID/username yozuvi "kuydirilmaydi". Faqat data-URI
        # prefiksi borligini ta'minlaymiz (aks holda <img> ishlamaydi).
        if photo_base64:
            if not photo_base64.startswith("data:"):
                photo_base64 = f"data:image/jpeg;base64,{_normalize_base64(photo_base64)}"
            profile['photo_base64'] = photo_base64

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
                    to_lang = await get_user_lang(int(telegram_id))
                    from_lang = await get_user_lang(int(from_user))
                    await bot.send_message(
                        int(from_user),
                        t(from_lang, 'like_accepted', name=to_data['full_name']),
                        parse_mode="Markdown"
                    )
                    # Muloqotni darhol boshlash uchun tugma qo'shamiz
                    write_builder = InlineKeyboardBuilder()
                    write_builder.row(
                        InlineKeyboardButton(text=t(to_lang, 'btn_write'), callback_data=f"search_message:{from_user}")
                    )
                    await bot.send_message(
                        int(telegram_id),
                        t(to_lang, 'chat_started', name=from_data['full_name']),
                        parse_mode="Markdown",
                        reply_markup=write_builder.as_markup()
                    )
                except Exception as e:
                    logger.error(f"Notify error: {e}")
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
                    from_lang = await get_user_lang(int(from_user))
                    await bot.send_message(
                        int(from_user),
                        t(from_lang, 'rejected', name=to_data['full_name']),
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
        telegram_id = data.get('telegram_id')
        if not match_id:
            return web.json_response({'success': False, 'error': 'match_id required'}, status=400)
        messages = await db.get_chat_messages(int(match_id))
        return web.json_response({'success': True, 'messages': [serialize_user(m) for m in messages]})
    except Exception as e:
        logger.error(f"CHAT MESSAGES API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def chat_mark_read_api(request):
    try:
        data = await request.json()
        match_id = data.get('match_id')
        telegram_id = data.get('telegram_id')
        if not match_id or not telegram_id:
            return web.json_response({'success': False, 'error': 'Missing params'}, status=400)
        await db.mark_messages_read(int(match_id), int(telegram_id))
        return web.json_response({'success': True})
    except Exception as e:
        logger.error(f"CHAT MARK READ API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def send_chat_api(request):
    try:
        data = await request.json()
        match_id = data.get('match_id')
        sender_id = data.get('sender_id')
        message = data.get('message', '').strip()
        if not match_id or not sender_id or not message:
            return web.json_response({'success': False, 'error': 'Missing params'}, status=400)


        can_msg = await db.check_and_increment_limit(int(sender_id), 'messages')
        if not can_msg:
            return web.json_response({
                'success': False,
                'error': 'limit_exceeded',
                'message': 'Kunlik xabar yuborish limitingiz tugadi!'
            }, status=403)

        message_row = await db.send_chat_message(int(match_id), int(sender_id), message)
        success = message_row is not None

        if success:
            to_user = None
            try:
                match_users = await db.get_match_users(int(match_id))
                if match_users:
                    to_user = match_users[0] if match_users[1] == int(sender_id) else match_users[1]
                    if to_user is not None and int(to_user) == int(sender_id):
                        to_user = None
            except Exception as lookup_err:
                logger.error(f"Chat match users lookup error: {lookup_err}")

            # Xabarni suhbatdoshga (va agar u boshqa qurilmada ham ochiq bo'lsa,
            # yuboruvchining o'ziga ham) WebSocket orqali REAL-TIME yetkazamiz -
            # bu orqali chat ochiq bo'lsa xabar darhol, ro'yxatdagi belgi (badge)
            # esa foydalanuvchi boshqa bo'limda bo'lsa ham shu zahoti yangilanadi.
            ws_payload = {'type': 'chat_message', 'match_id': int(match_id), 'message': message_row}
            recipient_online = False
            if to_user is not None:
                recipient_online = bool(ws_connections.get(int(to_user)))
                await ws_push(int(to_user), ws_payload)
            await ws_push(int(sender_id), ws_payload)

            # Suhbatdosh hozir Web App'ni ochiq ushlab turmagan (ya'ni WebSocket
            # ulanmagan) bo'lsa, Telegram orqali bildirishnoma yuboramiz - ochiq
            # bo'lsa xabarni real-time o'zi ko'radi, qo'shimcha bildirishnoma shart emas.
            if to_user is not None and not recipient_online:
                    try:
                        sender_data = await db.get_user(int(sender_id))
                        sender_name = (sender_data or {}).get('full_name', 'Foydalanuvchi')
                        to_lang = await get_user_lang(int(to_user))
                        # Agar rasm yuborilgan bo'lsa, base64 matnini emas, qisqa belgi ko'rsatamiz
                        preview_text = '📷 Rasm' if message.startswith('[RASM]') else message[:100]
                        notify_text = t(to_lang, 'new_message', name=sender_name, text=preview_text)
                        photo = get_photo_input(sender_data) if sender_data else None
                        if photo:
                            await bot.send_photo(int(to_user), photo, caption=notify_text)
                        else:
                            await bot.send_message(int(to_user), notify_text)
                    except Exception as notify_err:
                        logger.error(f"Chat message notify error: {notify_err}")
                    # Bildirishnoma yubormasdan xatolik bo'lsa ham, xabar chatda saqlanib qoladi

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
        try:
            from_user = int(data.get('from_user'))
            to_user = int(data.get('to_user'))
        except (TypeError, ValueError):
            return web.json_response({'success': False, 'error': 'Invalid user ids'}, status=400)

        if from_user <= 0 or to_user <= 0:
            return web.json_response({'success': False, 'error': 'Invalid user ids'}, status=400)


        can = await db.can_write(from_user, to_user)
        if not can:
            return web.json_response({'success': False, 'error': 'Unauthorized'}, status=403)

        match_id = await db.create_match(from_user, to_user)
        if match_id:
            return web.json_response({'success': True, 'match_id': match_id})
        return web.json_response({'success': False, 'error': 'Failed to create match'}, status=500)
    except Exception as e:
        logger.error(f"INITIATE CHAT API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def send_pending_message_api(request):
    """Qidiruvdan (match bo'lmasa ham) xabar yuborilganda - darhol haqiqiy
    chat (match) ochiladi va xabar chat_messages ga yoziladi, shu bilan
    birga qabul qiluvchiga Telegram orqali bildirishnoma yuboriladi.
    Like bosish yoki uni qabul qilish shart emas - xabar ikkala tomon
    uchun ham Web App'ning Chat bo'limida darhol ko'rinadi."""
    try:
        data = await request.json()
        try:
            from_user = int(data.get('from_user'))
            to_user = int(data.get('to_user'))
        except (TypeError, ValueError):
            return web.json_response({'success': False, 'error': 'Invalid user ids'}, status=400)

        message = str(data.get('message', '')).strip()
        if not message:
            return web.json_response({'success': False, 'error': 'Empty message'}, status=400)


        from_user_data = await db.get_user(from_user)
        to_user_data = await db.get_user(to_user)

        if not from_user_data or not to_user_data:
            return web.json_response({'success': False, 'error': 'User not found'}, status=404)

        # Kunlik xabar limitini tekshiramiz (ayollar uchun limit yo'q,
        # erkaklar uchun kuniga 10 ta xabar).
        can_msg = await db.check_and_increment_limit(from_user, 'messages')
        if not can_msg:
            return web.json_response({
                'success': False,
                'error': 'limit_exceeded',
                'message': 'Kunlik xabar yuborish limitingiz tugadi!'
            }, status=403)

        # Match bo'lmasa ham darhol chat ochamiz - ikkala foydalanuvchi
        # uchun ham suhbat Chat bo'limida shu zahoti paydo bo'ladi.
        match_id = await db.create_match(from_user, to_user)
        if not match_id:
            return web.json_response({'success': False, 'error': 'Chat ochilmadi'}, status=500)

        # Bu ikki foydalanuvchi o'rtasida avvalroq saqlanib qolgan pending
        # xabarlar bo'lsa, ularni ham shu chatga ko'chiramiz.
        try:
            await db.get_pending_messages_for_match(match_id)
        except Exception as e:
            logger.error(f"Pending migrate error: {e}")

        sent = await db.send_chat_message(match_id, from_user, message)
        if not sent:
            return web.json_response({'success': False, 'error': 'Xabar yuborilmadi'}, status=500)

            try:
                to_lang = await get_user_lang(to_user)
                sender_name = from_user_data.get('full_name', 'Foydalanuvchi')
                notify_msg = (
                    f"💬 *{sender_name}* sizga xabar yubordi:\n\n"
                    f"_{message}_\n\n"
                    f"Javob berish uchun Web App'dagi Chat bo'limini tekshiring."
                )
                photo = get_photo_input(from_user_data)
                if photo:
                    await bot.send_photo(int(to_user), photo, caption=notify_msg, parse_mode="Markdown")
                else:
                    await bot.send_message(int(to_user), notify_msg, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Pending message send error: {e}")
            # Telegram xabarnomasi ketmasa ham, xabar chatda saqlanib qoldi

        return web.json_response({'success': True, 'match_id': match_id})

    except Exception as e:
        logger.error(f"SEND PENDING MESSAGE API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def like_send_api(request):
    try:
        data = await request.json()
        try:
            from_user = int(data.get('from_user'))
            to_user = int(data.get('to_user'))
        except (TypeError, ValueError):
            return web.json_response({'success': False, 'error': 'Invalid user ids'}, status=400)

        if from_user <= 0 or to_user <= 0:
            return web.json_response({'success': False, 'error': 'Invalid user ids'}, status=400)


        super_like = bool(data.get('super_like', False))
        sticker = data.get('sticker', '')

        limit_type = 'super_likes' if super_like else 'likes'
        can_use = await db.check_and_increment_limit(from_user, limit_type)
        if not can_use:
            return web.json_response({
                'success': False,
                'error': 'limit_exceeded',
                'message': f"Kunlik {limit_type} limitingiz tugadi!"
            }, status=403)

        # add_like — mutual bo'lsa match yaratiladi, aks holda faqat like saqlanadi
        is_mutual = await db.add_like(from_user, to_user, is_super=super_like)
        if super_like:
            await db.increment_super_like_usage(from_user)

        # Match ID ni faqat mutual bo'lsa olamiz
        match_id = await db.get_match_id(from_user, to_user) if is_mutual else None

        # Pending xabarlarni match chat ga o'tkazamiz (faqat mutual bo'lsa)
        if match_id:
            await db.deliver_pending_messages_to_match(from_user, to_user)

        to_user_data = await db.get_user(to_user)
        from_user_data = await db.get_user(from_user)

        if is_mutual:
            # Ikki tomonlama match — ikkalasiga ham xabar yuboramiz
            if to_user_data and from_user_data:
                try:
                    to_lang = await get_user_lang(to_user)
                    from_lang = await get_user_lang(from_user)
                    sticker_part = f"{sticker} " if sticker else "⭐ "

                    if super_like:
                        # to_user ga: X Super Like bilan match bo'ldi
                        to_msg = t(to_lang, 'super_like_match_notify',
                                   sticker=sticker_part, name=from_user_data['full_name'])
                        # from_user ga: match bo'ldi
                        from_msg = t(from_lang, 'super_like_match_self',
                                     sticker=sticker_part, name=to_user_data['full_name'])
                    else:
                        to_msg = t(to_lang, 'match', name=from_user_data['full_name'])
                        from_msg = t(from_lang, 'match', name=to_user_data['full_name'])

                    await bot.send_message(int(to_user), to_msg, parse_mode="Markdown")
                    await bot.send_message(int(from_user), from_msg, parse_mode="Markdown")
                except Exception as e:
                    logger.error(f"Match notify error: {e}")
            return web.json_response({'success': True, 'match': True, 'match_id': match_id, 'super_like': super_like})
        else:
            # Bir tomonlama like — qabul qiluvchiga bildirishnoma + Qabul/Rad tugmalari
            if to_user_data and from_user_data:
                try:
                    to_lang = await get_user_lang(to_user)
                    sender_name = from_user_data['full_name']
                    if super_like:
                        # Super like — emoji sticker bilan xabar
                        sticker_part = f"{sticker} " if sticker else "⭐ "
                        msg = t(to_lang, 'super_like_notify_btn',
                                sticker=sticker_part, name=sender_name)
                    else:
                        msg = t(to_lang, 'like_notify_btn', name=sender_name)

                    # Jo'natuvchi haqida qo'shimcha: yoshi, shahar, about
                    extra_lines = []
                    sender_age   = from_user_data.get('age')
                    sender_city  = from_user_data.get('city', '')
                    sender_about = (from_user_data.get('about') or '').strip()
                    if sender_age:
                        extra_lines.append(f"🎂 {sender_age}")
                    if sender_city:
                        loc = format_location_label(sender_city, to_lang)
                        if loc and loc != "Joy ko'rsatilmagan":
                            extra_lines.append(f"📍 {loc}")
                    if sender_about:
                        extra_lines.append(f"💬 {sender_about}")
                    if extra_lines:
                        msg += "\n\n" + "\n".join(extra_lines)

                    # Inline accept/reject tugmalar (har ikki holatda ham)
                    kb = InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(
                            text=t(to_lang, 'btn_accept_like'),
                            callback_data=f"accept_like_{from_user}"
                        ),
                        InlineKeyboardButton(
                            text=t(to_lang, 'btn_reject_like'),
                            callback_data=f"reject_like_{from_user}"
                        ),
                    ]])
                    await bot.send_message(int(to_user), msg, parse_mode="Markdown", reply_markup=kb)
                except Exception as e:
                    logger.error(f"Like notification error: {e}")
            # Match hali yaratilmagan — frontend chatni ochmasin
            return web.json_response({'success': True, 'match': False, 'match_id': None, 'super_like': super_like})
    except Exception as e:
        logger.error(f"LIKE SEND API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


# ========== TIL API ==========
async def user_language_api(request):
    """Foydalanuvchining tilini olish/o'zgartirish"""
    try:
        data = await request.json()
        telegram_id = data.get('telegram_id')
        if not telegram_id:
            return web.json_response({'success': False, 'error': 'telegram_id required'}, status=400)


        # Agar language berilgan bo'lsa, o'zgartirish
        new_lang = data.get('language')
        if new_lang:
            if new_lang not in SUPPORTED_LANGUAGES:
                return web.json_response({'success': False, 'error': 'Invalid language'}, status=400)
            await db.set_user_language(int(telegram_id), new_lang)

        # Joriy tilni qaytarish
        lang = await db.get_user_language(int(telegram_id))
        return web.json_response({
            'success': True,
            'language': lang,
            'languages': {code: info for code, info in SUPPORTED_LANGUAGES.items()}
        })
    except Exception as e:
        logger.error(f"LANGUAGE API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def user_theme_api(request):
    """Foydalanuvchining ko'rinish rejimini (kunduzgi/tungi) olish/o'zgartirish"""
    try:
        data = await request.json()
        telegram_id = data.get('telegram_id')
        if not telegram_id:
            return web.json_response({'success': False, 'error': 'telegram_id required'}, status=400)

        # Agar theme berilgan bo'lsa, o'zgartirish
        new_theme = data.get('theme')
        if new_theme:
            if new_theme not in ('light', 'dark'):
                return web.json_response({'success': False, 'error': 'Invalid theme'}, status=400)
            await db.set_user_theme(int(telegram_id), new_theme)

        # Joriy rejimni qaytarish
        theme = await db.get_user_theme(int(telegram_id))
        return web.json_response({'success': True, 'theme': theme})
    except Exception as e:
        logger.error(f"THEME API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


# ========== LIMIT API ENDPOINTS ==========
async def limit_status_api(request):
    try:
        data = await request.json()
        telegram_id = data.get('telegram_id')
        if not telegram_id:
            return web.json_response({'success': False, 'error': 'telegram_id required'}, status=400)
        status = await db.get_limit_status(int(telegram_id))
        return web.json_response({'success': True, 'limits': status})
    except Exception as e:
        logger.error(f"LIMIT STATUS API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def referral_status_api(request):
    try:
        data = await request.json()
        telegram_id = data.get('telegram_id')
        if not telegram_id:
            return web.json_response({'success': False, 'error': 'telegram_id required'}, status=400)


        status = await db.get_referral_status(int(telegram_id))
        invite_count = await db.get_group_invite_count(int(telegram_id))
        invitees = await db.get_group_invitees(int(telegram_id))

        # Statik (umumiy) havola o'rniga shaxsiy havola qaytariladi, shunda
        # foydalanuvchi ulashgan havola orqali guruhga kirgan har bir kishi
        # aynan shu foydalanuvchi nomidan hisoblanadi.
        status['referral_link'] = await get_or_create_group_invite_link(int(telegram_id))
        status['group_invite_count'] = invite_count
        status['group_invitees'] = invitees

        return web.json_response({'success': True, 'referral': status})
    except Exception as e:
        logger.error(f"REFERRAL STATUS API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


# ========== STATS / LEADERBOARD ==========
async def leaderboard_api(request):
    try:
        conn = await db.get_db()
        try:
            # Haftalik TOP: faqat shu haftaning dushanbasidan boshlab hisoblash
            most_active = await conn.fetch("""
                SELECT u.telegram_id, u.full_name, u.photo_base64,
                       COUNT(l.id) AS count
                FROM users u
                LEFT JOIN likes l ON l.from_user = u.telegram_id
                    AND l.created_at >= date_trunc('week', NOW())
                WHERE u.is_active = TRUE
                GROUP BY u.telegram_id, u.full_name, u.photo_base64
                ORDER BY count DESC
                LIMIT 10
            """)
            top_liked = await conn.fetch("""
                SELECT u.telegram_id, u.full_name, u.photo_base64,
                       COUNT(l.id) AS count
                FROM users u
                LEFT JOIN likes l ON l.to_user = u.telegram_id
                    AND l.created_at >= date_trunc('week', NOW())
                WHERE u.is_active = TRUE
                GROUP BY u.telegram_id, u.full_name, u.photo_base64
                ORDER BY count DESC
                LIMIT 10
            """)
            # Haftalik Super Like TOP: likes jadvalidagi is_super=TRUE yozuvlaridan
            top_super_liked = await conn.fetch("""
                SELECT u.telegram_id, u.full_name, u.photo_base64,
                       COUNT(l.id) AS count
                FROM users u
                LEFT JOIN likes l ON l.to_user = u.telegram_id
                    AND l.is_super = TRUE
                    AND l.created_at >= date_trunc('week', NOW())
                WHERE u.is_active = TRUE
                GROUP BY u.telegram_id, u.full_name, u.photo_base64
                ORDER BY count DESC
                LIMIT 10
            """)

            # Haftaning qolgan vaqtini hisoblash (dushanba boshidan)
            import datetime
            now = datetime.datetime.utcnow()
            days_until_monday = (7 - now.weekday()) % 7 or 7
            next_monday = now.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=days_until_monday)
            seconds_until_reset = int((next_monday - now).total_seconds())
            week_start = (now - datetime.timedelta(days=now.weekday())).strftime('%Y-%m-%d')

        finally:
            await db.release_db(conn)

        def row_to_dict(r):
            photo_b64 = r['photo_base64']
            if photo_b64 and not photo_b64.startswith('data:'):
                photo_b64 = f"data:image/jpeg;base64,{photo_b64}"
            return {
                'telegram_id': r['telegram_id'],
                'full_name': r['full_name'] or 'Anonim',
                'photo_base64': photo_b64,
                'count': r['count'],
            }

        return web.json_response({
            'success': True,
            'most_active': [row_to_dict(r) for r in most_active],
            'top_liked': [row_to_dict(r) for r in top_liked],
            'top_super_liked': [row_to_dict(r) for r in top_super_liked],
            'weekly': True,
            'week_start': week_start,
            'seconds_until_reset': seconds_until_reset,
        })
    except Exception as e:
        logger.error(f"LEADERBOARD API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


# ========== VERIFIKATSIYA API ==========
async def verify_upload_api(request: web.Request):
    """
    Foydalanuvchi selfi yuboradi → avtomatik verified qilinadi.
    Body: { telegram_id, selfie_base64 }
    """
    try:
        data = await request.json()
        telegram_id = data.get('telegram_id')
        selfie_b64 = data.get('selfie_base64', '')

        if not telegram_id:
            return web.json_response({'success': False, 'error': 'telegram_id kerak'}, status=400)
        if not selfie_b64 or len(selfie_b64) < 100:
            return web.json_response({'success': False, 'error': 'Selfie rasm kerak'}, status=400)


        # Rasm o'lchamini tekshirish (base64 ~ 1.33x asl o'lcham)
        # Max 8MB asl rasm ≈ ~11MB base64
        if len(selfie_b64) > 11 * 1024 * 1024:
            return web.json_response({'success': False, 'error': 'Rasm hajmi juda katta (max 8MB)'}, status=400)

        # Foydalanuvchi mavjudligini tekshirish
        user = await db.get_user(int(telegram_id))
        if not user:
            return web.json_response({'success': False, 'error': 'Foydalanuvchi topilmadi'}, status=404)

        # Avatomatik tasdiqlash va saqlash
        ok = await db.save_selfie_and_verify(int(telegram_id), selfie_b64)
        if not ok:
            return web.json_response({'success': False, 'error': 'Saqlashda xatolik'}, status=500)

        # Telegram orqali xabar yuborish
        lang = await get_user_lang(int(telegram_id))
        verify_messages = {
            'uz': "✅ *Profilingiz muvaffaqiyatli tasdiqlandi!*\n\nEndi profilingizda 💙 ko'k galochka mavjud.",
            'ru': "✅ *Ваш профиль успешно верифицирован!*\n\nТеперь у вашего профиля есть 💙 синяя галочка.",
            'kk': "✅ *Профиліңіз сәтті расталды!*\n\nПрофиліңізде енді 💙 көк белгі бар.",
            'ky': "✅ *Профилиңиз ийгиликтүү ырасталды!*\n\nПрофилиңизде эми 💙 көк белги бар.",
            'kaa': "✅ *Profiliñiz wátiliwshe tastıyıqlandı!*\n\nProfiliñizde 💙 kók belgi bar.",
            'tg': "✅ *Профили шумо бомуваффақият тасдиқ шуд!*\n\nПрофили шумо акнун 💙 аломати кабуд дорад.",
            'en': "✅ *Your profile has been verified!*\n\nYour profile now has a 💙 blue checkmark.",
        }
        msg = verify_messages.get(lang, verify_messages['uz'])
        try:
            await bot.send_message(int(telegram_id), msg, parse_mode="Markdown")
        except Exception:
            pass

        return web.json_response({'success': True, 'is_verified': True})

    except Exception as e:
        logger.error(f"VERIFY API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def verify_status_api(request: web.Request):
    """Foydalanuvchining verifikatsiya holatini qaytaradi."""
    try:
        data = await request.json()
        telegram_id = data.get('telegram_id')
        if not telegram_id:
            return web.json_response({'success': False, 'error': 'telegram_id kerak'}, status=400)
        status = await db.get_verification_status(int(telegram_id))
        verified_at = status.get('verified_at')
        if verified_at is not None and hasattr(verified_at, 'isoformat'):
            verified_at = verified_at.isoformat()
        return web.json_response({
            'success': True,
            'is_verified': status.get('is_verified', False),
            'verified_at': verified_at,
        })
    except Exception as e:
        logger.error(f"VERIFY STATUS xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def moderate_photo_api(request: web.Request):
    """
    Rasm yuklashdan oldin (preview bosqichida) AI filter orqali tekshirish.
    Body: { photo_base64 }
    Javob: { success, ok, reason }
    """
    try:
        data = await request.json()
        photo_base64 = data.get('photo_base64', '')
        if not photo_base64:
            return web.json_response({'success': False, 'error': 'photo_base64 required'}, status=400)

        is_safe, reason = await moderate_image_base64(photo_base64)
        return web.json_response({'success': True, 'ok': is_safe, 'reason': reason})
    except Exception as e:
        logger.error(f"MODERATE PHOTO API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def block_api(request: web.Request):
    """Web App'dan foydalanuvchini bloklash."""
    try:
        data = await request.json()
        try:
            blocker = int(data.get('blocker'))
            blocked = int(data.get('blocked'))
        except (TypeError, ValueError):
            return web.json_response({'success': False, 'error': 'Invalid user ids'}, status=400)
        await db.block_user(blocker, blocked)
        return web.json_response({'success': True})
    except Exception as e:
        logger.error(f"BLOCK API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def report_api(request: web.Request):
    """Web App / bot'dan kelgan shikoyatni qabul qiladi.
    Body: { reporter_id, reported_id, category, description?, source, messages?: [str], photo_base64? }
    Darhol 'qabul qilindi' javobi qaytariladi, AI tekshiruvi fon jarayonida ishlaydi."""
    try:
        data = await request.json()
        try:
            reporter_id = int(data.get('reporter_id'))
        except (TypeError, ValueError):
            return web.json_response({'success': False, 'error': 'Invalid user ids'}, status=400)

        category = str(data.get('category') or 'other')
        if category not in REPORT_CATEGORIES:
            category = 'other'
        description = (data.get('description') or '')[:1000]
        source = str(data.get('source') or 'unknown')  # search_profile / chat / anon_chat
        messages = data.get('messages') or []
        if not isinstance(messages, list):
            messages = []
        photo_base64 = data.get('photo_base64')
        reported_id = None

        # Anonim chatda reported_id client'ga ma'lum emas (anonimlikni saqlash uchun) -
        # shuning uchun anon_match_id orqali serverda o'zimiz aniqlaymiz.
        anon_match_id = data.get('anon_match_id')
        if anon_match_id is not None:
            try:
                anon_match_id = int(anon_match_id)
            except (TypeError, ValueError):
                return web.json_response({'success': False, 'error': 'Invalid anon_match_id'}, status=400)
            anon_row = await db.get_anon_match(anon_match_id)
            if not anon_row or reporter_id not in (anon_row['user_a'], anon_row['user_b']):
                return web.json_response({'success': False, 'error': 'Unauthorized'}, status=403)
            reported_id = anon_row['user_b'] if reporter_id == anon_row['user_a'] else anon_row['user_a']
            if not messages:
                try:
                    anon_msgs = await db.get_anon_messages(anon_match_id)
                    messages = [m['message'] for m in anon_msgs if m.get('sender_id') == reported_id][-20:]
                except Exception:
                    messages = []
        else:
            try:
                reported_id = int(data.get('reported_id'))
            except (TypeError, ValueError):
                return web.json_response({'success': False, 'error': 'Invalid user ids'}, status=400)

        if reporter_id == reported_id:
            return web.json_response({'success': False, 'error': 'self_report_not_allowed'}, status=400)

        # Dublikat himoyasi: shu juftlik bo'yicha so'nggi 24 soatda shikoyat bo'lsa, qayta yubormaymiz
        existing = await db.get_recent_reports_for_pair(reporter_id, reported_id, hours=24)
        if existing:
            return web.json_response({'success': True, 'already_reported': True})

        # Agar rasm berilmagan bo'lsa, reported foydalanuvchining profil rasmini olamiz
        if not photo_base64:
            reported_user = await db.get_user(reported_id)
            if reported_user:
                photo_base64 = reported_user.get('photo_base64')

        context_snapshot = {'messages': messages[-20:], 'has_photo': bool(photo_base64)}
        report_id = await db.create_report(reporter_id, reported_id, category, description, source, context_snapshot)

        asyncio.create_task(
            process_report_background(report_id, reporter_id, reported_id, category, messages, photo_base64)
        )

        return web.json_response({'success': True, 'report_id': report_id})
    except Exception as e:
        logger.error(f"REPORT API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


# ========== TUNGI ANONIM CHAT (API) ==========
TASHKENT_TZ = timezone(timedelta(hours=5))  # Asia/Tashkent (DST yo'q)


def _anon_public_status(anon_row, telegram_id):
    """Frontendga faqat kerakli (identifikatsiya qilmaydigan) ma'lumotni qaytaradi."""
    if not anon_row:
        return None
    is_a = telegram_id == anon_row['user_a']
    my_accepted = anon_row['user_a_accepted'] if is_a else anon_row['user_b_accepted']
    other_accepted = anon_row['user_b_accepted'] if is_a else anon_row['user_a_accepted']
    my_reveal = anon_row['user_a_reveal'] if is_a else anon_row['user_b_reveal']
    other_reveal = anon_row['user_b_reveal'] if is_a else anon_row['user_a_reveal']
    return {
        'anon_match_id': anon_row['id'],
        'status': anon_row['status'],
        'my_accepted': bool(my_accepted),
        'other_accepted': bool(other_accepted),
        'my_reveal_requested': bool(my_reveal),
        'other_reveal_requested': bool(other_reveal),
    }


async def anon_status_api(request):
    """Foydalanuvchining joriy anonim chat holatini qaytaradi (navbatda/taklif/faol/yo'q)."""
    try:
        data = await request.json()
        telegram_id = int(data.get('telegram_id'))
        row = await db.get_my_anon_match(telegram_id)
        in_queue = False if row else await db.is_in_anon_queue(telegram_id)
        return web.json_response({
            'success': True,
            'anon': _anon_public_status(row, telegram_id),
            'in_queue': in_queue,
        })
    except Exception as e:
        logger.error(f"ANON STATUS API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def anon_queue_join_api(request):
    """Foydalanuvchi 'Anonim suhbatdosh topish' tugmasini bosganda istalgan vaqt
    navbatga qo'shiladi. Juftlashuvning o'zi fon jarayoni orqali amalga oshadi."""
    try:
        data = await request.json()
        telegram_id = int(data.get('telegram_id'))

        existing = await db.get_my_anon_match(telegram_id)
        if existing:
            return web.json_response({'success': True, 'anon': _anon_public_status(existing, telegram_id), 'in_queue': False})

        user = await db.get_user(telegram_id)
        if not user or not user.get('gender') or not user.get('full_name'):
            return web.json_response({'success': False, 'error': 'Profil to\'liq emas'}, status=400)

        await db.join_anon_queue(telegram_id)
        return web.json_response({'success': True, 'in_queue': True})
    except Exception as e:
        logger.error(f"ANON QUEUE JOIN API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def anon_queue_leave_api(request):
    """Foydalanuvchi qidiruvni bekor qiladi va navbatdan chiqadi."""
    try:
        data = await request.json()
        telegram_id = int(data.get('telegram_id'))
        await db.leave_anon_queue(telegram_id)
        return web.json_response({'success': True})
    except Exception as e:
        logger.error(f"ANON QUEUE LEAVE API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)



async def anon_messages_api(request):
    try:
        data = await request.json()
        telegram_id = int(data.get('telegram_id'))
        anon_match_id = int(data.get('anon_match_id'))
        row = await db.get_anon_match(anon_match_id)
        if not row or telegram_id not in (row['user_a'], row['user_b']):
            return web.json_response({'success': False, 'error': 'Unauthorized'}, status=403)
        messages = await db.get_anon_messages(anon_match_id)
        return web.json_response({'success': True, 'messages': [serialize_user(m) for m in messages]})
    except Exception as e:
        logger.error(f"ANON MESSAGES API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def anon_send_api(request):
    try:
        data = await request.json()
        telegram_id = int(data.get('telegram_id'))
        anon_match_id = int(data.get('anon_match_id'))
        message = (data.get('message') or '').strip()
        if not message:
            return web.json_response({'success': False, 'error': 'Bo\'sh xabar'}, status=400)


        can_msg = await db.check_and_increment_limit(telegram_id, 'messages')
        if not can_msg:
            return web.json_response({
                'success': False,
                'error': 'limit_exceeded',
                'message': 'Kunlik xabar yuborish limitingiz tugadi!'
            }, status=403)

        result = await db.send_anon_message(anon_match_id, telegram_id, message)
        success = result is not None

        if success:
            ws_payload = {
                'type': 'anon_chat_message',
                'anon_match_id': anon_match_id,
                'message': result['message']
            }
            await ws_push(result['partner_id'], ws_payload)
            await ws_push(telegram_id, ws_payload)

        return web.json_response({'success': success})
    except Exception as e:
        logger.error(f"ANON SEND API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def anon_reveal_api(request):
    """Foydalanuvchi profilni ochish (asosiy chatga o'tish)ni so'raydi yoki javob beradi."""
    try:
        data = await request.json()
        telegram_id = int(data.get('telegram_id'))
        anon_match_id = int(data.get('anon_match_id'))
        accept = bool(data.get('accept', True))

        result = await db.request_anon_reveal(telegram_id, anon_match_id, accept)
        if not result:
            return web.json_response({'success': False, 'error': 'Chat topilmadi'}, status=404)

        other_id = result.get('other_id')
        try:
            if result['status'] == 'waiting' and result.get('notify_other') and other_id:
                other_lang = await get_user_lang(other_id)
                await bot.send_message(other_id, t(other_lang, 'anon_reveal_request_notify'))
            elif result['status'] == 'revealed' and other_id:
                for uid in (telegram_id, other_id):
                    lang = await get_user_lang(uid)
                    await bot.send_message(uid, t(lang, 'anon_revealed_notify'))
            elif result['status'] == 'declined' and other_id:
                other_lang = await get_user_lang(other_id)
                await bot.send_message(other_id, t(other_lang, 'anon_reveal_declined_notify'))
        except Exception as notify_err:
            logger.warning(f"Anon reveal notify error: {notify_err}")

        return web.json_response({'success': True, 'result': result})
    except Exception as e:
        logger.error(f"ANON REVEAL API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def anon_disconnect_api(request):
    """Anonim chatni yakunlaydi (ajratish): xabarlar o'chiriladi, ikkalasi ham ajraladi."""
    try:
        data = await request.json()
        telegram_id = int(data.get('telegram_id'))
        anon_match_id = int(data.get('anon_match_id'))


        result = await db.disconnect_anon_match(telegram_id, anon_match_id)
        if not result:
            return web.json_response({'success': False, 'error': 'Chat topilmadi'}, status=404)

        other_id = result.get('other_id')
        try:
            if other_id:
                other_lang = await get_user_lang(other_id)
                await bot.send_message(other_id, t(other_lang, 'anon_disconnected_notify'))
        except Exception as notify_err:
            logger.warning(f"Anon disconnect notify error: {notify_err}")

        return web.json_response({'success': True})
    except Exception as e:
        logger.error(f"ANON DISCONNECT API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def _notify_anon_queue_match(user_a, user_b):
    """On-demand navbatda juftlashgan ikkala foydalanuvchiga ham xabar yuboradi.
    Bu holatda chat darhol 'active' bo'lib yaratilgani uchun qabul/rad qilish
    kerak emas — shunchaki suhbat boshlanganini bildiramiz."""
    for uid in (user_a, user_b):
        try:
            lang = await get_user_lang(uid)
            builder = InlineKeyboardBuilder()
            builder.row(InlineKeyboardButton(text=t(lang, 'btn_webapp'), web_app=WebAppInfo(url=f"{WEBAPP_URL}/index.html")))
            await bot.send_message(
                uid,
                t(lang, 'anon_match_found_notify'),
                parse_mode="Markdown",
                reply_markup=builder.as_markup()
            )
        except TelegramForbiddenError:
            pass
        except Exception as e:
            logger.warning(f"Anon queue match notify error for {uid}: {e}")


async def anon_queue_matcher():
    """Fon jarayoni: on-demand navbatda turgan foydalanuvchilarni muntazam
    ravishda (har necha soniyada) bir-biriga juftlab boradi, shunda anonim
    suhbatdosh istalgan vaqtda, kechqurunni kutmasdan topiladi."""
    logger.info("Anonim on-demand navbat matcher (anon_queue_matcher) ishga tushdi")
    while True:
        try:
            pairs = await db.match_from_queue()
            if pairs:
                logger.info(f"On-demand anonim chat: {len(pairs)} ta juftlik yaratildi")
            for user_a, user_b, _anon_id in pairs:
                await _notify_anon_queue_match(user_a, user_b)
        except Exception as e:
            logger.error(f"Anon queue matcher xatolik: {e}", exc_info=True)
        await asyncio.sleep(8)


async def admin_anon_run_match_api(request):
    """Admin uchun: anonim tungi chat juftlashuvini FAQAT 21:00 da emas, istalgan
    vaqtda qo'lda ishga tushirish. `create_daily_anon_matches` allaqachon band
    (pending/active), bloklangan, oddiy match bo'lgan yoki oxirgi 30 kunda anonim
    juft bo'lgan foydalanuvchilarni o'zi chiqarib tashlaydi — shuning uchun buni
    kuniga bir necha marta chaqirish xavfsiz: faqat hozircha bo'sh va mos
    foydalanuvchilar orasidan yangi juftliklar yaratiladi."""
    try:
        data = await request.json()
        if ADMIN_PASSWORD and data.get('admin_password') != ADMIN_PASSWORD:
            return web.json_response({'success': False, 'error': 'Unauthorized'}, status=403)

        today = datetime.now(TASHKENT_TZ).date()
        pairs = await db.create_daily_anon_matches(today)
        logger.info(f"Anonim chat (qo'lda ishga tushirildi): {len(pairs)} ta juftlik yaratildi ({today})")

        for user_a, user_b, _anon_id in pairs:
            await _notify_anon_queue_match(user_a, user_b)

        return web.json_response({
            'success': True,
            'pairs_created': len(pairs),
            'pairs': [
                {'user_a': user_a, 'user_b': user_b, 'anon_match_id': anon_id}
                for user_a, user_b, anon_id in pairs
            ]
        })
    except Exception as e:
        logger.error(f"ADMIN ANON RUN MATCH API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def admin_visibility_run_api(request):
    """Admin uchun: haftalik ko'rinuvchanlik/TOP-10 hisobotini istalgan vaqtda
    qo'lda ishga tushirish (test qilish yoki jadvalni majburan yangilash uchun)."""
    try:
        data = await request.json()
        if ADMIN_PASSWORD and data.get('admin_password') != ADMIN_PASSWORD:
            return web.json_response({'success': False, 'error': 'Unauthorized'}, status=403)

        result = await db.recalculate_visibility_and_top10()
        logger.info(f"Visibility (qo'lda ishga tushirildi): {result}")
        return web.json_response({'success': True, **result})
    except Exception as e:
        logger.error(f"ADMIN VISIBILITY RUN API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def anon_match_scheduler():
    """Har kuni Toshkent vaqti bilan soat 21:00 da, bir marta, BARCHA faol
    foydalanuvchilarga anonim suhbat haqida eslatma yuboradi.

    Muhim: bu yerda hech kim avtomatik juftlashtirilmaydi - anonim suhbat
    endi faqat kechqurun emas, istalgan vaqt ishlaydi. Haqiqiy juftlashtirish
    doimiy ishlaydigan `anon_queue_matcher` fon jarayoni orqali amalga oshadi
    (foydalanuvchi Web App'da "Qidirish" tugmasini bosganda). 21:00 dagi bu
    xabar shunchaki barcha foydalanuvchilarni ilovani ochib qidiruvdan
    foydalanishga taklif qiladigan eslatma, xolos."""
    logger.info("Anonim kechqurungi eslatma scheduleri ishga tushdi")
    while True:
        try:
            now = datetime.now(TASHKENT_TZ)
            today = now.date()
            already_ran = await db.has_anon_run_today(today)
            if not already_ran and now.hour >= 21:
                await db.mark_anon_run(today)
                recipients = await db.get_anon_reminder_recipients()
                sent = 0
                for uid in recipients:
                    try:
                        lang = await get_user_lang(uid)
                        builder = InlineKeyboardBuilder()
                        builder.row(InlineKeyboardButton(text=t(lang, 'btn_webapp'), web_app=WebAppInfo(url=f"{WEBAPP_URL}/index.html")))
                        await bot.send_message(
                            uid,
                            t(lang, 'anon_evening_reminder_notify'),
                            parse_mode="Markdown",
                            reply_markup=builder.as_markup()
                        )
                        sent += 1
                    except TelegramForbiddenError:
                        pass
                    except Exception as e:
                        logger.warning(f"Anon evening reminder error for {uid}: {e}")
                logger.info(f"Anonim kechqurungi eslatma: {sent}/{len(recipients)} foydalanuvchiga yuborildi ({today})")
        except Exception as e:
            logger.error(f"Anon match scheduler xatolik: {e}", exc_info=True)
        await asyncio.sleep(60)


async def visibility_scheduler():
    """Har hafta dushanba kuni (Toshkent vaqti, soat 00:05 dan keyin) bir marta
    ishga tushib, xavfsizlik/reyting ko'rinuvchanlik tizimini yangilaydi:
    - Haftalik TOP-10 (eng ko'p layk olganlar) ni topadi va ularni qidiruvda
      ko'proq ko'rsatish uchun "boost" beradi.
    - Ban tugagandan keyingi "nazorat davri"da (probation) bo'lgan
      foydalanuvchilar TOP-10 ga ketma-ket 2 marta kirsa, ularning anketasi
      qidiruvda hamma qatori (to'liq) ko'rinishga qaytariladi.
    - TOP-10dan tushib qolganlarning boosti asta-sekin pasayadi.
    """
    logger.info("Ko'rinuvchanlik (visibility) haftalik scheduleri ishga tushdi")
    while True:
        try:
            now = datetime.now(TASHKENT_TZ)
            week_start = (now - timedelta(days=now.weekday())).strftime('%Y-%m-%d')
            already_ran = await db.has_visibility_run_this_week(week_start)
            if not already_ran and now.weekday() == 0 and now.hour >= 0:
                await db.mark_visibility_run(week_start)
                result = await db.recalculate_visibility_and_top10()
                logger.info(f"Visibility scheduler ishladi: {result}")
        except Exception as e:
            logger.error(f"Visibility scheduler xatolik: {e}", exc_info=True)
        await asyncio.sleep(3600)  # har soatda tekshiradi, lekin haftada bir marta ishlaydi


async def incomplete_profile_cleanup_scheduler():
    """Doimiy fon jarayoni: anketasi hech qachon to'liq to'ldirilmagan
    foydalanuvchilarni (masalan, faqat /start bosib tilni tanlagan, lekin
    anketani to'ldirmay tashlab ketgan) bazadan butunlay o'chirib tashlaydi.

    Shu bilan botda va qidiruvda doim faqat haqiqiy, anketasi to'liq
    foydalanuvchilar qoladi ("null" ism, "Shahar ko'rsatilmagan" kabi bo'sh
    profillar bazada saqlanib qolmaydi).

    24 soatlik "grace period" beriladi — hozirgina ro'yxatdan o'ta
    boshlagan, anketani hali to'ldirib ulgurmagan foydalanuvchi bexosdan
    o'chirib yuborilmasligi uchun.
    """
    logger.info("To'liq bo'lmagan anketalarni tozalash scheduleri ishga tushdi")
    while True:
        try:
            deleted = await db.delete_incomplete_profiles(grace_hours=24)
            if deleted:
                logger.info(f"Tozalash: {deleted} ta to'liq to'ldirilmagan anketa bazadan o'chirildi.")
        except Exception as e:
            logger.error(f"Incomplete profile cleanup scheduler xatolik: {e}", exc_info=True)
        await asyncio.sleep(3600)  # har soatda ishlaydi


async def admin_cleanup_incomplete_profiles_api(request):
    """Admin uchun: to'liq bo'lmagan anketalarni istalgan vaqtda qo'lda
    tozalash (masalan, avvaldan bazada to'planib qolgan eski "bo'sh"
    qatorlarni darhol o'chirish uchun)."""
    try:
        data = await request.json()
        if ADMIN_PASSWORD and data.get('admin_password') != ADMIN_PASSWORD:
            return web.json_response({'success': False, 'error': 'Unauthorized'}, status=403)

        grace_hours = int(data.get('grace_hours', 24))
        deleted = await db.delete_incomplete_profiles(grace_hours=grace_hours)
        logger.info(f"Anketa tozalash (qo'lda ishga tushirildi): {deleted} ta o'chirildi.")
        return web.json_response({'success': True, 'deleted': deleted})
    except Exception as e:
        logger.error(f"ADMIN CLEANUP INCOMPLETE PROFILES API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def main():
    await db.init_pool()
    await db.init_db()
    logger.info("Bot ishga tushdi...")

    # Bazada avvaldan to'planib qolgan, anketasi to'liq to'ldirilmagan
    # "bo'sh" foydalanuvchilarni darhol tozalab tashlaymiz (keyingi tozalash
    # esa incomplete_profile_cleanup_scheduler orqali har soatda avtomatik davom etadi).
    try:
        deleted_at_startup = await db.delete_incomplete_profiles(grace_hours=24)
        if deleted_at_startup:
            logger.info(f"Bot ishga tushishida tozalandi: {deleted_at_startup} ta to'liq to'ldirilmagan anketa o'chirildi.")
    except Exception as e:
        logger.error(f"Ishga tushishdagi anketa tozalash xatolik: {e}", exc_info=True)

    app = web.Application()
    app.middlewares.append(cors_middleware)
    app.middlewares.append(ban_check_middleware)

    app.router.add_post('/api/search', search_api)
    app.router.add_post('/api/search/count', search_count_api)
    app.router.add_post('/api/profile', profile_api)
    app.router.add_post('/api/save_profile', save_profile_api)
    app.router.add_post('/api/admin/users', admin_users_api)
    app.router.add_post('/api/admin/analytics', admin_analytics_api)

    # Chat routes
    app.router.add_post('/api/likes/received', likes_received_api)
    app.router.add_post('/api/likes/send', like_send_api)
    app.router.add_post('/api/likes/accept', accept_like_api)
    app.router.add_post('/api/likes/reject', reject_like_api)
    app.router.add_post('/api/matches', matches_api)
    app.router.add_post('/api/chat/messages', chat_messages_api)
    app.router.add_post('/api/chat/mark_read', chat_mark_read_api)
    app.router.add_post('/api/chat/send', send_chat_api)
    app.router.add_post('/api/can_write', can_write_api)
    app.router.add_post('/api/initiate_chat', initiate_chat_api)

    # Limit routes
    app.router.add_post('/api/messages/send_pending', send_pending_message_api)
    app.router.add_post('/api/limits/status', limit_status_api)
    app.router.add_post('/api/referral/status', referral_status_api)

    # Language route
    app.router.add_post('/api/language', user_language_api)
    app.router.add_post('/api/theme', user_theme_api)

    # Stats / Leaderboard
    app.router.add_post('/api/stats/leaderboard', leaderboard_api)

    # Verifikatsiya
    app.router.add_post('/api/verify/upload', verify_upload_api)
    app.router.add_post('/api/verify/status', verify_status_api)
    app.router.add_post('/api/moderate_photo', moderate_photo_api)

    # Shikoyat va blok
    app.router.add_post('/api/block', block_api)
    app.router.add_post('/api/report', report_api)

    # Tungi anonim chat
    app.router.add_post('/api/anon/status', anon_status_api)
    app.router.add_post('/api/anon/queue/join', anon_queue_join_api)
    app.router.add_post('/api/anon/queue/leave', anon_queue_leave_api)
    app.router.add_post('/api/anon/messages', anon_messages_api)
    app.router.add_post('/api/anon/send', anon_send_api)
    app.router.add_post('/api/anon/reveal', anon_reveal_api)
    app.router.add_post('/api/anon/disconnect', anon_disconnect_api)
    app.router.add_post('/api/admin/anon/run_match', admin_anon_run_match_api)  # istalgan vaqtda qo'lda ishga tushirish
    app.router.add_post('/api/admin/visibility/run', admin_visibility_run_api)  # haftalik ko'rinuvchanlik/TOP-10 ni qo'lda ishga tushirish
    app.router.add_post('/api/admin/cleanup_incomplete_profiles', admin_cleanup_incomplete_profiles_api)  # to'liq bo'lmagan anketalarni qo'lda tozalash

    # Real-time chat (WebSocket)
    app.router.add_get('/ws/chat', chat_ws_handler)

    asyncio.create_task(anon_match_scheduler())
    asyncio.create_task(anon_queue_matcher())
    asyncio.create_task(visibility_scheduler())
    asyncio.create_task(incomplete_profile_cleanup_scheduler())

    webhook_url = os.environ.get('WEBHOOK_URL')
    if webhook_url:
        parsed = urlparse(webhook_url)
        webhook_path = parsed.path or '/telegram/webhook'
        app.router.add_post(webhook_path, telegram_webhook_handler)
        await bot.set_webhook(
            webhook_url,
            drop_pending_updates=True,
            allowed_updates=dp.resolve_used_update_types()
        )
        logger.info(f"Webhook enabled on {webhook_url}, allowed_updates={dp.resolve_used_update_types()}")
    else:
        logger.warning('WEBHOOK_URL not set; falling back to polling.')

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.environ.get('PORT', 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"✅ HTTP API server started on port {port}")

    try:
        if webhook_url:
            await asyncio.Event().wait()
        else:
            await dp.start_polling(bot, drop_pending_updates=True)
    finally:
        await db.close_pool()


if __name__ == "__main__":
    asyncio.run(main())
