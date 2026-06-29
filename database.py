import asyncpg
import json
from datetime import datetime, date, timedelta
from config import DATABASE_URL

async def get_db():
    return await asyncpg.connect(DATABASE_URL)

async def init_db():
    conn = await get_db()
    try:
        # Asosiy users jadvali
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id BIGSERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE NOT NULL,
                username TEXT,
                full_name TEXT,
                gender TEXT,
                age INTEGER,
                city TEXT,
                interests TEXT[],
                zodiac TEXT,
                goals TEXT[],
                photo_file_id TEXT,
                photo_base64 TEXT,
                invited_friends INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS photo_base64 TEXT
        """)

        await conn.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS about TEXT
        """)

        await conn.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS super_likes_used INTEGER DEFAULT 0
        """)

        await conn.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS group_subscribed BOOLEAN DEFAULT FALSE
        """)

        await conn.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS friends_invited INTEGER DEFAULT 0
        """)

        # ===== TIL MAYDONI =====
        await conn.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS language TEXT DEFAULT 'uz'
        """)

        # ===== REGION / DAVLAT MAYDONI =====
        await conn.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS region TEXT
        """)

        await conn.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS country TEXT DEFAULT 'Oʻzbekiston'
        """)

        # ===== VERIFIKATSIYA =====
        await conn.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE
        """)
        await conn.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS selfie_base64 TEXT
        """)
        await conn.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP
        """)

        # Faqat jiddiy niyatli erkaklar korina oladi (ayollar uchun sozlama)
        await conn.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS only_serious_men BOOLEAN DEFAULT FALSE
        """)

        # Likes
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS likes (
                id BIGSERIAL PRIMARY KEY,
                from_user BIGINT NOT NULL,
                to_user BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                is_super BOOLEAN DEFAULT FALSE,
                UNIQUE(from_user, to_user)
            )
        """)

        # Super like ustunini mavjud jadvalga qo'shish (migration)
        await conn.execute("""
            ALTER TABLE likes ADD COLUMN IF NOT EXISTS is_super BOOLEAN DEFAULT FALSE
        """)

        # Matches
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                id BIGSERIAL PRIMARY KEY,
                user1 BIGINT NOT NULL,
                user2 BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(user1, user2)
            )
        """)

        # Blocks
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS blocks (
                id BIGSERIAL PRIMARY KEY,
                blocker BIGINT NOT NULL,
                blocked BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(blocker, blocked)
            )
        """)

        # Chat messages
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id BIGSERIAL PRIMARY KEY,
                match_id BIGINT NOT NULL,
                sender_id BIGINT NOT NULL,
                message TEXT NOT NULL,
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Kunlik limitlar
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_limits (
                id BIGSERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE NOT NULL,
                likes_used INTEGER DEFAULT 0,
                messages_used INTEGER DEFAULT 0,
                super_likes_used INTEGER DEFAULT 0,
                limit_date DATE DEFAULT CURRENT_DATE
            )
        """)

        # Referral rewards
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS referral_rewards (
                id BIGSERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE NOT NULL,
                referral_count INTEGER DEFAULT 0,
                unlimited_until TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Referral tracking
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id BIGSERIAL PRIMARY KEY,
                referrer_id BIGINT NOT NULL,
                referred_id BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(referred_id)
            )
        """)

        # Guruhga a'zo bo'lishlarini kuzatish
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS group_members (
                id BIGSERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE NOT NULL,
                invited_by BIGINT,
                joined_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Guruhga odam qo'shishlarini kuzatish
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS group_invites (
                id BIGSERIAL PRIMARY KEY,
                inviter_id BIGINT NOT NULL,
                invited_id BIGINT NOT NULL,
                invited_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(inviter_id, invited_id)
            )
        """)

        # Pending xabarlar — match bo'lmasa ham yuborilgan xabarlar
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS pending_messages (
                id BIGSERIAL PRIMARY KEY,
                from_user BIGINT NOT NULL,
                to_user BIGINT NOT NULL,
                message TEXT NOT NULL,
                is_delivered BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # MIGRATION: Bir tomonlama like asosida yaratilgan "yetim" matchlarni o'chirish.
        # Match faqat ikki tomonlama like bo'lganda yaratilishi kerak.
        # Bu avvalgi versiyada noto'g'ri yaratilgan matchlarni tozalaydi.
        await conn.execute("""
            DELETE FROM matches
            WHERE NOT EXISTS (
                SELECT 1 FROM likes l1
                WHERE l1.from_user = matches.user1 AND l1.to_user = matches.user2
            )
            OR NOT EXISTS (
                SELECT 1 FROM likes l2
                WHERE l2.from_user = matches.user2 AND l2.to_user = matches.user1
            )
        """)

    finally:
        await conn.close()


# ========== TIL FUNKSIYALARI ==========
async def get_user_language(telegram_id):
    """Foydalanuvchining tilini olish"""
    conn = await get_db()
    try:
        row = await conn.fetchrow(
            "SELECT language FROM users WHERE telegram_id = $1",
            telegram_id
        )
        if row and row['language']:
            return row['language']
        return 'uz'  # default
    finally:
        await conn.close()


async def set_user_language(telegram_id, language):
    """Foydalanuvchining tilini saqlash"""
    conn = await get_db()
    try:
        # Avval user borligini tekshirish
        row = await conn.fetchrow(
            "SELECT telegram_id FROM users WHERE telegram_id = $1",
            telegram_id
        )
        if row:
            await conn.execute(
                "UPDATE users SET language = $1 WHERE telegram_id = $2",
                language, telegram_id
            )
        else:
            # Yangi user yaratish (faqat til bilan)
            await conn.execute(
                "INSERT INTO users (telegram_id, language) VALUES ($1, $2)",
                telegram_id, language
            )
        return True
    except Exception as e:
        print(f"Error setting language: {e}")
        return False
    finally:
        await conn.close()


# ========== DAILY LIMITS ==========
async def get_daily_limits(telegram_id):
    conn = await get_db()
    try:
        row = await conn.fetchrow(
            "SELECT likes_used, messages_used, super_likes_used, limit_date FROM daily_limits WHERE telegram_id = $1",
            telegram_id
        )
        today = date.today()

        if row:
            if row['limit_date'] < today:
                await conn.execute(
                    """UPDATE daily_limits
                       SET likes_used = 0, messages_used = 0, super_likes_used = 0, limit_date = $1
                       WHERE telegram_id = $2""",
                    today, telegram_id
                )
                return {'likes_used': 0, 'messages_used': 0, 'super_likes_used': 0}
            return {
                'likes_used': row['likes_used'],
                'messages_used': row['messages_used'],
                'super_likes_used': row['super_likes_used']
            }
        else:
            await conn.execute(
                "INSERT INTO daily_limits (telegram_id, likes_used, messages_used, super_likes_used, limit_date) VALUES ($1, 0, 0, 0, $2)",
                telegram_id, today
            )
            return {'likes_used': 0, 'messages_used': 0, 'super_likes_used': 0}
    finally:
        await conn.close()


async def is_unlimited(telegram_id):
    conn = await get_db()
    try:
        row = await conn.fetchrow(
            "SELECT unlimited_until FROM referral_rewards WHERE telegram_id = $1",
            telegram_id
        )
        if row and row['unlimited_until']:
            return row['unlimited_until'] > datetime.now()
        return False
    finally:
        await conn.close()


async def is_female_user(telegram_id):
    """Foydalanuvchi ayol ekanligini tekshirish — ayollar uchun limit yo'q"""
    conn = await get_db()
    try:
        row = await conn.fetchrow(
            "SELECT gender FROM users WHERE telegram_id = $1",
            telegram_id
        )
        if row and row['gender'] == 'ayol':
            return True
        return False
    finally:
        await conn.close()


async def is_male_user(telegram_id):
    """Foydalanuvchi erkak ekanligini tekshirish — guruhga qo'shish tugmasi faqat erkaklar uchun chiqadi"""
    conn = await get_db()
    try:
        row = await conn.fetchrow(
            "SELECT gender FROM users WHERE telegram_id = $1",
            telegram_id
        )
        if row and row['gender'] == 'erkak':
            return True
        return False
    finally:
        await conn.close()


async def check_and_increment_limit(telegram_id, limit_type):
    # Ayol foydalanuvchilar uchun hech qanday limit yo'q
    if await is_female_user(telegram_id):
        return True

    unlimited = await is_unlimited(telegram_id)
    if unlimited:
        return True

    limits = await get_daily_limits(telegram_id)

    MAX_LIKES = 25
    MAX_MESSAGES = 10
    MAX_SUPER_LIKES = 10

    if limit_type == 'likes':
        if limits['likes_used'] >= MAX_LIKES:
            return False
        await _increment_limit(telegram_id, 'likes_used')
        return True
    elif limit_type == 'messages':
        if limits['messages_used'] >= MAX_MESSAGES:
            return False
        await _increment_limit(telegram_id, 'messages_used')
        return True
    elif limit_type == 'super_likes':
        if limits['super_likes_used'] >= MAX_SUPER_LIKES:
            return False
        await _increment_limit(telegram_id, 'super_likes_used')
        return True

    return False


async def _increment_limit(telegram_id, column):
    conn = await get_db()
    try:
        await conn.execute(
            f"""UPDATE daily_limits
                SET {column} = {column} + 1
                WHERE telegram_id = $1""",
            telegram_id
        )
    finally:
        await conn.close()


async def get_limit_status(telegram_id):
    # Ayol foydalanuvchilar uchun har doim limitsiz
    if await is_female_user(telegram_id):
        return {
            'unlimited': True,
            'is_female': True,
            'likes_remaining': 999,
            'messages_remaining': 999,
            'super_likes_remaining': 999,
            'likes_used': 0,
            'messages_used': 0,
            'super_likes_used': 0,
        }

    unlimited = await is_unlimited(telegram_id)
    if unlimited:
        return {
            'unlimited': True,
            'is_female': False,
            'likes_remaining': 999,
            'messages_remaining': 999,
            'super_likes_remaining': 999
        }
    limits = await get_daily_limits(telegram_id)
    MAX_LIKES = 25
    MAX_MESSAGES = 10
    MAX_SUPER_LIKES = 10

    return {
        'unlimited': False,
        'is_female': False,
        'likes_used': limits['likes_used'],
        'likes_remaining': max(0, MAX_LIKES - limits['likes_used']),
        'messages_used': limits['messages_used'],
        'messages_remaining': max(0, MAX_MESSAGES - limits['messages_used']),
        'super_likes_used': limits['super_likes_used'],
        'super_likes_remaining': max(0, MAX_SUPER_LIKES - limits['super_likes_used'])
    }


# ========== REFERRAL REWARDS ==========
async def process_referral(referrer_id, referred_id):
    conn = await get_db()
    try:
        existing = await conn.fetchrow(
            "SELECT id FROM referrals WHERE referred_id = $1", referred_id
        )
        if existing:
            return False, "Bu foydalanuvchi avval referral qilgan."

        if referrer_id == referred_id:
            return False, "O'zingizni qo'sha olmaysiz."

        await conn.execute(
            "INSERT INTO referrals (referrer_id, referred_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            referrer_id, referred_id
        )

        await conn.execute("""
            INSERT INTO referral_rewards (telegram_id, referral_count, updated_at)
            VALUES ($1, 1, NOW())
            ON CONFLICT (telegram_id) DO UPDATE SET
                referral_count = referral_rewards.referral_count + 1,
                updated_at = NOW()
        """, referrer_id)

        row = await conn.fetchrow(
            "SELECT referral_count FROM referral_rewards WHERE telegram_id = $1",
            referrer_id
        )
        count = row['referral_count'] if row else 0

        if count == 5:
            until = datetime.now() + timedelta(days=7)
            await conn.execute(
                "UPDATE referral_rewards SET unlimited_until = $1 WHERE telegram_id = $2",
                until, referrer_id
            )
            return True, f"🎉 Tabriklaymiz! {count} ta odam qo'shdingiz. 1 hafta limitsiz foydalanish!"
        elif count == 10:
            until = datetime.now() + timedelta(days=30)
            await conn.execute(
                "UPDATE referral_rewards SET unlimited_until = $1 WHERE telegram_id = $2",
                until, referrer_id
            )
            return True, f"🎉 Ajoyib! {count} ta odam qo'shdingiz. 1 oy limitsiz foydalanish!"

        return True, f"✅ {count} ta odam qo'shildi. 5 tagacha: 1 hafta, 10 tagacha: 1 oy limitsiz."
    finally:
        await conn.close()


async def get_referral_status(telegram_id):
    conn = await get_db()
    try:
        row = await conn.fetchrow(
            "SELECT referral_count, unlimited_until FROM referral_rewards WHERE telegram_id = $1",
            telegram_id
        )
        if row:
            return {
                'referral_count': row['referral_count'],
                'unlimited_until': row['unlimited_until'].isoformat() if row['unlimited_until'] else None,
                'is_unlimited': row['unlimited_until'] > datetime.now() if row['unlimited_until'] else False
            }
        return {'referral_count': 0, 'unlimited_until': None, 'is_unlimited': False}
    finally:
        await conn.close()


async def get_referral_link(telegram_id, bot_username):
    return f"https://t.me/{bot_username}?start=ref_{telegram_id}"


# ========== USER FUNCTIONS ==========
async def save_user(telegram_id, data):
    conn = await get_db()
    try:
        await conn.execute("""
            INSERT INTO users (telegram_id, username, full_name, gender, age, city, about, interests, zodiac, goals, photo_file_id, photo_base64, region, country, only_serious_men)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
            ON CONFLICT (telegram_id) DO UPDATE SET
                username = EXCLUDED.username,
                full_name = EXCLUDED.full_name,
                gender = EXCLUDED.gender,
                age = EXCLUDED.age,
                city = EXCLUDED.city,
                about = EXCLUDED.about,
                interests = EXCLUDED.interests,
                zodiac = EXCLUDED.zodiac,
                goals = EXCLUDED.goals,
                photo_file_id = EXCLUDED.photo_file_id,
                photo_base64 = EXCLUDED.photo_base64,
                region = EXCLUDED.region,
                country = EXCLUDED.country,
                only_serious_men = EXCLUDED.only_serious_men,
                is_active = TRUE
        """,
            telegram_id,
            data.get("username"),
            data.get("full_name"),
            data.get("gender"),
            data.get("age"),
            data.get("city"),
            data.get("about"),
            data.get("interests", []),
            data.get("zodiac"),
            data.get("goals", []),
            data.get("photo_file_id"),
            data.get("photo_base64"),
            data.get("region"),
            data.get("country", "Oʻzbekiston"),
            bool(data.get("only_serious_men", False))
        )
        return True
    except Exception as e:
        print(f"Error saving user: {e}")
        return False
    finally:
        await conn.close()


async def get_user(telegram_id):
    conn = await get_db()
    try:
        row = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", telegram_id)
        if row:
            return dict(row)
        return None
    finally:
        await conn.close()


ZODIAC_COMPAT = {
    "qoy":         ["arslon", "oqotar", "egizak", "qovga"],
    "buzoq":       ["sunbula", "qisqichbaqa", "tarozi", "baliq"],
    "egizak":      ["tarozi", "qovga", "qoy", "arslon"],
    "qisqichbaqa": ["chayon", "baliq", "buzoq", "sunbula"],
    "arslon":      ["qoy", "oqotar", "egizak", "tarozi"],
    "sunbula":     ["buzoq", "qisqichbaqa", "tarozi", "chayon"],
    "tarozi":      ["egizak", "qovga", "arslon", "oqotar"],
    "chayon":      ["qisqichbaqa", "baliq", "sunbula", "tog_echkisi"],
    "oqotar":      ["qoy", "arslon", "tarozi", "qovga"],
    "tog_echkisi": ["buzoq", "sunbula", "chayon", "baliq"],
    "qovga":       ["egizak", "tarozi", "oqotar", "qoy"],
    "baliq":       ["qisqichbaqa", "chayon", "buzoq", "tog_echkisi"],
}

def zodiac_compatibility_percent(z1_key, z2_key):
    """Ikki burj o'rtasidagi moslik foizini qaytaradi (45-98%)."""
    if not z1_key or not z2_key:
        return None
    if z1_key == z2_key:
        return 72
    compat = ZODIAC_COMPAT.get(z1_key, [])
    if z2_key == compat[0] if compat else False:
        return 98
    elif z2_key in (compat[1:2] if len(compat) > 1 else []):
        return 91
    elif z2_key in (compat[2:3] if len(compat) > 2 else []):
        return 84
    elif z2_key in (compat[3:] if len(compat) > 3 else []):
        return 78
    else:
        return 52

async def search_users(telegram_id, filters):
    conn = await get_db()
    try:
        blocked_ids = await conn.fetch(
            "SELECT blocked FROM blocks WHERE blocker = $1 UNION SELECT blocker FROM blocks WHERE blocked = $1",
            telegram_id
        )
        excluded = [r["blocked"] for r in blocked_ids] + [telegram_id]

        # Qidirayotgan foydalanuvchining ma'lumotlari
        searcher_goals = filters.pop('searcher_goals', []) or []
        searcher_is_serious = 'goal_jiddiy' in searcher_goals
        searcher_zodiac_key = filters.pop('searcher_zodiac_key', None)
        searcher_gender = filters.pop('searcher_gender', None)

        query = """
            SELECT telegram_id, username, full_name, gender, age, city, about, interests, zodiac, goals, photo_file_id, photo_base64
            FROM users
            WHERE telegram_id != ALL($1::bigint[])
            AND is_active = TRUE
            AND (
                only_serious_men = FALSE OR only_serious_men IS NULL
                OR (only_serious_men = TRUE AND $2 = TRUE)
            )
        """
        params = [excluded, searcher_is_serious]
        idx = 3

        # Xuddi jins qidiruvini bloklash: erkak erkakni, ayol ayolni qidira olmaydi
        if searcher_gender:
            query += f" AND gender != ${idx}"
            params.append(searcher_gender)
            idx += 1

        if filters.get("gender"):
            # Gender filtr faqat qidirayotganniki bilan zid bo'lsa ishlaydi
            # (masalan erkak ayol qidirsa, gender='ayol' filtrlanadi — bu to'g'ri)
            query += f" AND gender = ${idx}"
            params.append(filters["gender"])
            idx += 1

        if filters.get("age_from"):
            query += f" AND age >= ${idx}"
            params.append(int(filters["age_from"]))
            idx += 1

        if filters.get("age_to"):
            query += f" AND age <= ${idx}"
            params.append(int(filters["age_to"]))
            idx += 1

        if filters.get("city"):
            # Tuman yoki viloyat bo'yicha ILIKE qidirish
            query += f" AND city ILIKE ${idx}"
            params.append(f"%{filters['city']}%")
            idx += 1

        if filters.get('central_asia'):
            # Butun Markaziy Osiyo bo'yicha qidirish
            query += f" AND country = ANY(${idx}::text[])"
            params.append(CENTRAL_ASIA_COUNTRIES)
            idx += 1
        elif filters.get('country'):
            query += f" AND country ILIKE ${idx}"
            params.append(f"%{filters['country']}%")
            idx += 1

        if filters.get("goals"):
            query += f" AND goals && ${idx}::text[]"
            params.append(filters["goals"])
            idx += 1

        if filters.get("interests"):
            query += f" AND interests && ${idx}::text[]"
            params.append(filters["interests"])
            idx += 1

        if filters.get("name"):
            query += f" AND full_name ILIKE ${idx}"
            params.append(f"%{filters['name']}%")
            idx += 1

        if filters.get("zodiac"):
            query += f" AND zodiac ILIKE ${idx}"
            params.append(f"%{filters['zodiac']}%")
            idx += 1

        query += " LIMIT 50"
        rows = await conn.fetch(query, *params)

        match_rows = await conn.fetch(
            "SELECT user1, user2 FROM matches WHERE user1 = $1 OR user2 = $1",
            telegram_id
        )
        match_ids = set()
        for mr in match_rows:
            other = mr['user1'] if mr['user2'] == telegram_id else mr['user2']
            match_ids.add(other)

        result = []
        for row in rows:
            user = dict(row)
            user['can_write'] = user['telegram_id'] in match_ids
            # Burj moslik foizini hisoblash
            if searcher_zodiac_key and user.get('zodiac'):
                candidate_key = ZODIAC_NAME_TO_KEY.get(
                    str(user['zodiac']).lower().replace('\u2018', "'").replace('\u2019', "'").replace('`', "'").replace('\u02bb', "'")
                )
                user['zodiac_match_percent'] = zodiac_compatibility_percent(searcher_zodiac_key, candidate_key)
            else:
                user['zodiac_match_percent'] = None
            result.append(user)
        return result
    finally:
        await conn.close()


# Markaziy Osiyo davlatlari
CENTRAL_ASIA_COUNTRIES = [
    'O\'zbekiston', 'Ozbekiston', 'Uzbekistan', 'Ўзбекистон', 'Узбекистан',
    'Qozog\'iston', 'Qozogiston', 'Kazakhstan', 'Казахстан', 'Қазақстан',
    'Qirg\'iziston', 'Kyrgyzstan', 'Кыргызстан', 'Қырғызстан', 'Киргизстан',
    'Tojikiston', 'Tajikistan', 'Таджикистан', 'Тоҷикистон',
    'Turkmaniston', 'Turkmenistan', 'Туркменистан', 'Türkmenistan',
]

# Burj nomlari
ZODIAC_KEY_TO_NAMES = {
    "qoy": ["Qo'y", "Qo'y (Aries)", "Aries", "♈", "qoy", "qo'y", "qo`y"],
    "buzoq": ["Buqa", "Buzoq", "Buqa (Taurus)", "Taurus", "♉", "buzoq", "buqa"],
    "egizak": ["Egizak", "Egizaklar", "Egizaklar (Gemini)", "Gemini", "♊", "egizak", "egizaklar"],
    "qisqichbaqa": ["Qisqichbaqa", "Qisqichbaqa (Cancer)", "Cancer", "♋", "qisqichbaqa"],
    "arslon": ["Arslon", "Sher", "Sher (Leo)", "Leo", "♌", "arslon", "sher"],
    "sunbula": ["Sunbula", "Qiz", "Qiz (Virgo)", "Virgo", "♍", "sunbula", "qiz"],
    "tarozi": ["Tarozi", "Tarozi (Libra)", "Libra", "♎", "tarozi"],
    "chayon": ["Chayon", "Chayonlar", "Chayonlar (Scorpio)", "Scorpio", "♏", "chayon", "chayonlar"],
    "oqotar": ["O'qotar", "Yoy", "Yoy (Sagittarius)", "Sagittarius", "♐", "oqotar", "yoy"],
    "tog_echkisi": ["Tog' echkisi", "Tog' echkisi (Capricorn)", "Capricorn", "♑", "tog echkisi", "tog' echkisi", "togʻ echkisi"],
    "qovga": ["Qovg'a", "Qovunchi", "Qovunchi (Aquarius)", "Aquarius", "♒", "qovga", "qovg'a", "qovgʻa", "qovunchi"],
    "baliq": ["Baliq", "Baliq (Pisces)", "Pisces", "♓", "baliq"],
}

ZODIAC_NAME_TO_KEY = {}
for key, names in ZODIAC_KEY_TO_NAMES.items():
    for name in names:
        ZODIAC_NAME_TO_KEY[name.lower().replace('’', "'").replace('`', "'").replace('ʻ', "'")] = key


def normalize_zodiac_name(value):
    if not value:
        return None
    text = str(value)
    text = text.replace('’', "'").replace('`', "'").replace('ʻ', "'")
    text = text.replace('♈', '').replace('♉', '').replace('♊', '')
    text = text.replace('♋', '').replace('♌', '').replace('♍', '')
    text = text.replace('♎', '').replace('♏', '').replace('♐', '')
    text = text.replace('♑', '').replace('♒', '').replace('♓', '')
    text = text.replace('(', ' ').replace(')', ' ')
    text = text.lower().strip()
    text = ' '.join(text.split())
    return ZODIAC_NAME_TO_KEY.get(text) or ZODIAC_NAME_TO_KEY.get(text.replace("'", ''))


async def search_users_by_zodiac(telegram_id, filters):
    conn = await get_db()
    try:
        blocked_ids = await conn.fetch(
            "SELECT blocked FROM blocks WHERE blocker = $1 UNION SELECT blocker FROM blocks WHERE blocked = $1",
            telegram_id
        )
        excluded = [r["blocked"] for r in blocked_ids] + [telegram_id]

        zodiac_keys = filters.get("zodiac_keys", [])
        zodiac_names = filters.get("zodiac_names", [])

        all_names = set()

        if zodiac_keys:
            for key in zodiac_keys:
                names = ZODIAC_KEY_TO_NAMES.get(key, [])
                all_names.update(names)

        for name in zodiac_names:
            key = normalize_zodiac_name(name)
            if key:
                all_names.update(ZODIAC_KEY_TO_NAMES.get(key, []))
            else:
                all_names.add(name)

        if not all_names:
            for key in zodiac_keys:
                all_names.update(ZODIAC_KEY_TO_NAMES.get(key, []))

        zodiac_names = list(all_names)

        if not zodiac_names:
            return []

        # Qidirayotgan foydalanuvchining o'z maqsadlari
        searcher_goals = filters.pop('searcher_goals', []) or []
        searcher_is_serious = 'goal_jiddiy' in searcher_goals

        query = """
            SELECT telegram_id, username, full_name, gender, age, city, about, interests, zodiac, goals, photo_file_id, photo_base64
            FROM users
            WHERE telegram_id != ALL($1::bigint[])
            AND is_active = TRUE
            AND zodiac IS NOT NULL
            AND (
                only_serious_men = FALSE OR only_serious_men IS NULL
                OR (only_serious_men = TRUE AND $2 = TRUE)
            )
        """
        params = [excluded, searcher_is_serious]
        idx = 3

        like_conditions = []
        for name in zodiac_names:
            like_conditions.append(f"zodiac ILIKE ${idx}")
            params.append(f"%{name}%")
            idx += 1

        if like_conditions:
            query += " AND (" + " OR ".join(like_conditions) + ")"

        if filters.get('gender'):
            query += f" AND gender = ${idx}"
            params.append(filters['gender'])
            idx += 1

        if filters.get('central_asia'):
            query += f" AND country = ANY(${idx}::text[])"
            params.append(CENTRAL_ASIA_COUNTRIES)
            idx += 1
        elif filters.get('country'):
            query += f" AND country ILIKE ${idx}"
            params.append(f"%{filters['country']}%")
            idx += 1

        if filters.get('city'):
            query += f" AND city ILIKE ${idx}"
            params.append(f"%{filters['city']}%")
            idx += 1

        query += " LIMIT 50"
        rows = await conn.fetch(query, *params)

        match_rows = await conn.fetch(
            "SELECT user1, user2 FROM matches WHERE user1 = $1 OR user2 = $1",
            telegram_id
        )
        match_ids = set()
        for mr in match_rows:
            other = mr['user1'] if mr['user2'] == telegram_id else mr['user2']
            match_ids.add(other)

        result = []
        for row in rows:
            user = dict(row)
            user['can_write'] = user['telegram_id'] in match_ids
            result.append(user)
        return result
    finally:
        await conn.close()


async def add_like(from_user, to_user, is_super=False):
    """Like yuboradi. Faqat mutual like bo'lsagina match yaratiladi.
    Mutual like bo'lsa True, aks holda False qaytaradi."""
    conn = await get_db()
    try:
        await conn.execute(
            "INSERT INTO likes (from_user, to_user, is_super) VALUES ($1, $2, $3) ON CONFLICT (from_user, to_user) DO UPDATE SET is_super = EXCLUDED.is_super",
            from_user, to_user, is_super
        )
        # Mutual like tekshirish
        mutual = await conn.fetchrow(
            "SELECT id FROM likes WHERE from_user = $1 AND to_user = $2",
            to_user, from_user
        )
        # Faqat mutual bo'lsa match yaratamiz
        if mutual is not None:
            u1, u2 = min(from_user, to_user), max(from_user, to_user)
            await conn.execute(
                "INSERT INTO matches (user1, user2) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                u1, u2
            )
        return mutual is not None
    finally:
        await conn.close()


async def get_match_id(user1, user2):
    conn = await get_db()
    try:
        u1, u2 = min(user1, user2), max(user1, user2)
        row = await conn.fetchrow(
            "SELECT id FROM matches WHERE user1 = $1 AND user2 = $2",
            u1, u2
        )
        return row['id'] if row else None
    finally:
        await conn.close()


async def block_user(blocker, blocked):
    conn = await get_db()
    try:
        await conn.execute(
            "INSERT INTO blocks (blocker, blocked) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            blocker, blocked
        )
    finally:
        await conn.close()


async def get_all_users():
    conn = await get_db()
    try:
        rows = await conn.fetch(
            "SELECT telegram_id, username, full_name, gender, age, city, about, interests, zodiac, goals, photo_file_id, photo_base64, invited_friends, created_at "
            "FROM users WHERE is_active = TRUE ORDER BY created_at DESC"
        )
        return [dict(row) for row in rows]
    finally:
        await conn.close()


async def get_user_stats():
    conn = await get_db()
    try:
        row = await conn.fetchrow(
            "SELECT COUNT(*) AS total, "
            "COUNT(*) FILTER (WHERE gender = 'erkak') AS male, "
            "COUNT(*) FILTER (WHERE gender = 'ayol') AS female, "
            "AVG(age) AS avg_age "
            "FROM users "
            "WHERE is_active = TRUE"
        )
        return dict(row) if row else {'total': 0, 'male': 0, 'female': 0, 'avg_age': None}
    finally:
        await conn.close()


async def get_top_cities(limit=10):
    conn = await get_db()
    try:
        rows = await conn.fetch(
            "SELECT city, COUNT(*) AS count FROM users "
            "WHERE city IS NOT NULL AND city <> '' AND is_active = TRUE "
            "GROUP BY city ORDER BY count DESC LIMIT $1",
            limit
        )
        return [dict(row) for row in rows]
    finally:
        await conn.close()


async def can_write(from_user, to_user):
    conn = await get_db()
    try:
        match = await conn.fetchrow(
            "SELECT id FROM matches WHERE (user1 = $1 AND user2 = $2) OR (user1 = $2 AND user2 = $1)",
            from_user, to_user
        )
        return match is not None
    finally:
        await conn.close()


async def increment_super_like_usage(from_user):
    conn = await get_db()
    try:
        await conn.execute(
            "UPDATE users SET super_likes_used = COALESCE(super_likes_used, 0) + 1 WHERE telegram_id = $1",
            from_user
        )
    finally:
        await conn.close()


# ========== CHAT & MATCH FUNCTIONS ==========
async def get_pending_likes(telegram_id):
    conn = await get_db()
    try:
        rows = await conn.fetch("""
            SELECT u.telegram_id, u.username, u.full_name, u.gender, u.age, u.city,
            u.interests, u.zodiac, u.goals, u.photo_file_id, u.photo_base64, l.created_at
            FROM likes l
            JOIN users u ON u.telegram_id = l.from_user
            WHERE l.to_user = $1
            AND NOT EXISTS (
                SELECT 1 FROM likes l2
                WHERE l2.from_user = $1 AND l2.to_user = l.from_user
            )
            ORDER BY l.created_at DESC
        """, telegram_id)
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def accept_like(telegram_id, from_user):
    conn = await get_db()
    try:
        like = await conn.fetchrow(
            "SELECT id FROM likes WHERE from_user = $1 AND to_user = $2",
            from_user, telegram_id
        )
        if not like:
            return None

        u1, u2 = min(from_user, telegram_id), max(from_user, telegram_id)
        row = await conn.fetchrow(
            "INSERT INTO matches (user1, user2) VALUES ($1, $2) ON CONFLICT DO NOTHING RETURNING id",
            u1, u2
        )
        if not row:
            row = await conn.fetchrow(
                "SELECT id FROM matches WHERE user1 = $1 AND user2 = $2", u1, u2
            )
        return row['id'] if row else None
    finally:
        await conn.close()


async def reject_like(telegram_id, from_user):
    conn = await get_db()
    try:
        result = await conn.execute(
            "DELETE FROM likes WHERE from_user = $1 AND to_user = $2",
            from_user, telegram_id
        )
        return result == 'DELETE 1'
    finally:
        await conn.close()


async def get_matches(telegram_id):
    """Foydalanuvchining barcha chat suhbatlarini olish.
    Matches jadvalidagi + pending xabar yuborilgan suhbatlar."""
    conn = await get_db()
    try:
        rows = await conn.fetch("""
            SELECT m.id as match_id, m.created_at as matched_at,
            u.telegram_id, u.username, u.full_name, u.gender, u.age, u.city,
            u.interests, u.zodiac, u.goals, u.photo_file_id, u.photo_base64
            FROM matches m
            JOIN users u ON (
                CASE
                    WHEN m.user1 = $1 THEN m.user2 = u.telegram_id
                    ELSE m.user1 = u.telegram_id
                END
            )
            WHERE m.user1 = $1 OR m.user2 = $1
            ORDER BY m.created_at DESC
        """, telegram_id)
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def create_match(user1, user2):
    conn = await get_db()
    try:
        u1, u2 = min(user1, user2), max(user1, user2)
        row = await conn.fetchrow(
            "INSERT INTO matches (user1, user2) VALUES ($1, $2) ON CONFLICT DO NOTHING RETURNING id",
            u1, u2
        )
        if not row:
            row = await conn.fetchrow(
                "SELECT id FROM matches WHERE user1 = $1 AND user2 = $2", u1, u2
            )
        return row['id'] if row else None
    finally:
        await conn.close()


async def get_chat_messages(match_id, limit=50):
    conn = await get_db()
    try:
        rows = await conn.fetch(
            "SELECT * FROM chat_messages WHERE match_id = $1 ORDER BY created_at DESC LIMIT $2",
            match_id, limit
        )
        return [dict(r) for r in rows][::-1]
    finally:
        await conn.close()


async def send_chat_message(match_id, sender_id, message):
    conn = await get_db()
    try:
        await conn.execute(
            "INSERT INTO chat_messages (match_id, sender_id, message) VALUES ($1, $2, $3)",
            match_id, sender_id, message
        )
        return True
    except Exception:
        return False
    finally:
        await conn.close()


# ========== PENDING MESSAGES ==========
async def save_pending_message(from_user, to_user, message):
    """Match bo'lmasa ham xabarni saqlaydi."""
    conn = await get_db()
    try:
        await conn.execute(
            "INSERT INTO pending_messages (from_user, to_user, message) VALUES ($1, $2, $3)",
            from_user, to_user, message
        )
        return True
    except Exception:
        return False
    finally:
        await conn.close()


async def get_pending_messages_for_match(match_id):
    """Match uchun pending xabarlarni oladi va ularni chat_messages ga ko'chiradi."""
    conn = await get_db()
    try:
        # Match ma'lumotlarini olamiz
        match_row = await conn.fetchrow(
            "SELECT user1, user2 FROM matches WHERE id = $1", match_id
        )
        if not match_row:
            return 0

        user1 = match_row['user1']
        user2 = match_row['user2']

        # Ikkala tomonning pending xabarlarini olamiz
        pending_rows = await conn.fetch("""
            SELECT id, from_user, message, created_at FROM pending_messages
            WHERE ((from_user = $1 AND to_user = $2) OR (from_user = $2 AND to_user = $1))
            AND is_delivered = FALSE
            ORDER BY created_at ASC
        """, user1, user2)

        count = 0
        for row in pending_rows:
            # chat_messages ga ko'chiramiz
            await conn.execute(
                "INSERT INTO chat_messages (match_id, sender_id, message, created_at) VALUES ($1, $2, $3, $4)",
                match_id, row['from_user'], row['message'], row['created_at']
            )
            # Delivered deb belgilaymiz
            await conn.execute(
                "UPDATE pending_messages SET is_delivered = TRUE WHERE id = $1",
                row['id']
            )
            count += 1
        return count
    except Exception as e:
        print(f"get_pending_messages_for_match error: {e}")
        return 0
    finally:
        await conn.close()


async def deliver_pending_messages_to_match(from_user, to_user):
    """from_user → to_user ga yuborilgan pending xabarlarni match chat_messages ga o'tkazadi."""
    conn = await get_db()
    try:
        u1, u2 = min(from_user, to_user), max(from_user, to_user)
        match_row = await conn.fetchrow(
            "SELECT id FROM matches WHERE user1 = $1 AND user2 = $2", u1, u2
        )
        if not match_row:
            return 0

        match_id = match_row['id']

        # Pending xabarlarni olamiz (ikki tomonlama)
        pending_rows = await conn.fetch("""
            SELECT id, from_user, message, created_at FROM pending_messages
            WHERE ((from_user = $1 AND to_user = $2) OR (from_user = $2 AND to_user = $1))
            AND is_delivered = FALSE
            ORDER BY created_at ASC
        """, from_user, to_user)

        count = 0
        for row in pending_rows:
            await conn.execute(
                "INSERT INTO chat_messages (match_id, sender_id, message, created_at) VALUES ($1, $2, $3, $4)",
                match_id, row['from_user'], row['message'], row['created_at']
            )
            await conn.execute(
                "UPDATE pending_messages SET is_delivered = TRUE WHERE id = $1",
                row['id']
            )
            count += 1
        return count
    except Exception as e:
        print(f"deliver_pending_messages_to_match error: {e}")
        return 0
    finally:
        await conn.close()


async def mark_messages_read(match_id, reader_id):
    conn = await get_db()
    try:
        await conn.execute(
            "UPDATE chat_messages SET is_read = TRUE WHERE match_id = $1 AND sender_id != $2",
            match_id, reader_id
        )
    finally:
        await conn.close()


# ========== REFERRAL FUNCTIONS ==========
async def register_invite(inviter_id, invited_id):
    return await process_referral(inviter_id, invited_id)


async def get_invite_count(telegram_id):
    conn = await get_db()
    try:
        row = await conn.fetchrow(
            "SELECT referral_count FROM referral_rewards WHERE telegram_id = $1", telegram_id
        )
        return row["referral_count"] if row else 0
    finally:
        await conn.close()


async def set_group_subscribed(telegram_id, subscribed=True):
    conn = await get_db()
    try:
        await conn.execute(
            "UPDATE users SET group_subscribed = $1 WHERE telegram_id = $2",
            subscribed, telegram_id
        )
        return True
    except Exception:
        return False
    finally:
        await conn.close()


async def get_group_subscribed(telegram_id):
    conn = await get_db()
    try:
        row = await conn.fetchrow(
            "SELECT group_subscribed, friends_invited FROM users WHERE telegram_id = $1",
            telegram_id
        )
        if row:
            return {'group_subscribed': row['group_subscribed'], 'friends_invited': row['friends_invited']}
        return {'group_subscribed': False, 'friends_invited': 0}
    finally:
        await conn.close()


async def get_group_invite_count(telegram_id):
    conn = await get_db()
    try:
        row = await conn.fetchrow(
            "SELECT COUNT(*) as count FROM group_invites WHERE inviter_id = $1",
            telegram_id
        )
        return row['count'] if row else 0
    finally:
        await conn.close()


async def get_group_invitees(telegram_id):
    conn = await get_db()
    try:
        rows = await conn.fetch("""
            SELECT u.telegram_id, u.full_name, u.username
            FROM group_invites gi
            JOIN users u ON u.telegram_id = gi.invited_id
            WHERE gi.inviter_id = $1
            ORDER BY gi.invited_at DESC
        """, telegram_id)
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def record_group_invite(inviter_id, invited_id):
    conn = await get_db()
    try:
        await conn.execute("""
            INSERT INTO group_invites (inviter_id, invited_id)
            VALUES ($1, $2)
            ON CONFLICT DO NOTHING
        """, inviter_id, invited_id)
        return True, "Guruhga odam qo'shildi."
    except Exception as e:
        return False, str(e)
    finally:
        await conn.close()


async def record_group_join(telegram_id, invited_by=None):
    conn = await get_db()
    try:
        await conn.execute("""
            INSERT INTO group_members (telegram_id, invited_by)
            VALUES ($1, $2)
            ON CONFLICT (telegram_id) DO NOTHING
        """, telegram_id, invited_by)
    except Exception:
        pass
    finally:
        await conn.close()

# ========== VERIFIKATSIYA FUNKSIYALARI ==========

async def save_selfie_and_verify(telegram_id: int, selfie_base64: str):
    """Selfieni saqlaydi va foydalanuvchini verified deb belgilaydi (avtomatik)."""
    conn = await get_db()
    try:
        await conn.execute("""
            UPDATE users
            SET selfie_base64 = $1,
                is_verified = TRUE,
                verified_at = NOW()
            WHERE telegram_id = $2
        """, selfie_base64, telegram_id)
        return True
    except Exception as e:
        return False
    finally:
        await conn.close()


async def get_verification_status(telegram_id: int):
    """Foydalanuvchining verifikatsiya holatini qaytaradi."""
    conn = await get_db()
    try:
        row = await conn.fetchrow("""
            SELECT is_verified, verified_at FROM users WHERE telegram_id = $1
        """, telegram_id)
        if row:
            return {'is_verified': row['is_verified'], 'verified_at': row['verified_at']}
        return {'is_verified': False, 'verified_at': None}
    except Exception:
        return {'is_verified': False, 'verified_at': None}
    finally:
        await conn.close()
