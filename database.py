import asyncpg
import json
import random
from datetime import datetime, date, timedelta
from config import DATABASE_URL

# ========== CONNECTION POOL ==========
# Har bir so'rov uchun yangi TCP/SSL ulanish ochish o'rniga (bu yuqori
# yuklamada Postgres'ning max_connections limitini tugatib, sock_connect
# TimeoutError'larga olib kelgan edi), bitta umumiy pool ishlatiladi.
_pool = None


async def init_pool():
    """Ilova ishga tushganda BIR MARTA chaqiriladi va umumiy pool yaratadi."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=2,
            max_size=20,
            max_inactive_connection_lifetime=300,
            command_timeout=30,
            timeout=10,
        )
    return _pool


async def close_pool():
    """Ilova to'xtaganda pool'ni tozalab yopadi."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def get_db():
    """
    Pool'dan bo'sh connection oladi (yangi TCP ulanish ochmaydi).
    Qaytarilgan connection ishlatib bo'lingach albatta release_db(conn)
    chaqirilishi shart (conn.close() emas!).
    """
    global _pool
    if _pool is None:
        await init_pool()
    return await _pool.acquire()


async def release_db(conn):
    """Connection'ni pool'ga qaytaradi. Har bir get_db() dan keyin finally blokida chaqiriladi."""
    global _pool
    if conn is None:
        return
    if _pool is not None:
        try:
            await _pool.release(conn)
        except Exception:
            pass

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

        # ===== KO'RINISH REJIMI (kunduzgi/tungi) =====
        await conn.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS theme TEXT DEFAULT 'light'
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

        # So'zlashuv tili (anketada foydalanuvchi tanlaydigan til: uz, ru, kk, ky, kaa, tg, en).
        # Endi foydalanuvchi bir nechta til tanlashi mumkin, shuning uchun ustun TEXT[] (massiv).
        await conn.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS spoken_language TEXT[]
        """)
        # Eski bazalarda bu ustun oddiy TEXT bo'lib, bitta til saqlangan bo'lishi mumkin -
        # shu holatni TEXT[] ga xavfsiz o'giramiz (mavjud qiymat 1 elementli massivga aylanadi).
        await conn.execute("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'users' AND column_name = 'spoken_language' AND data_type <> 'ARRAY'
                ) THEN
                    ALTER TABLE users ALTER COLUMN spoken_language TYPE TEXT[] USING
                        CASE WHEN spoken_language IS NULL OR spoken_language = '' THEN NULL
                             ELSE ARRAY[spoken_language]::TEXT[] END;
                END IF;
            END $$;
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
        # Botdan foydalanmagan/ro'yxatdan o'tmagan odamlar ham guruhga qo'shilgani
        # uchun hisoblanadi va ko'rsatiladi - shu maqsadda ularning ismi/username'ini
        # Telegram'dan kelgan holida saqlab qo'yamiz (agar eski jadval bo'lsa ham qo'shamiz).
        await conn.execute("""
            ALTER TABLE group_invites ADD COLUMN IF NOT EXISTS invited_full_name TEXT
        """)
        await conn.execute("""
            ALTER TABLE group_invites ADD COLUMN IF NOT EXISTS invited_username TEXT
        """)

        # Har bir foydalanuvchi uchun shaxsiy guruh taklifnoma havolasi.
        # Bu havola orqali kim qo'shilsa, aynan shu foydalanuvchi nomidan hisoblanadi
        # (statik/umumiy havolada Telegram kim taklif qilganini bilmaydi).
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_invite_links (
                id BIGSERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE NOT NULL,
                invite_link TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
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

        # ===== ANONIM SUHBATDOSH ("Anonim chat") =====
        # Foydalanuvchi istalgan vaqt "Qidirish" tugmasini bosib, tizim ikki mos
        # foydalanuvchini anonim ravishda ulaydi (on-demand navbat, anon_queue_matcher).
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS anon_matches (
                id BIGSERIAL PRIMARY KEY,
                user_a BIGINT NOT NULL,
                user_b BIGINT NOT NULL,
                match_date DATE NOT NULL DEFAULT CURRENT_DATE,
                status TEXT NOT NULL DEFAULT 'pending',
                user_a_accepted BOOLEAN,
                user_b_accepted BOOLEAN,
                user_a_reveal BOOLEAN DEFAULT FALSE,
                user_b_reveal BOOLEAN DEFAULT FALSE,
                revealed_match_id BIGINT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS anon_chat_messages (
                id BIGSERIAL PRIMARY KEY,
                anon_match_id BIGINT NOT NULL,
                sender_id BIGINT NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Har bir kun uchun moslashtirish faqat bir marta ishga tushishini nazorat qilish
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS anon_match_runs (
                run_date DATE PRIMARY KEY,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Istalgan vaqtda ("on-demand") anonim suhbatdosh qidirish uchun navbat.
        # Foydalanuvchi tugma bosib shu jadvalga qo'shiladi, fon jarayoni
        # (anon_queue_matcher) navbatdagilarni muntazam ravishda juftlab boradi.
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS anon_queue (
                telegram_id BIGINT PRIMARY KEY,
                joined_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_anon_matches_user_a ON anon_matches(user_a)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_anon_matches_user_b ON anon_matches(user_b)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_anon_chat_messages_match ON anon_chat_messages(anon_match_id)
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

        # ========== SHIKOYAT (REPORT) VA BAN TIZIMI ==========
        await conn.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS violation_count INTEGER DEFAULT 0
        """)
        await conn.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS banned_until TIMESTAMP
        """)
        await conn.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS ban_reason TEXT
        """)

        # ========== KO'RINUVCHANLIK (VISIBILITY) TIZIMI ==========
        # Ban tugagandan keyingi "nazorat davri" va haftalik TOP-10 orqali
        # reyting tiklanishi, shuningdek TOP-10 foydalanuvchilarni ko'proq
        # ko'rsatish (boost) uchun ishlatiladi.
        await conn.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS visibility_multiplier DOUBLE PRECISION DEFAULT 1.0
        """)
        await conn.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS probation_until TIMESTAMP
        """)
        await conn.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS weekly_top10_count INTEGER DEFAULT 0
        """)
        await conn.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS last_top10_week TEXT
        """)
        await conn.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS is_boosted BOOLEAN DEFAULT FALSE
        """)
        # Haftalik visibility/top10 hisoblash faqat bir marta ishlashini
        # ta'minlash uchun (anon_match_runs bilan bir xil naqsh)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS visibility_runs (
                week_start TEXT PRIMARY KEY,
                run_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id BIGSERIAL PRIMARY KEY,
                reporter_id BIGINT NOT NULL,
                reported_id BIGINT NOT NULL,
                category TEXT NOT NULL
            )
        """)
        # Jadval avvalroq (masalan yarim muvaffaqiyatli deploy tufayli) boshqa
        # ustunlar bilan yaratilgan bo'lishi mumkin - shu sabab har bir ustunni
        # alohida ALTER TABLE orqali qo'shamiz (CREATE TABLE IF NOT EXISTS
        # jadval mavjud bo'lsa ustunlarni qo'shib bermaydi).
        await conn.execute("""
            ALTER TABLE reports ADD COLUMN IF NOT EXISTS description TEXT
        """)
        await conn.execute("""
            ALTER TABLE reports ADD COLUMN IF NOT EXISTS source TEXT
        """)
        await conn.execute("""
            ALTER TABLE reports ADD COLUMN IF NOT EXISTS context_snapshot JSONB
        """)
        await conn.execute("""
            ALTER TABLE reports ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'pending'
        """)
        await conn.execute("""
            ALTER TABLE reports ADD COLUMN IF NOT EXISTS ai_verdict JSONB
        """)
        await conn.execute("""
            ALTER TABLE reports ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()
        """)
        await conn.execute("""
            ALTER TABLE reports ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMP
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_reports_reported ON reports(reported_id)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_reports_reporter ON reports(reporter_id)
        """)

    finally:
        await release_db(conn)


# ========== SHIKOYAT / BAN FUNKSIYALARI ==========
# Progressiv ban muddatlari (kun hisobida). Indeks = tasdiqlangan buzilish soni - 1.
BAN_TIER_DAYS = [1, 3, 7, 30, 365]

# ========== KO'RINUVCHANLIK (VISIBILITY) SOZLAMALARI ==========
# Ban tugagandan keyin necha kun "nazorat davri" (probation) davom etadi.
PROBATION_DAYS = 14
# Nazorat davrida qidiruvda ko'rinish og'irligi (1.0 = oddiy, kichikroq = kamroq ko'rinadi).
PROBATION_VISIBILITY_MULTIPLIER = 0.3
# Nazorat davrida haftalik TOP-10 ga necha marta kirsa, to'liq ko'rinish tiklanadi.
TOP10_GRADUATION_COUNT = 2
# TOP-10 (haftalik eng ko'p layk olganlar) foydalanuvchilari uchun qidiruvda
# ko'proq ko'rsatilish (boost) og'irligi.
TOP10_BOOST_MULTIPLIER = 1.7
# Oddiy (jarimasiz, boostsiz) foydalanuvchi og'irligi.
DEFAULT_VISIBILITY_MULTIPLIER = 1.0


async def create_report(reporter_id, reported_id, category, description, source, context_snapshot):
    """Yangi shikoyat yozuvini yaratadi va uning id'sini qaytaradi.
    context_snapshot - masalan {'messages': [...], 'photo_base64': '...'} - AI tekshiruvi uchun
    kerakli holatni saqlab qoladi (anonim chatda xabarlar keyinchalik o'chirilishi mumkin)."""
    conn = await get_db()
    try:
        row = await conn.fetchrow("""
            INSERT INTO reports (reporter_id, reported_id, category, description, source, context_snapshot)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb)
            RETURNING id
        """, reporter_id, reported_id, category, description, source,
            json.dumps(context_snapshot or {}))
        return row['id'] if row else None
    finally:
        await release_db(conn)


async def set_report_result(report_id, status, ai_verdict=None):
    """AI/admin tekshiruvidan so'ng shikoyat holatini yakunlaydi."""
    conn = await get_db()
    try:
        await conn.execute("""
            UPDATE reports
            SET status = $1, ai_verdict = $2::jsonb, resolved_at = NOW()
            WHERE id = $3
        """, status, json.dumps(ai_verdict or {}), report_id)
        return True
    finally:
        await release_db(conn)


async def get_ban_info(telegram_id):
    """Foydalanuvchining joriy ban holatini qaytaradi.
    Muddati tugagan bo'lsa - avtomatik faollashtiriladi (banned_until tozalanadi)
    va foydalanuvchi uchun "nazorat davri" (probation) boshlanadi - shu davrda
    anketasi qidiruv natijalarida kamroq ko'rsatiladi (visibility_multiplier pasaytiriladi)."""
    conn = await get_db()
    try:
        row = await conn.fetchrow("""
            SELECT violation_count, banned_until, ban_reason FROM users WHERE telegram_id = $1
        """, telegram_id)
        if not row:
            return {'is_banned': False, 'banned_until': None, 'ban_reason': None, 'violation_count': 0}

        banned_until = row['banned_until']
        if banned_until and banned_until > datetime.utcnow():
            return {
                'is_banned': True,
                'banned_until': banned_until.isoformat(),
                'ban_reason': row['ban_reason'],
                'violation_count': row['violation_count'] or 0,
            }

        # Muddat tugagan - tozalab qo'yamiz (lekin violation_count tarix uchun saqlanadi)
        # va "nazorat davri"ni ishga tushiramiz (agar hali boshlanmagan bo'lsa)
        if banned_until:
            await conn.execute("""
                UPDATE users
                SET banned_until = NULL,
                    probation_until = COALESCE(probation_until, NOW() + ($1 || ' days')::interval),
                    visibility_multiplier = LEAST(COALESCE(visibility_multiplier, 1.0), $2),
                    weekly_top10_count = 0,
                    last_top10_week = NULL
                WHERE telegram_id = $3
            """, str(PROBATION_DAYS), PROBATION_VISIBILITY_MULTIPLIER, telegram_id)
        return {
            'is_banned': False,
            'banned_until': None,
            'ban_reason': None,
            'violation_count': row['violation_count'] or 0,
        }
    finally:
        await release_db(conn)


async def register_violation_and_ban(telegram_id, category, severe=False):
    """Tasdiqlangan buzilishni hisoblaydi va progressiv ban qo'llaydi.
    `severe=True` bo'lsa (masalan kichik yoshdagilarga oid kontent), birinchi
    holatdayoq eng qattiq (doimiy) chora qo'llanadi."""
    conn = await get_db()
    try:
        row = await conn.fetchrow(
            "SELECT violation_count FROM users WHERE telegram_id = $1", telegram_id
        )
        current = (row['violation_count'] if row else 0) or 0
        new_count = current + 1

        if severe:
            days = BAN_TIER_DAYS[-1]
        else:
            tier_index = min(new_count - 1, len(BAN_TIER_DAYS) - 1)
            days = BAN_TIER_DAYS[tier_index]

        banned_until = datetime.utcnow() + timedelta(days=days)
        reason = f"{category} ({new_count}-marta tasdiqlangan buzilish)"

        await conn.execute("""
            UPDATE users
            SET violation_count = $1, banned_until = $2, ban_reason = $3
            WHERE telegram_id = $4
        """, new_count, banned_until, reason, telegram_id)

        return {
            'violation_count': new_count,
            'days': days,
            'banned_until': banned_until.isoformat(),
            'ban_reason': reason,
        }
    finally:
        await release_db(conn)


async def recalculate_visibility_and_top10():
    """Haftalik ishga tushiriladigan funksiya (scheduler orqali):
    1) Shu haftaning TOP-10 (eng ko'p layk olgan) foydalanuvchilarini topadi.
    2) Ular uchun visibility_multiplier'ni oshiradi (boost) - qidiruvda ko'proq
       ko'rinishi uchun.
    3) Agar TOP-10dagi foydalanuvchi "nazorat davri"da (probation) bo'lsa,
       weekly_top10_count'ni oshiradi; TOP10_GRADUATION_COUNT marta kirgach
       nazorat davri butunlay bekor qilinadi (visibility_multiplier = 1.0).
    4) TOP-10dan tushib qolgan, lekin oldin boost qilingan foydalanuvchilarning
       boostini asta-sekin (keskin emas) pasaytiradi.
    5) Muddati tugagan probation'larni ham tozalaydi.
    Bir xil haftada ikki marta ishga tushsa ham xato hisobga olinmasligi uchun
    `last_top10_week` ustunidan foydalaniladi.
    """
    conn = await get_db()
    try:
        week_start = (datetime.utcnow() - timedelta(days=datetime.utcnow().weekday())).strftime('%Y-%m-%d')

        # 1) Shu haftaning TOP-10 (layk soni bo'yicha) foydalanuvchilari
        top10_rows = await conn.fetch("""
            SELECT u.telegram_id,
                   COUNT(l.id) AS like_count
            FROM users u
            LEFT JOIN likes l ON l.to_user = u.telegram_id
                AND l.created_at >= date_trunc('week', NOW())
            WHERE u.is_active = TRUE
            GROUP BY u.telegram_id
            ORDER BY like_count DESC
            LIMIT 10
        """)
        top10_ids = [r['telegram_id'] for r in top10_rows if r['like_count'] and r['like_count'] > 0]

        # 2) va 3) TOP-10dagilarni yangilash
        if top10_ids:
            rows = await conn.fetch("""
                SELECT telegram_id, probation_until, weekly_top10_count, last_top10_week
                FROM users WHERE telegram_id = ANY($1::bigint[])
            """, top10_ids)
            for row in rows:
                tid = row['telegram_id']
                in_probation = row['probation_until'] and row['probation_until'] > datetime.utcnow()
                already_counted_this_week = row['last_top10_week'] == week_start

                if in_probation:
                    new_count = (row['weekly_top10_count'] or 0)
                    if not already_counted_this_week:
                        new_count += 1

                    if new_count >= TOP10_GRADUATION_COUNT:
                        # Nazorat davridan "bitirdi" - reytingi hamma qatori tiklanadi
                        await conn.execute("""
                            UPDATE users
                            SET probation_until = NULL,
                                visibility_multiplier = $1,
                                weekly_top10_count = $2,
                                last_top10_week = $3
                            WHERE telegram_id = $4
                        """, TOP10_BOOST_MULTIPLIER, new_count, week_start, tid)
                    else:
                        await conn.execute("""
                            UPDATE users
                            SET weekly_top10_count = $1,
                                last_top10_week = $2
                            WHERE telegram_id = $3
                        """, new_count, week_start, tid)
                else:
                    # Probationda emas - to'g'ridan-to'g'ri boost beriladi
                    await conn.execute("""
                        UPDATE users
                        SET visibility_multiplier = $1,
                            is_boosted = TRUE,
                            last_top10_week = $2
                        WHERE telegram_id = $3
                    """, TOP10_BOOST_MULTIPLIER, week_start, tid)

        # 4) TOP-10dan tushib qolganlarning boostini asta-sekin pasaytirish
        # (keskin 1.0 ga tushirilmaydi - bir necha bosqichda pasayadi)
        await conn.execute("""
            UPDATE users
            SET visibility_multiplier = GREATEST(1.0, visibility_multiplier - 0.3),
                is_boosted = FALSE
            WHERE is_boosted = TRUE
              AND NOT (telegram_id = ANY($1::bigint[]))
        """, top10_ids or [0])

        # 5) Muddati tugagan probation'larni tozalash (agar TOP-10 orqali
        # tiklanmagan bo'lsa ham, vaqt o'tishi bilan avtomatik tugaydi)
        await conn.execute("""
            UPDATE users
            SET probation_until = NULL,
                visibility_multiplier = 1.0,
                weekly_top10_count = 0,
                last_top10_week = NULL
            WHERE probation_until IS NOT NULL AND probation_until <= NOW()
        """)

        return {'top10_ids': top10_ids, 'week_start': week_start}
    finally:
        await release_db(conn)


async def get_recent_reports_for_pair(reporter_id, reported_id, hours=24):
    """Bir xil voqea uchun takroriy (dublikat) shikoyatlarni aniqlash uchun -
    so'nggi N soat ichida shu juftlik bo'yicha allaqachon shikoyat borligini tekshiradi."""
    conn = await get_db()
    try:
        row = await conn.fetchrow("""
            SELECT id FROM reports
            WHERE reporter_id = $1 AND reported_id = $2
              AND created_at > NOW() - ($3 || ' hours')::interval
            ORDER BY created_at DESC LIMIT 1
        """, reporter_id, reported_id, str(hours))
        return row['id'] if row else None
    finally:
        await release_db(conn)


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
        await release_db(conn)


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
        await release_db(conn)


# ========== KO'RINISH REJIMI (KUNDUZGI/TUNGI) ==========
async def get_user_theme(telegram_id):
    """Foydalanuvchining tanlagan ko'rinish rejimini olish ('light' yoki 'dark')."""
    conn = await get_db()
    try:
        row = await conn.fetchrow(
            "SELECT theme FROM users WHERE telegram_id = $1",
            telegram_id
        )
        if row and row['theme'] in ('light', 'dark'):
            return row['theme']
        return 'light'  # default - hozirgi kunduzgi ko'rinish
    finally:
        await release_db(conn)


async def set_user_theme(telegram_id, theme):
    """Foydalanuvchining ko'rinish rejimini saqlash."""
    if theme not in ('light', 'dark'):
        return False
    conn = await get_db()
    try:
        row = await conn.fetchrow(
            "SELECT telegram_id FROM users WHERE telegram_id = $1",
            telegram_id
        )
        if row:
            await conn.execute(
                "UPDATE users SET theme = $1 WHERE telegram_id = $2",
                theme, telegram_id
            )
        else:
            await conn.execute(
                "INSERT INTO users (telegram_id, theme) VALUES ($1, $2)",
                telegram_id, theme
            )
        return True
    except Exception as e:
        print(f"Error setting theme: {e}")
        return False
    finally:
        await release_db(conn)


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
        await release_db(conn)


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
        await release_db(conn)


async def is_female_user(telegram_id):
    """Foydalanuvchi ayol ekanligini tekshirish — ayollar uchun limit yo'q"""
    conn = await get_db()
    try:
        row = await conn.fetchrow(
            "SELECT gender FROM users WHERE telegram_id = $1",
            telegram_id
        )
        if row and normalize_gender(row['gender']) == 'ayol':
            return True
        return False
    finally:
        await release_db(conn)


async def is_male_user(telegram_id):
    """Foydalanuvchi erkak ekanligini tekshirish — guruhga qo'shish tugmasi faqat erkaklar uchun chiqadi"""
    conn = await get_db()
    try:
        row = await conn.fetchrow(
            "SELECT gender FROM users WHERE telegram_id = $1",
            telegram_id
        )
        if row and normalize_gender(row['gender']) == 'erkak':
            return True
        return False
    finally:
        await release_db(conn)


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
        await release_db(conn)


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
        await release_db(conn)


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
        await release_db(conn)


async def get_referral_link(telegram_id, bot_username):
    return f"https://t.me/{bot_username}?start=ref_{telegram_id}"


# ========== USER FUNCTIONS ==========
def normalize_gender(value):
    """Turli jins nomlarini bot ichidagi yagona formatga o'zgartiradi."""
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    text = value.strip().lower()
    if not text:
        return None

    normalized = text.replace(' ', '').replace('_', '').replace('-', '')
    aliases = {
        'erkak': 'erkak',
        'male': 'erkak',
        'man': 'erkak',
        'boy': 'erkak',
        'm': 'erkak',
        'ayol': 'ayol',
        'female': 'ayol',
        'woman': 'ayol',
        'girl': 'ayol',
        'qiz': 'ayol',
        'f': 'ayol',
        'kiz': 'ayol',
    }
    return aliases.get(normalized) or aliases.get(text) or normalized


def build_gender_filter(value):
    normalized = normalize_gender(value)
    return [normalized] if normalized else []


def build_gender_match_values(value):
    normalized = normalize_gender(value)
    if normalized == 'erkak':
        return ['erkak', 'male', 'man', 'boy', 'm']
    if normalized == 'ayol':
        return ['ayol', 'female', 'woman', 'girl', 'qiz', 'kiz', 'f']
    return []


async def save_user(telegram_id, data):
    conn = await get_db()
    try:
        gender = normalize_gender(data.get("gender"))
        data = dict(data)
        data["gender"] = gender
        # spoken_language endi bir nechta til bo'lishi mumkin (TEXT[] ustun).
        # Eski mijozlar hali bitta stringni yuborishi mumkin - shuni ham ro'yxatga aylantiramiz.
        raw_lang = data.get("spoken_language")
        if raw_lang is None:
            data["spoken_language"] = None
        elif isinstance(raw_lang, (list, tuple)):
            data["spoken_language"] = [str(c) for c in raw_lang if c] or None
        else:
            data["spoken_language"] = [str(raw_lang)] if raw_lang else None
        await conn.execute("""
            INSERT INTO users (telegram_id, username, full_name, gender, age, city, about, interests, zodiac, goals, photo_file_id, photo_base64, region, country, only_serious_men, spoken_language)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
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
                spoken_language = EXCLUDED.spoken_language,
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
            bool(data.get("only_serious_men", False)),
            data.get("spoken_language")
        )
        return True
    except Exception as e:
        print(f"Error saving user: {e}")
        return False
    finally:
        await release_db(conn)


async def get_user(telegram_id):
    conn = await get_db()
    try:
        row = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", telegram_id)
        if row:
            user = dict(row)
            user['gender'] = normalize_gender(user.get('gender'))
            return user
        return None
    finally:
        await release_db(conn)


async def search_users(telegram_id, filters):
    conn = await get_db()
    try:
        blocked_ids = await conn.fetch(
            "SELECT blocked FROM blocks WHERE blocker = $1 UNION SELECT blocker FROM blocks WHERE blocked = $1",
            telegram_id
        )
        excluded = [r["blocked"] for r in blocked_ids] + [telegram_id]

        searcher_goals = filters.pop('searcher_goals', []) or []
        searcher_is_serious = 'goal_jiddiy' in searcher_goals
        # Jins va burj — moslik foizi va xuddi jins bloklash uchun
        searcher_gender = filters.pop('searcher_gender', None)
        searcher_zodiac_key = filters.pop('searcher_zodiac_key', None)
        # "Barchasi" tanlanganda xuddi jinsdagilarni chiqarmaslik
        exclude_gender = filters.pop('exclude_gender', None)
        normalized_gender = build_gender_filter(filters.get('gender'))
        if normalized_gender:
            filters['gender'] = normalized_gender[0]
        elif 'gender' in filters:
            filters.pop('gender')
        if exclude_gender:
            exclude_gender = normalize_gender(exclude_gender)

        query = """
            SELECT telegram_id, username, full_name, gender, age, city, about,
                   interests, zodiac, goals, photo_file_id, photo_base64, spoken_language,
                   COALESCE(visibility_multiplier, 1.0) AS visibility_multiplier,
                   COALESCE(is_boosted, FALSE) AS is_boosted
            FROM users
            WHERE telegram_id != ALL($1::bigint[])
            AND is_active = TRUE
            -- Faqat anketasi to'liq to'ldirilgan (til tanlangandan keyin yaratilgan
            -- "bo'sh" qatorlar bu yerda chiqmasligi kerak)
            AND full_name IS NOT NULL AND full_name != ''
            AND age IS NOT NULL
            AND gender IS NOT NULL AND gender != ''
            AND city IS NOT NULL AND city != ''
            AND spoken_language IS NOT NULL AND cardinality(spoken_language) > 0
            AND (
                (photo_base64 IS NOT NULL AND photo_base64 != '')
                OR (photo_file_id IS NOT NULL AND photo_file_id != '')
            )
            -- Hozir ban qilingan foydalanuvchilar boshqalarning qidiruvida
            -- umuman ko'rinmaydi (xavfsizlik talabi)
            AND (banned_until IS NULL OR banned_until <= NOW())
            AND (
                only_serious_men = FALSE OR only_serious_men IS NULL
                OR (only_serious_men = TRUE AND $2 = TRUE)
            )
        """
        params = [excluded, searcher_is_serious]
        idx = 3

        # Jins filtri: aniq gender= berilgan bo'lsa uni ishlatamiz
        # exclude_gender= berilgan bo'lsa (barchasi holati) xuddi jinsdagilarni chiqaramiz
        if filters.get("gender"):
            gender_values = build_gender_match_values(filters["gender"])
            if gender_values:
                query += f" AND LOWER(COALESCE(gender, '')) = ANY(${idx}::text[])"
                params.append(gender_values)
                idx += 1
            else:
                query += f" AND gender ILIKE ${idx}"
                params.append(filters["gender"])
                idx += 1
        elif exclude_gender:
            query += f" AND LOWER(COALESCE(gender, '')) != ALL(${idx}::text[])"
            params.append([exclude_gender])
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
            query += f" AND city ILIKE ${idx}"
            params.append(f"%{filters['city']}%")
            idx += 1

        if filters.get('central_asia'):
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

        if filters.get("spoken_language"):
            # Foydalanuvchi bir nechta til bilan gaplasha oladi - filtrda tanlangan
            # tillardan istalganida mos keladigan foydalanuvchilarni topamiz (overlap).
            sl = filters["spoken_language"]
            sl_list = sl if isinstance(sl, (list, tuple)) else [sl]
            query += f" AND spoken_language && ${idx}::text[]"
            params.append(list(sl_list))
            idx += 1

        if filters.get("name"):
            query += f" AND full_name ILIKE ${idx}"
            params.append(f"%{filters['name']}%")
            idx += 1

        if filters.get("zodiac"):
            query += f" AND zodiac ILIKE ${idx}"
            params.append(f"%{filters['zodiac']}%")
            idx += 1

        # Oddiy RANDOM() o'rniga vaznlangan tasodifiy tartiblash ishlatiladi:
        # visibility_multiplier yuqori bo'lgan foydalanuvchi (masalan haftalik
        # TOP-10 boosti) LIMIT 50 ichiga tushish ehtimoli yuqoriroq, past
        # bo'lgan foydalanuvchi (masalan ban tugagandan keyingi nazorat davri)
        # kamroq ehtimol bilan chiqadi.
        query += " ORDER BY RANDOM() * COALESCE(visibility_multiplier, 1.0) DESC LIMIT 50"
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
            # Ichki maydonni tashqariga chiqarmaymiz, faqat "boostlangan"
            # belgisini frontendga qoldiramiz (masalan 🔥 TOP nishonchasi uchun)
            user.pop('visibility_multiplier', None)
            user['can_write'] = user['telegram_id'] in match_ids
            # Burj moslik foizini hisoblash
            if searcher_zodiac_key and user.get('zodiac'):
                cand_key = _normalize_zodiac_for_db(user['zodiac'])
                user['zodiac_match_percent'] = _zodiac_compat_db(searcher_zodiac_key, cand_key)
            else:
                user['zodiac_match_percent'] = None
            result.append(user)
        return result
    finally:
        await release_db(conn)


def _normalize_zodiac_for_db(value):
    """Burj nomini key ga aylantiradi (database.py ichida)."""
    if not value:
        return None
    text = str(value).replace('\u2018', "'").replace('\u2019', "'").replace('`', "'").replace('\u02bb', "'")
    for sym in ('♈','♉','♊','♋','♌','♍','♎','♏','♐','♑','♒','♓'):
        text = text.replace(sym, '')
    text = text.lower().strip()
    _map = {
        'qoy': 'qoy', "qo'y": 'qoy', 'aries': 'qoy',
        'buzoq': 'buzoq', 'buqa': 'buzoq', 'taurus': 'buzoq',
        'egizak': 'egizak', 'egizaklar': 'egizak', 'gemini': 'egizak',
        'qisqichbaqa': 'qisqichbaqa', 'cancer': 'qisqichbaqa',
        'arslon': 'arslon', 'sher': 'arslon', 'leo': 'arslon',
        'sunbula': 'sunbula', 'qiz': 'sunbula', 'virgo': 'sunbula',
        'tarozi': 'tarozi', 'libra': 'tarozi',
        'chayon': 'chayon', 'chayonlar': 'chayon', 'scorpio': 'chayon',
        'oqotar': 'oqotar', "o'qotar": 'oqotar', 'yoy': 'oqotar', 'sagittarius': 'oqotar',
        "tog' echkisi": 'tog_echkisi', 'tog echkisi': 'tog_echkisi', 'capricorn': 'tog_echkisi',
        "qovg'a": 'qovga', 'qovga': 'qovga', 'qovunchi': 'qovga', 'aquarius': 'qovga',
        'baliq': 'baliq', 'pisces': 'baliq',
    }
    return _map.get(text)


_ZODIAC_PCT = {
    ('qoy','arslon'):98,('qoy','oqotar'):95,('qoy','egizak'):91,('qoy','tarozi'):78,('qoy','qovga'):82,('qoy','qoy'):72,
    ('buzoq','sunbula'):98,('buzoq','qisqichbaqa'):95,('buzoq','tog_echkisi'):92,('buzoq','baliq'):85,('buzoq','buzoq'):70,
    ('egizak','tarozi'):97,('egizak','qovga'):93,('egizak','arslon'):88,('egizak','egizak'):68,
    ('qisqichbaqa','chayon'):98,('qisqichbaqa','baliq'):96,('qisqichbaqa','sunbula'):80,('qisqichbaqa','qisqichbaqa'):73,
    ('arslon','oqotar'):96,('arslon','tarozi'):85,('arslon','arslon'):65,
    ('sunbula','tog_echkisi'):97,('sunbula','chayon'):88,('sunbula','sunbula'):71,
    ('tarozi','qovga'):95,('tarozi','tarozi'):69,
    ('chayon','baliq'):97,('chayon','tog_echkisi'):84,('chayon','chayon'):74,
    ('oqotar','qovga'):90,('oqotar','oqotar'):67,
    ('tog_echkisi','baliq'):86,('tog_echkisi','tog_echkisi'):72,
    ('qovga','qovga'):66,('baliq','baliq'):75,
}

def _zodiac_compat_db(k1, k2):
    if not k1 or not k2:
        return None
    return _ZODIAC_PCT.get((k1,k2)) or _ZODIAC_PCT.get((k2,k1)) or 50


# Har bir burj uchun eng mos keladigan 3 ta burj (bot.py'dagi ZODIAC_COMPATIBILITY
# bilan bir xil ma'lumot - shu yerda alohida saqlanadi, chunki bot.py database.py'ni
# import qiladi va teskarisini qilib bo'lmaydi). Anonim on-demand navbatda
# (match_from_queue) suhbatdoshni birinchi navbatda shu ro'yxat bo'yicha qidirish
# uchun ishlatiladi.
ZODIAC_MOS_BURJLAR = {
    "qoy": ["arslon", "egizak", "oqotar"],
    "buzoq": ["sunbula", "qisqichbaqa", "tog_echkisi"],
    "egizak": ["qoy", "tarozi", "qovga"],
    "qisqichbaqa": ["buzoq", "baliq", "chayon"],
    "arslon": ["qoy", "egizak", "tarozi"],
    "sunbula": ["buzoq", "tog_echkisi", "chayon"],
    "tarozi": ["egizak", "arslon", "qovga"],
    "chayon": ["qisqichbaqa", "baliq", "buzoq"],
    "oqotar": ["qoy", "arslon", "qovga"],
    "tog_echkisi": ["buzoq", "sunbula", "chayon"],
    "qovga": ["oqotar", "egizak", "tarozi"],
    "baliq": ["buzoq", "qisqichbaqa", "chayon"],
}


def _zodiac_is_good_match(z1, z2):
    """Ikki burj bir-biriga (o'zaro) mos keladimi: bir xil burj yoki
    ZODIAC_MOS_BURJLAR ro'yxatidagi 3 ta mos burjdan biri bo'lsa True.
    Burjlardan biri noma'lum bo'lsa - False (keyin fallback bosqichida
    baribir juftlanadi, lekin ustuvorlik berilmaydi)."""
    if not z1 or not z2:
        return False
    if z1 == z2:
        return True
    if z2 in ZODIAC_MOS_BURJLAR.get(z1, []):
        return True
    if z1 in ZODIAC_MOS_BURJLAR.get(z2, []):
        return True
    return False


# Markaziy Osiyo davlatlari
# MUHIM: apostrof belgisining bir nechta varianti qo'shilgan (' U+0027, ʻ U+02BB,
# ʼ U+02BC, ’ U+2019, ` backtick), chunki frontend (app.js) davlat nomlarini
# "Oʻzbekiston" kabi maxsus apostrof (U+02BB) bilan yuboradi, oddiy apostrof (U+0027)
# bilan emas. Shu farq sababli "= ANY(...)" solishtiruvi mos kelmay, O'zbekiston (va
# boshqa apostrofli davlatlar) markaziy osiyo bo'yicha qidiruv natijalaridan tushib
# qolgan edi.
CENTRAL_ASIA_COUNTRIES = [
    "O'zbekiston", 'Oʻzbekiston', 'Oʼzbekiston', 'O’zbekiston', 'O`zbekiston',
    'Ozbekiston', 'Uzbekistan', 'Ўзбекистон', 'Узбекистан',
    "Qozog'iston", 'Qozogʻiston', 'Qozogʼiston', 'Qozog’iston', 'Qozog`iston',
    'Qozogiston', 'Kazakhstan', 'Казахстан', 'Қазақстан',
    "Qirg'iziston", 'Qirgʻiziston', 'Qirgʼiziston', 'Qirg’iziston', 'Qirg`iziston',
    'Kyrgyzstan', 'Кыргызстан', 'Қырғызстан', 'Киргизстан',
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
        searcher_zodiac_key = filters.pop('searcher_zodiac_key', None)
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
            SELECT telegram_id, username, full_name, gender, age, city, about, interests, zodiac, goals, photo_file_id, photo_base64, spoken_language,
                   COALESCE(visibility_multiplier, 1.0) AS visibility_multiplier,
                   COALESCE(is_boosted, FALSE) AS is_boosted
            FROM users
            WHERE telegram_id != ALL($1::bigint[])
            AND is_active = TRUE
            AND full_name IS NOT NULL AND full_name != ''
            AND age IS NOT NULL
            AND gender IS NOT NULL AND gender != ''
            AND city IS NOT NULL AND city != ''
            AND spoken_language IS NOT NULL AND cardinality(spoken_language) > 0
            AND (
                (photo_base64 IS NOT NULL AND photo_base64 != '')
                OR (photo_file_id IS NOT NULL AND photo_file_id != '')
            )
            AND zodiac IS NOT NULL
            AND (banned_until IS NULL OR banned_until <= NOW())
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
            gender_values = build_gender_match_values(filters['gender'])
            if gender_values:
                query += f" AND LOWER(COALESCE(gender, '')) = ANY(${idx}::text[])"
                params.append(gender_values)
                idx += 1
            else:
                query += f" AND gender ILIKE ${idx}"
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

        if filters.get('spoken_language'):
            # Foydalanuvchi bir nechta til bilan gaplasha oladi - filtrda tanlangan
            # tillardan istalganida mos keladigan foydalanuvchilarni topamiz (overlap).
            sl = filters['spoken_language']
            sl_list = sl if isinstance(sl, (list, tuple)) else [sl]
            query += f" AND spoken_language && ${idx}::text[]"
            params.append(list(sl_list))
            idx += 1

        query += " ORDER BY RANDOM() * COALESCE(visibility_multiplier, 1.0) DESC LIMIT 50"
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
            user.pop('visibility_multiplier', None)
            user['can_write'] = user['telegram_id'] in match_ids
            # Burj moslik foizini hisoblash
            if searcher_zodiac_key and user.get('zodiac'):
                cand_key = _normalize_zodiac_for_db(user['zodiac'])
                user['zodiac_match_percent'] = _zodiac_compat_db(searcher_zodiac_key, cand_key)
            else:
                user['zodiac_match_percent'] = None
            result.append(user)
        return result
    finally:
        await release_db(conn)


async def count_search_users(telegram_id, filters):
    """Filtrlar bo'yicha foydalanuvchilar sonini qaytaradi (statistika uchun)."""
    conn = await get_db()
    try:
        blocked_ids = await conn.fetch(
            "SELECT blocked FROM blocks WHERE blocker = $1 UNION SELECT blocker FROM blocks WHERE blocked = $1",
            telegram_id
        )
        excluded = [r["blocked"] for r in blocked_ids] + [telegram_id]

        zodiac_compat_list = filters.pop('zodiac_compat_list', None)
        searcher_zodiac = filters.pop('searcher_zodiac', None)
        zodiac_keys = []
        zodiac_names_all = []

        if zodiac_compat_list:
            for name in zodiac_compat_list:
                key = _normalize_zodiac_for_db(name)
                if key:
                    zodiac_keys.append(key)
                    zodiac_names_all.append(name)

            # Qidiruvchining o'z burjini ham qo'shamiz (mos burjlar + o'z burji)
            own_key = _normalize_zodiac_for_db(searcher_zodiac) if searcher_zodiac else None
            if own_key and own_key not in zodiac_keys:
                zodiac_keys.append(own_key)
                zodiac_names_all.append(own_key)

        searcher_goals = filters.pop('searcher_goals', []) or []
        searcher_is_serious = 'goal_jiddiy' in searcher_goals

        query = """
            SELECT COUNT(*) AS total
            FROM users
            WHERE telegram_id != ALL($1::bigint[])
            AND is_active = TRUE
            AND full_name IS NOT NULL AND full_name != ''
            AND age IS NOT NULL
            AND gender IS NOT NULL AND gender != ''
            AND city IS NOT NULL AND city != ''
            AND spoken_language IS NOT NULL AND cardinality(spoken_language) > 0
            AND (
                (photo_base64 IS NOT NULL AND photo_base64 != '')
                OR (photo_file_id IS NOT NULL AND photo_file_id != '')
            )
            AND (banned_until IS NULL OR banned_until <= NOW())
            AND (
                only_serious_men = FALSE OR only_serious_men IS NULL
                OR (only_serious_men = TRUE AND $2 = TRUE)
            )
        """
        params = [excluded, searcher_is_serious]
        idx = 3

        if filters.get("gender"):
            gender_values = build_gender_match_values(filters["gender"])
            if gender_values:
                query += f" AND LOWER(COALESCE(gender, '')) = ANY(${idx}::text[])"
                params.append(gender_values)
                idx += 1
            else:
                query += f" AND gender ILIKE ${idx}"
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
            query += f" AND city ILIKE ${idx}"
            params.append(f"%{filters['city']}%")
            idx += 1

        if filters.get('central_asia'):
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

        if filters.get("spoken_language"):
            # Foydalanuvchi bir nechta til bilan gaplasha oladi - filtrda tanlangan
            # tillardan istalganida mos keladigan foydalanuvchilarni topamiz (overlap).
            sl = filters["spoken_language"]
            sl_list = sl if isinstance(sl, (list, tuple)) else [sl]
            query += f" AND spoken_language && ${idx}::text[]"
            params.append(list(sl_list))
            idx += 1

        if filters.get("zodiac"):
            query += f" AND zodiac ILIKE ${idx}"
            params.append(f"%{filters['zodiac']}%")
            idx += 1

        # Burjga mos qidirish uchun
        if zodiac_keys:
            all_names = set(zodiac_names_all)
            for key in zodiac_keys:
                all_names.update(ZODIAC_KEY_TO_NAMES.get(key, []))
            zodiac_names_list = list(all_names)
            if zodiac_names_list:
                like_conditions = []
                for name in zodiac_names_list:
                    like_conditions.append(f"zodiac ILIKE ${idx}")
                    params.append(f"%{name}%")
                    idx += 1
                query += " AND (" + " OR ".join(like_conditions) + ")"

        if filters.get("name"):
            query += f" AND full_name ILIKE ${idx}"
            params.append(f"%{filters['name']}%")
            idx += 1

        row = await conn.fetchrow(query, *params)
        return row['total'] if row else 0
    finally:
        await release_db(conn)


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
        await release_db(conn)


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
        await release_db(conn)


async def block_user(blocker, blocked):
    conn = await get_db()
    try:
        await conn.execute(
            "INSERT INTO blocks (blocker, blocked) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            blocker, blocked
        )
    finally:
        await release_db(conn)



async def get_all_users():
    conn = await get_db()
    try:
        rows = await conn.fetch(
            "SELECT telegram_id, username, full_name, gender, age, city, about, interests, zodiac, goals, photo_file_id, photo_base64, spoken_language, invited_friends, created_at "
            "FROM users WHERE is_active = TRUE ORDER BY created_at DESC"
        )
        return [dict(row) for row in rows]
    finally:
        await release_db(conn)


async def count_incomplete_profiles(grace_hours: int = 24):
    """Anketasi to'liq to'ldirilmagan (til tanlangandan keyin yaratilgan
    "bo'sh" qatorlar) foydalanuvchilar sonini qaytaradi. grace_hours —
    hali anketani to'ldirib ulgurmagan yangi foydalanuvchilarni bexosdan
    o'chirib yubormaslik uchun berilgan muhlat.

    Majburiy maydonlar (frontenddagi anketa formasi bilan mos): full_name,
    age, gender, city, spoken_language va rasm (photo_base64 yoki
    photo_file_id). Shulardan biri ham bo'sh bo'lsa — anketa to'liq emas."""
    conn = await get_db()
    try:
        row = await conn.fetchrow(
            """
            SELECT COUNT(*) AS total FROM users
            WHERE created_at < NOW() - ($1 || ' hours')::interval
            AND (
                full_name IS NULL OR full_name = ''
                OR age IS NULL
                OR gender IS NULL OR gender = ''
                OR city IS NULL OR city = ''
                OR spoken_language IS NULL OR cardinality(spoken_language) = 0
                OR (
                    (photo_base64 IS NULL OR photo_base64 = '')
                    AND (photo_file_id IS NULL OR photo_file_id = '')
                )
            )
            """,
            str(grace_hours)
        )
        return row['total'] if row else 0
    finally:
        await release_db(conn)


async def delete_incomplete_profiles(grace_hours: int = 24):
    """Anketasi to'liq to'ldirilmagan foydalanuvchilarni bazadan butunlay
    o'chirib tashlaydi. Faqat /start bosib tilni tanlagan, lekin anketani
    hech qachon to'ldirmagan (majburiy maydonlardan hech bo'lmasa bittasi
    bo'sh) foydalanuvchilar o'chiriladi — shu bilan botda va qidiruvda doim
    faqat haqiqiy, to'liq anketali foydalanuvchilar qoladi.

    Majburiy maydonlar (frontenddagi anketa formasi bilan mos): full_name,
    age, gender, city, spoken_language va rasm (photo_base64 yoki
    photo_file_id). Shulardan biri ham bo'sh bo'lsa — anketa to'liq emas
    deb hisoblanadi va shu qator butunlay o'chiriladi.

    grace_hours: hozirgina ro'yxatdan o'ta boshlagan (anketani hali
    to'ldirib ulgurmagan) foydalanuvchini bexosdan o'chirib yubormaslik
    uchun kutish muhlati (soatlarda).

    Returns: o'chirilgan qatorlar soni.
    """
    conn = await get_db()
    try:
        deleted_ids = await conn.fetch(
            """
            DELETE FROM users
            WHERE created_at < NOW() - ($1 || ' hours')::interval
            AND (
                full_name IS NULL OR full_name = ''
                OR age IS NULL
                OR gender IS NULL OR gender = ''
                OR city IS NULL OR city = ''
                OR spoken_language IS NULL OR cardinality(spoken_language) = 0
                OR (
                    (photo_base64 IS NULL OR photo_base64 = '')
                    AND (photo_file_id IS NULL OR photo_file_id = '')
                )
            )
            RETURNING telegram_id
            """,
            str(grace_hours)
        )
        deleted_count = len(deleted_ids)
        if deleted_count:
            ids = [r['telegram_id'] for r in deleted_ids]
            # Shu foydalanuvchilarga tegishli, bog'liqlik zanjiri bo'lmagan
            # yordamchi jadvallardagi qoldiqlarni ham tozalaymiz (agar mavjud bo'lsa).
            try:
                await conn.execute("DELETE FROM daily_limits WHERE telegram_id = ANY($1::bigint[])", ids)
            except Exception:
                pass
            try:
                await conn.execute("DELETE FROM user_invite_links WHERE telegram_id = ANY($1::bigint[])", ids)
            except Exception:
                pass
        return deleted_count
    finally:
        await release_db(conn)


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
        await release_db(conn)


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
        await release_db(conn)


async def can_write(from_user, to_user):
    conn = await get_db()
    try:
        match = await conn.fetchrow(
            "SELECT id FROM matches WHERE (user1 = $1 AND user2 = $2) OR (user1 = $2 AND user2 = $1)",
            from_user, to_user
        )
        return match is not None
    finally:
        await release_db(conn)


async def increment_super_like_usage(from_user):
    conn = await get_db()
    try:
        await conn.execute(
            "UPDATE users SET super_likes_used = COALESCE(super_likes_used, 0) + 1 WHERE telegram_id = $1",
            from_user
        )
    finally:
        await release_db(conn)


# ========== CHAT & MATCH FUNCTIONS ==========
async def get_pending_likes(telegram_id):
    conn = await get_db()
    try:
        rows = await conn.fetch("""
            SELECT u.telegram_id, u.username, u.full_name, u.gender, u.age, u.city,
            u.interests, u.zodiac, u.goals, u.photo_file_id, u.photo_base64, u.spoken_language, l.created_at
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
        await release_db(conn)


async def accept_like(telegram_id, from_user):
    conn = await get_db()
    try:
        like = await conn.fetchrow(
            "SELECT id FROM likes WHERE from_user = $1 AND to_user = $2",
            from_user, telegram_id
        )
        if not like:
            return None

        # Qabul qilingan like bo'yicha o'z tomonimdan ham "like" yozuvini
        # qo'shamiz - shu orqali get_pending_likes() dagi mutual tekshiruvi
        # (NOT EXISTS) ushbu bildirishnomani ro'yxatdan olib tashlaydi.
        await conn.execute(
            "INSERT INTO likes (from_user, to_user, is_super) VALUES ($1, $2, FALSE) "
            "ON CONFLICT (from_user, to_user) DO NOTHING",
            telegram_id, from_user
        )

        u1, u2 = min(from_user, telegram_id), max(from_user, telegram_id)
        row = await conn.fetchrow(
            "INSERT INTO matches (user1, user2) VALUES ($1, $2) ON CONFLICT DO NOTHING RETURNING id",
            u1, u2
        )
        if not row:
            row = await conn.fetchrow(
                "SELECT id FROM matches WHERE user1 = $1 AND user2 = $2", u1, u2
            )
        match_id = row['id'] if row else None
        if match_id:
            # Match hosil bo'lgach, ikki tomon o'rtasidagi eski pending
            # xabarlarni (agar bo'lsa) chatga ko'chirib olamiz.
            await deliver_pending_messages_to_match(from_user, telegram_id)
        return match_id
    finally:
        await release_db(conn)


async def reject_like(telegram_id, from_user):
    conn = await get_db()
    try:
        result = await conn.execute(
            "DELETE FROM likes WHERE from_user = $1 AND to_user = $2",
            from_user, telegram_id
        )
        return result == 'DELETE 1'
    finally:
        await release_db(conn)


async def get_matches(telegram_id):
    """Foydalanuvchining barcha chat suhbatlarini olish.
    Matches jadvalidagi + pending xabar yuborilgan suhbatlar.
    Har bir suhbat uchun oxirgi xabar va o'qilmagan xabarlar soni ham qaytariladi,
    shu orqali Web App'da yangi xabar kelgani ko'rinib turadi."""
    conn = await get_db()
    try:
        rows = await conn.fetch("""
            SELECT m.id as match_id, m.created_at as matched_at,
            u.telegram_id, u.username, u.full_name, u.gender, u.age, u.city,
            u.interests, u.zodiac, u.goals, u.photo_file_id, u.photo_base64, u.spoken_language, lm.message as last_message, lm.sender_id as last_sender_id, lm.created_at as last_message_at,
            COALESCE(uc.unread_count, 0) as unread_count
            FROM matches m
            JOIN users u ON (
                CASE
                    WHEN m.user1 = $1 THEN m.user2 = u.telegram_id
                    ELSE m.user1 = u.telegram_id
                END
            )
            LEFT JOIN LATERAL (
                SELECT message, sender_id, created_at FROM chat_messages
                WHERE match_id = m.id ORDER BY created_at DESC LIMIT 1
            ) lm ON true
            LEFT JOIN LATERAL (
                SELECT COUNT(*) as unread_count FROM chat_messages
                WHERE match_id = m.id AND sender_id != $1 AND is_read = FALSE
            ) uc ON true
            WHERE m.user1 = $1 OR m.user2 = $1
            ORDER BY COALESCE(lm.created_at, m.created_at) DESC
        """, telegram_id)
        return [dict(r) for r in rows]
    finally:
        await release_db(conn)


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
        await release_db(conn)


async def get_chat_messages(match_id, limit=50):
    conn = await get_db()
    try:
        rows = await conn.fetch(
            "SELECT * FROM chat_messages WHERE match_id = $1 ORDER BY created_at DESC LIMIT $2",
            match_id, limit
        )
        return [dict(r) for r in rows][::-1]
    finally:
        await release_db(conn)


async def get_match_users(match_id):
    """Match ichidagi ikkala foydalanuvchi ID sini qaytaradi: (user1, user2) yoki None."""
    conn = await get_db()
    try:
        row = await conn.fetchrow(
            "SELECT user1, user2 FROM matches WHERE id = $1", match_id
        )
        if not row:
            return None
        return row['user1'], row['user2']
    finally:
        await release_db(conn)


async def send_chat_message(match_id, sender_id, message):
    conn = await get_db()
    try:
        row = await conn.fetchrow(
            """INSERT INTO chat_messages (match_id, sender_id, message)
               VALUES ($1, $2, $3)
               RETURNING id, match_id, sender_id, message, is_read, created_at""",
            match_id, sender_id, message
        )
        return dict(row) if row else None
    except Exception:
        return None
    finally:
        await release_db(conn)


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
        await release_db(conn)


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
        await release_db(conn)


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
        await release_db(conn)


async def mark_messages_read(match_id, reader_id):
    conn = await get_db()
    try:
        await conn.execute(
            "UPDATE chat_messages SET is_read = TRUE WHERE match_id = $1 AND sender_id != $2",
            match_id, reader_id
        )
    finally:
        await release_db(conn)


# ========== HAFTALIK KO'RINUVCHANLIK (VISIBILITY) SCHEDULERI ==========
async def has_visibility_run_this_week(week_start):
    """Berilgan hafta uchun visibility/top10 hisoboti allaqachon ishga
    tushganmi, tekshiradi (bir haftada faqat bir marta ishlashi kerak)."""
    conn = await get_db()
    try:
        row = await conn.fetchrow(
            "SELECT week_start FROM visibility_runs WHERE week_start = $1", week_start
        )
        return row is not None
    finally:
        await release_db(conn)


async def mark_visibility_run(week_start):
    conn = await get_db()
    try:
        await conn.execute(
            "INSERT INTO visibility_runs (week_start) VALUES ($1) ON CONFLICT DO NOTHING",
            week_start
        )
    finally:
        await release_db(conn)


# ========== TUNGI ANONIM CHAT ==========
async def has_anon_run_today(run_date):
    """Berilgan sana uchun moslashtirish allaqachon ishga tushganmi, tekshiradi."""
    conn = await get_db()
    try:
        row = await conn.fetchrow("SELECT run_date FROM anon_match_runs WHERE run_date = $1", run_date)
        return row is not None
    finally:
        await release_db(conn)


async def mark_anon_run(run_date):
    conn = await get_db()
    try:
        await conn.execute(
            "INSERT INTO anon_match_runs (run_date) VALUES ($1) ON CONFLICT DO NOTHING",
            run_date
        )
    finally:
        await release_db(conn)


def _anon_user_key(user):
    return {
        'id': user['telegram_id'],
        'gender': user['gender'],
        'age': user.get('age'),
        'region': (user.get('region') or '').strip().lower() if user.get('region') else None,
        'country': (user.get('country') or '').strip().lower() if user.get('country') else None,
        'zodiac': _normalize_zodiac_for_db(user.get('zodiac')),
        'goals': [g for g in (user.get('goals') or []) if g],
        'interests': [i for i in (user.get('interests') or []) if i],
        'only_serious_men': bool(user.get('only_serious_men')),
    }


def _anon_pair_score(user_a, user_b):
    score = 0
    if user_a['country'] and user_a['country'] == user_b['country']:
        score += 20
    if user_a['region'] and user_a['region'] == user_b['region']:
        score += 10

    if user_a['age'] is not None and user_b['age'] is not None:
        age_diff = abs(user_a['age'] - user_b['age'])
        if age_diff <= 2:
            score += 12
        elif age_diff <= 5:
            score += 8
        elif age_diff <= 10:
            score += 4
        elif age_diff <= 15:
            score += 1

    common_goals = set(user_a['goals']) & set(user_b['goals'])
    score += len(common_goals) * 12

    common_interests = set(user_a['interests']) & set(user_b['interests'])
    score += len(common_interests) * 5

    if user_a['zodiac'] and user_b['zodiac']:
        compat = _zodiac_compat_db(user_a['zodiac'], user_b['zodiac'])
        score += int(compat * 0.15)

    if user_a['only_serious_men'] and 'goal_jiddiy' not in user_b['goals']:
        score -= 10
    if user_b['only_serious_men'] and 'goal_jiddiy' not in user_a['goals']:
        score -= 10

    return score


async def create_daily_anon_matches(run_date):
    """Anonim chat uchun jins mos foydalanuvchilarni eng yaxshi moslik balli bilan juftlaydi.
    Bu funksiya faqat faol, profil to'liq, bloklanmagan va allaqachon match bo'lmagan foydalanuvchilarni hisobga oladi.
    Yaqinda (oxirgi 30 kun) anonim juft bo'lganlar takroran juftlanmaydi.
    Yaratilgan juftliklar ro'yxatini qaytaradi: [(user_a, user_b, anon_match_id), ...]

    Eslatma: bu funksiyaning o'zida vaqt yoki "kuniga bir marta" bo'yicha hech
    qanday cheklov yo'q — shuning uchun kunning istalgan vaqtida (masalan admin
    panel/API orqali qo'lda) xohlagancha marta chaqirilishi mumkin. "Kuniga
    faqat bir marta avtomatik ishga tushirish" cheklovi faqat
    `anon_match_scheduler`ning o'zida (has_anon_run_today orqali) qo'llaniladi
    va u faqat 21:00 dagi avtomatik ishga tegishli, qo'lda chaqirishga bu
    cheklov umuman ta'sir qilmaydi.
    """
    conn = await get_db()
    try:
        users = await conn.fetch("""
            SELECT telegram_id, gender, age, region, country, zodiac, goals, interests, only_serious_men
            FROM users
            WHERE is_active = TRUE
              AND gender IN ('erkak', 'ayol')
              AND full_name IS NOT NULL
        """)
        user_map = {r['telegram_id']: _anon_user_key(r) for r in users}
        males = [u for u in users if u['gender'] == 'erkak']
        females = [u for u in users if u['gender'] == 'ayol']

        blocked_rows = await conn.fetch(
            "SELECT blocker, blocked FROM blocks"
        )
        blocked_pairs = {(r['blocker'], r['blocked']) for r in blocked_rows}
        blocked_pairs |= {(r['blocked'], r['blocker']) for r in blocked_rows}

        match_rows = await conn.fetch("SELECT user1, user2 FROM matches")
        matched_pairs = {(r['user1'], r['user2']) for r in match_rows}
        matched_pairs |= {(r['user2'], r['user1']) for r in match_rows}

        active_anon_rows = await conn.fetch(
            "SELECT user_a, user_b FROM anon_matches WHERE status IN ('pending', 'active')"
        )
        currently_busy = set()
        for r in active_anon_rows:
            currently_busy.add(r['user_a'])
            currently_busy.add(r['user_b'])

        recent_cutoff = run_date - timedelta(days=30)
        recent_anon_rows = await conn.fetch(
            "SELECT user_a, user_b FROM anon_matches WHERE match_date >= $1",
            recent_cutoff
        )
        recent_pairs = {(r['user_a'], r['user_b']) for r in recent_anon_rows}
        recent_pairs |= {(r['user_b'], r['user_a']) for r in recent_anon_rows}

        candidates = []
        for m in males:
            if m['telegram_id'] in currently_busy:
                continue
            for f in females:
                if f['telegram_id'] in currently_busy:
                    continue
                if (m['telegram_id'], f['telegram_id']) in blocked_pairs:
                    continue
                if (m['telegram_id'], f['telegram_id']) in matched_pairs:
                    continue
                if (m['telegram_id'], f['telegram_id']) in recent_pairs:
                    continue

                score = _anon_pair_score(user_map[m['telegram_id']], user_map[f['telegram_id']])
                candidates.append((score, m['telegram_id'], f['telegram_id']))

        candidates.sort(reverse=True, key=lambda item: item[0])

        used_males = set()
        used_females = set()
        created_pairs = []
        for score, m_id, f_id in candidates:
            if score <= 0:
                break
            if m_id in used_males or f_id in used_females:
                continue
            used_males.add(m_id)
            used_females.add(f_id)
            row = await conn.fetchrow(
                """INSERT INTO anon_matches
                   (user_a, user_b, match_date, status, user_a_accepted, user_b_accepted)
                   VALUES ($1, $2, $3, 'active', TRUE, TRUE) RETURNING id""",
                m_id, f_id, run_date
            )
            created_pairs.append((m_id, f_id, row['id']))

        return created_pairs
    finally:
        await release_db(conn)


async def get_anon_reminder_recipients():
    """Kechqurungi (21:00) eslatma yuborish uchun barcha faol va profili
    to'liq bo'lgan foydalanuvchilarning telegram_id ro'yxatini qaytaradi.
    Bu yerda hech qanday juftlashtirish bo'lmaydi - eslatma faqat
    foydalanuvchini ilovani ochib, istalgan vaqt ishlaydigan qidiruvdan
    foydalanishga taklif qiladi."""
    conn = await get_db()
    try:
        rows = await conn.fetch("""
            SELECT telegram_id FROM users
            WHERE is_active = TRUE
              AND gender IN ('erkak', 'ayol')
              AND full_name IS NOT NULL
        """)
        return [r['telegram_id'] for r in rows]
    finally:
        await release_db(conn)


async def is_in_anon_queue(telegram_id):
    """Foydalanuvchi hozir on-demand anonim navbatda turgan-turmaganini tekshiradi."""
    conn = await get_db()
    try:
        row = await conn.fetchrow("SELECT telegram_id FROM anon_queue WHERE telegram_id = $1", telegram_id)
        return row is not None
    finally:
        await release_db(conn)


async def join_anon_queue(telegram_id):
    """Foydalanuvchini on-demand anonim suhbat navbatiga qo'shadi.
    Juftlashning o'zi alohida fon jarayoni (`match_from_queue`) tomonidan amalga oshiriladi."""
    conn = await get_db()
    try:
        await conn.execute(
            "INSERT INTO anon_queue (telegram_id) VALUES ($1) ON CONFLICT (telegram_id) DO NOTHING",
            telegram_id
        )
        return True
    finally:
        await release_db(conn)


async def leave_anon_queue(telegram_id):
    """Foydalanuvchini on-demand anonim suhbat navbatidan chiqaradi (bekor qilish)."""
    conn = await get_db()
    try:
        await conn.execute("DELETE FROM anon_queue WHERE telegram_id = $1", telegram_id)
        return True
    finally:
        await release_db(conn)


async def match_from_queue():
    """Navbatda turganlarni bir-biriga juftlaydi (on-demand, istalgan vaqt).

    Kuniga bir marta ishlaydigan `create_daily_anon_matches`dan farqi:
    - faqat `anon_queue`da real vaqtda turganlarni ko'rib chiqadi;
    - "so'nggi 30 kunda juft bo'lganlar" cheklovi qo'llanilmaydi, chunki
      foydalanuvchi bu safar ham o'zi xohlab navbatga turgan;
    - moslik balli eng past bo'lsa ham (hatto manfiy bo'lsa ham) juftlaydi,
      chunki maqsad - foydalanuvchini iloji boricha tezroq kimdir bilan ulash.

    Yaratilgan juftliklar ro'yxatini qaytaradi: [(user_a, user_b, anon_match_id), ...]
    """
    conn = await get_db()
    try:
        queue_rows = await conn.fetch("SELECT telegram_id FROM anon_queue ORDER BY joined_at ASC")
        if len(queue_rows) < 2:
            return []
        queue_ids = [r['telegram_id'] for r in queue_rows]

        users = await conn.fetch("""
            SELECT telegram_id, gender, age, region, country, zodiac, goals, interests, only_serious_men
            FROM users
            WHERE telegram_id = ANY($1::bigint[])
              AND is_active = TRUE
              AND gender IN ('erkak', 'ayol')
              AND full_name IS NOT NULL
        """, queue_ids)
        user_map = {r['telegram_id']: _anon_user_key(r) for r in users}

        # Profili to'liq bo'lmagan yoki faol bo'lmagan foydalanuvchilarni navbatdan chiqarib tashlaymiz
        invalid_ids = [tid for tid in queue_ids if tid not in user_map]
        if invalid_ids:
            await conn.execute("DELETE FROM anon_queue WHERE telegram_id = ANY($1::bigint[])", invalid_ids)

        males = [tid for tid in queue_ids if tid in user_map and user_map[tid]['gender'] == 'erkak']
        females = [tid for tid in queue_ids if tid in user_map and user_map[tid]['gender'] == 'ayol']
        if not males or not females:
            return []

        blocked_rows = await conn.fetch("SELECT blocker, blocked FROM blocks")
        blocked_pairs = {(r['blocker'], r['blocked']) for r in blocked_rows}
        blocked_pairs |= {(r['blocked'], r['blocker']) for r in blocked_rows}

        match_rows = await conn.fetch("SELECT user1, user2 FROM matches")
        matched_pairs = {(r['user1'], r['user2']) for r in match_rows}
        matched_pairs |= {(r['user2'], r['user1']) for r in match_rows}

        active_anon_rows = await conn.fetch(
            "SELECT user_a, user_b FROM anon_matches WHERE status IN ('pending', 'active')"
        )
        currently_busy = set()
        for r in active_anon_rows:
            currently_busy.add(r['user_a'])
            currently_busy.add(r['user_b'])

        # Allaqachon boshqa anonim suhbatga band bo'lib qolganlarni navbatdan tozalaymiz
        stale_busy_ids = [tid for tid in queue_ids if tid in currently_busy]
        if stale_busy_ids:
            await conn.execute("DELETE FROM anon_queue WHERE telegram_id = ANY($1::bigint[])", stale_busy_ids)

        candidates = []
        for m_id in males:
            if m_id in currently_busy:
                continue
            for f_id in females:
                if f_id in currently_busy:
                    continue
                if (m_id, f_id) in blocked_pairs:
                    continue
                if (m_id, f_id) in matched_pairs:
                    continue
                score = _anon_pair_score(user_map[m_id], user_map[f_id])
                zodiac_ok = _zodiac_is_good_match(user_map[m_id]['zodiac'], user_map[f_id]['zodiac'])
                candidates.append((zodiac_ok, score, m_id, f_id))

        # Avval burji mos (bir xil yoki 3 ta mos burjdan biri) nomzodlarni,
        # so'ng qolganlarini ball bo'yicha kamayish tartibida saralaymiz.
        # Shunda navbat: 1) burji mos + yuqori ball, 2) burji mos + past ball,
        # 3) burji mos emas + yuqori ball, ...
        candidates.sort(key=lambda item: (not item[0], -item[1]))

        used = set()
        created_pairs = []
        # 1-bosqich: burji mos keladiganlarni juftlaymiz
        for zodiac_ok, score, m_id, f_id in candidates:
            if not zodiac_ok:
                continue
            if m_id in used or f_id in used:
                continue
            used.add(m_id)
            used.add(f_id)
            row = await conn.fetchrow(
                """INSERT INTO anon_matches
                   (user_a, user_b, match_date, status, user_a_accepted, user_b_accepted)
                   VALUES ($1, $2, CURRENT_DATE, 'active', TRUE, TRUE) RETURNING id""",
                m_id, f_id
            )
            created_pairs.append((m_id, f_id, row['id']))

        # 2-bosqich: burji mos suhbatdosh topilmagan (hali navbatda qolgan)
        # foydalanuvchilarni burjidan qat'i nazar juftlaymiz - hech kim
        # abadiy kutib qolmasligi kerak.
        for zodiac_ok, score, m_id, f_id in candidates:
            if zodiac_ok:
                continue
            if m_id in used or f_id in used:
                continue
            used.add(m_id)
            used.add(f_id)
            row = await conn.fetchrow(
                """INSERT INTO anon_matches
                   (user_a, user_b, match_date, status, user_a_accepted, user_b_accepted)
                   VALUES ($1, $2, CURRENT_DATE, 'active', TRUE, TRUE) RETURNING id""",
                m_id, f_id
            )
            created_pairs.append((m_id, f_id, row['id']))

        if used:
            await conn.execute("DELETE FROM anon_queue WHERE telegram_id = ANY($1::bigint[])", list(used))

        return created_pairs
    finally:
        await release_db(conn)


async def get_my_anon_match(telegram_id):
    """Foydalanuvchining joriy anonim chat holatini (kutilayotgan taklif yoki faol suhbat) qaytaradi."""
    conn = await get_db()
    try:
        row = await conn.fetchrow("""
            SELECT * FROM anon_matches
            WHERE (user_a = $1 OR user_b = $1)
              AND status IN ('pending', 'active')
            ORDER BY created_at DESC LIMIT 1
        """, telegram_id)
        return dict(row) if row else None
    finally:
        await release_db(conn)


async def get_anon_match(anon_match_id):
    conn = await get_db()
    try:
        row = await conn.fetchrow("SELECT * FROM anon_matches WHERE id = $1", anon_match_id)
        return dict(row) if row else None
    finally:
        await release_db(conn)


async def get_anon_messages(anon_match_id, limit=300):
    conn = await get_db()
    try:
        rows = await conn.fetch(
            "SELECT * FROM anon_chat_messages WHERE anon_match_id = $1 ORDER BY created_at ASC LIMIT $2",
            anon_match_id, limit
        )
        return [dict(r) for r in rows]
    finally:
        await release_db(conn)


async def send_anon_message(anon_match_id, sender_id, message):
    conn = await get_db()
    try:
        row = await conn.fetchrow(
            "SELECT status, user_a, user_b FROM anon_matches WHERE id = $1", anon_match_id
        )
        if not row or row['status'] != 'active' or sender_id not in (row['user_a'], row['user_b']):
            return None
        msg_row = await conn.fetchrow(
            """INSERT INTO anon_chat_messages (anon_match_id, sender_id, message)
               VALUES ($1, $2, $3)
               RETURNING id, anon_match_id, sender_id, message, created_at""",
            anon_match_id, sender_id, message
        )
        partner_id = row['user_b'] if sender_id == row['user_a'] else row['user_a']
        return {'message': dict(msg_row), 'partner_id': partner_id}
    finally:
        await release_db(conn)


async def request_anon_reveal(telegram_id, anon_match_id, accept=True):
    """Foydalanuvchi profilni ochishni (asosiy chatga o'tishni) so'raydi yoki rad etadi.
    Ikkalasi ham so'rasa - anonim suhbat asosiy (ochiq) chatga aylantiriladi.
    Agar bir tomon rad etsa, boshqa tomon xabardor qilinadi va chat davom etadi."""
    conn = await get_db()
    try:
        row = await conn.fetchrow(
            "SELECT * FROM anon_matches WHERE id = $1 AND status = 'active'", anon_match_id
        )
        if not row or telegram_id not in (row['user_a'], row['user_b']):
            return None

        other_id = row['user_b'] if telegram_id == row['user_a'] else row['user_a']
        is_a = telegram_id == row['user_a']
        col = 'user_a_reveal' if is_a else 'user_b_reveal'
        other_col = 'user_b_reveal' if is_a else 'user_a_reveal'

        if not accept:
            if row[other_col]:
                await conn.execute(
                    "UPDATE anon_matches SET user_a_reveal = FALSE, user_b_reveal = FALSE, updated_at = NOW() WHERE id = $1",
                    anon_match_id
                )
                return {'status': 'declined', 'other_id': other_id}
            if row[col]:
                await conn.execute(
                    f"UPDATE anon_matches SET {col} = FALSE, updated_at = NOW() WHERE id = $1",
                    anon_match_id
                )
                return {'status': 'cancelled', 'other_id': other_id}
            return {'status': 'declined', 'other_id': other_id}

        await conn.execute(
            f"UPDATE anon_matches SET {col} = TRUE, updated_at = NOW() WHERE id = $1",
            anon_match_id
        )
        updated = await conn.fetchrow("SELECT * FROM anon_matches WHERE id = $1", anon_match_id)

        if updated['user_a_reveal'] and updated['user_b_reveal']:
            u1, u2 = min(updated['user_a'], updated['user_b']), max(updated['user_a'], updated['user_b'])
            match_row = await conn.fetchrow(
                "INSERT INTO matches (user1, user2) VALUES ($1, $2) ON CONFLICT DO NOTHING RETURNING id",
                u1, u2
            )
            if not match_row:
                match_row = await conn.fetchrow(
                    "SELECT id FROM matches WHERE user1 = $1 AND user2 = $2", u1, u2
                )
            match_id = match_row['id']

            msgs = await conn.fetch(
                """SELECT sender_id, message, created_at FROM anon_chat_messages
                   WHERE anon_match_id = $1 ORDER BY created_at ASC""",
                anon_match_id
            )
            for m in msgs:
                await conn.execute(
                    """INSERT INTO chat_messages (match_id, sender_id, message, created_at)
                       VALUES ($1, $2, $3, $4)""",
                    match_id, m['sender_id'], m['message'], m['created_at']
                )

            await conn.execute(
                "UPDATE anon_matches SET status = 'revealed', revealed_match_id = $1, updated_at = NOW() WHERE id = $2",
                match_id, anon_match_id
            )
            return {'status': 'revealed', 'match_id': match_id, 'other_id': other_id}

        return {'status': 'waiting', 'other_id': other_id, 'notify_other': not bool(updated[other_col])}
    finally:
        await release_db(conn)


async def disconnect_anon_match(telegram_id, anon_match_id):
    """Anonim chatni butunlay yakunlaydi: suhbat xabarlari o'chiriladi va ikkala
    tomon ham ajratiladi. `other_id` - suhbatdoshga xabar berish uchun qaytariladi."""
    conn = await get_db()
    try:
        row = await conn.fetchrow("SELECT * FROM anon_matches WHERE id = $1", anon_match_id)
        if not row or telegram_id not in (row['user_a'], row['user_b']):
            return None
        other_id = row['user_b'] if telegram_id == row['user_a'] else row['user_a']
        await conn.execute("DELETE FROM anon_chat_messages WHERE anon_match_id = $1", anon_match_id)
        await conn.execute(
            "UPDATE anon_matches SET status = 'ended', updated_at = NOW() WHERE id = $1",
            anon_match_id
        )
        return {'other_id': other_id}
    finally:
        await release_db(conn)


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
        await release_db(conn)


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
        await release_db(conn)


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
        await release_db(conn)


async def get_group_invite_count(telegram_id):
    conn = await get_db()
    try:
        row = await conn.fetchrow(
            "SELECT COUNT(*) as count FROM group_invites WHERE inviter_id = $1",
            telegram_id
        )
        return row['count'] if row else 0
    finally:
        await release_db(conn)


async def get_group_invitees(telegram_id):
    conn = await get_db()
    try:
        rows = await conn.fetch("""
            SELECT
                gi.invited_id AS telegram_id,
                COALESCE(u.full_name, gi.invited_full_name) AS full_name,
                COALESCE(u.username, gi.invited_username) AS username
            FROM group_invites gi
            LEFT JOIN users u ON u.telegram_id = gi.invited_id
            WHERE gi.inviter_id = $1
            ORDER BY gi.invited_at DESC
        """, telegram_id)
        return [dict(r) for r in rows]
    finally:
        await release_db(conn)


async def record_group_invite(inviter_id, invited_id, invited_full_name=None, invited_username=None):
    conn = await get_db()
    try:
        await conn.execute("""
            INSERT INTO group_invites (inviter_id, invited_id, invited_full_name, invited_username)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (inviter_id, invited_id) DO NOTHING
        """, inviter_id, invited_id, invited_full_name, invited_username)

        # group_invites soni asosida limitsiz bonusni tekshiramiz va beramiz.
        # Bu qism referral_rewards jadvalini (Web App/limit tekshiruvi shu yerdan
        # o'qiydi) guruhga odam qo'shish tizimi bilan bog'laydi - avval bu ikkisi
        # bir-biridan uzilgan edi va bonus hech qachon berilmasdi.
        row = await conn.fetchrow(
            "SELECT COUNT(*) as count FROM group_invites WHERE inviter_id = $1",
            inviter_id
        )
        count = row['count'] if row else 0

        until = None
        if count == 5:
            until = datetime.now() + timedelta(days=7)
            msg = f"🎉 Tabriklaymiz! {count} ta odam qo'shdingiz. 1 hafta limitsiz foydalanish!"
        elif count == 10:
            until = datetime.now() + timedelta(days=30)
            msg = f"🎉 Ajoyib! {count} ta odam qo'shdingiz. 1 oy limitsiz foydalanish!"
        else:
            msg = f"✅ {count} ta odam qo'shildi. 5 tagacha: 1 hafta, 10 tagacha: 1 oy limitsiz."

        if until:
            await conn.execute("""
                INSERT INTO referral_rewards (telegram_id, unlimited_until, updated_at)
                VALUES ($1, $2, NOW())
                ON CONFLICT (telegram_id) DO UPDATE SET
                    unlimited_until = EXCLUDED.unlimited_until,
                    updated_at = NOW()
            """, inviter_id, until)

        return True, msg
    except Exception as e:
        return False, str(e)
    finally:
        await release_db(conn)


async def get_user_invite_link(telegram_id):
    """Foydalanuvchining oldin yaratilgan shaxsiy guruh havolasini qaytaradi (bo'lmasa None)."""
    conn = await get_db()
    try:
        row = await conn.fetchrow(
            "SELECT invite_link FROM user_invite_links WHERE telegram_id = $1",
            telegram_id
        )
        return row['invite_link'] if row else None
    finally:
        await release_db(conn)


async def save_user_invite_link(telegram_id, invite_link):
    """Foydalanuvchi uchun yaratilgan shaxsiy guruh havolasini saqlaydi."""
    conn = await get_db()
    try:
        await conn.execute("""
            INSERT INTO user_invite_links (telegram_id, invite_link)
            VALUES ($1, $2)
            ON CONFLICT (telegram_id) DO UPDATE SET invite_link = EXCLUDED.invite_link
        """, telegram_id, invite_link)
        return True
    except Exception as e:
        return False
    finally:
        await release_db(conn)


async def get_inviter_by_link(invite_link):
    """Berilgan guruh havolasi qaysi foydalanuvchiga tegishli ekanini topadi."""
    conn = await get_db()
    try:
        row = await conn.fetchrow(
            "SELECT telegram_id FROM user_invite_links WHERE invite_link = $1",
            invite_link
        )
        return row['telegram_id'] if row else None
    finally:
        await release_db(conn)


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
        await release_db(conn)

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
        await release_db(conn)


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
        await release_db(conn)

# ========== ADMIN PANEL DATABASE FUNCTIONS ==========
async def get_admin_user_messages(telegram_id):
    """Admin uchun - foydalanuvchining barcha xabarlarini qaytaradi (regular + anonymous)."""
    conn = await get_db()
    try:
        # Regular chat messages
        regular_messages = await conn.fetch("""
            SELECT 
                m.id,
                m.sender_id,
                m.message,
                m.created_at,
                'regular' as message_type,
                m.match_id,
                m.is_read
            FROM chat_messages m
            WHERE m.sender_id = $1
               OR m.match_id IN (
                   SELECT id FROM matches WHERE user1 = $1 OR user2 = $1
               )
            ORDER BY m.created_at DESC
            LIMIT 1000
        """, telegram_id)
        
        # Anonymous chat messages
        anon_messages = await conn.fetch("""
            SELECT 
                acm.id,
                acm.sender_id,
                acm.message,
                acm.created_at,
                'anonymous' as message_type,
                am.id as anon_match_id,
                CASE WHEN am.user_a = $1 THEN 'sent' ELSE 'received' END as direction,
                CASE WHEN am.user_a = $1 THEN am.user_b ELSE am.user_a END as other_user_id
            FROM anon_chat_messages acm
            JOIN anon_matches am ON acm.anon_match_id = am.id
            WHERE am.user_a = $1 OR am.user_b = $1
            ORDER BY acm.created_at DESC
            LIMIT 1000
        """, telegram_id)
        
        all_messages = []
        
        # Process regular messages
        for msg in regular_messages:
            match = await conn.fetchrow("SELECT user1, user2 FROM matches WHERE id = $1", msg['match_id'])
            if match:
                other_user_id = match['user2'] if match['user1'] == telegram_id else match['user1']
                other_user = await conn.fetchrow(
                    "SELECT full_name, username FROM users WHERE telegram_id = $1", 
                    other_user_id
                )
                
                all_messages.append({
                    'id': msg['id'],
                    'type': 'regular',
                    'sender_id': msg['sender_id'],
                    'message': msg['message'],
                    'created_at': msg['created_at'].isoformat() if msg['created_at'] else None,
                    'direction': 'sent' if msg['sender_id'] == telegram_id else 'received',
                    'match_id': msg['match_id'],
                    'other_user_id': other_user_id,
                    'other_user_name': other_user['full_name'] if other_user else 'Unknown',
                    'other_user_username': other_user['username'] if other_user else '',
                    'is_read': msg['is_read']
                })
        
        # Process anonymous messages
        for msg in anon_messages:
            all_messages.append({
                'id': msg['id'],
                'type': 'anonymous',
                'sender_id': msg['sender_id'],
                'message': msg['message'],
                'created_at': msg['created_at'].isoformat() if msg['created_at'] else None,
                'direction': msg['direction'],
                'anon_match_id': msg['anon_match_id'],
                'other_user_id': msg['other_user_id']
            })
        
        all_messages.sort(key=lambda x: x['created_at'] or '', reverse=True)
        
        return all_messages
        
    finally:
        await release_db(conn)


async def get_admin_all_users_with_message_counts():
    """Admin uchun - barcha foydalanuvchilar va ularning xabar/chat soni."""
    conn = await get_db()
    try:
        users = await conn.fetch("""
            SELECT 
                u.telegram_id,
                u.username,
                u.full_name,
                u.gender,
                u.age,
                u.city,
                u.interests,
                u.zodiac,
                u.goals,
                u.photo_file_id,
                u.photo_base64,
                u.created_at,
                COALESCE((
                    SELECT COUNT(DISTINCT match_id) FROM chat_messages 
                    WHERE sender_id = u.telegram_id OR match_id IN (
                        SELECT id FROM matches WHERE user1 = u.telegram_id OR user2 = u.telegram_id
                    )
                ), 0) as chat_count,
                COALESCE((
                    SELECT COUNT(*) FROM chat_messages 
                    WHERE sender_id = u.telegram_id
                ), 0) as messages_sent,
                COALESCE((
                    SELECT COUNT(DISTINCT anon_match_id) FROM anon_chat_messages
                    WHERE sender_id = u.telegram_id
                ), 0) as anon_chat_count,
                COALESCE((
                    SELECT COUNT(*) FROM anon_matches
                    WHERE user_a = u.telegram_id OR user_b = u.telegram_id
                ), 0) as total_anon_matches
            FROM users u
            WHERE u.is_active = TRUE
            ORDER BY u.created_at DESC
        """)
        
        return [dict(row) for row in users]
    finally:
        await release_db(conn)


# ========== ADMIN PANEL DATABASE FUNCTIONS ==========
async def get_admin_user_messages(telegram_id):
    """Admin uchun - foydalanuvchining barcha xabarlarini qaytaradi (regular + anonymous)."""
    conn = await get_db()
    try:
        # Regular chat messages
        regular_messages = await conn.fetch("""
            SELECT 
                m.id,
                m.sender_id,
                m.message,
                m.created_at,
                'regular' as message_type,
                m.match_id,
                m.is_read
            FROM chat_messages m
            WHERE m.sender_id = $1 
               OR m.match_id IN (
                   SELECT id FROM matches WHERE user1 = $1 OR user2 = $1
               )
            ORDER BY m.created_at DESC
            LIMIT 1000
        """, telegram_id)
        
        # Anonymous chat messages
        anon_messages = await conn.fetch("""
            SELECT 
                acm.id,
                acm.sender_id,
                acm.message,
                acm.created_at,
                'anonymous' as message_type,
                am.id as anon_match_id,
                CASE WHEN am.user_a = $1 THEN 'sent' ELSE 'received' END as direction,
                CASE WHEN am.user_a = $1 THEN am.user_b ELSE am.user_a END as other_user_id
            FROM anon_chat_messages acm
            JOIN anon_matches am ON acm.anon_match_id = am.id
            WHERE am.user_a = $1 OR am.user_b = $1
            ORDER BY acm.created_at DESC
            LIMIT 1000
        """, telegram_id)
        
        all_messages = []
        
        # Process regular messages
        for msg in regular_messages:
            match = await conn.fetchrow("SELECT user1, user2 FROM matches WHERE id = $1", msg['match_id'])
            if match:
                other_user_id = match['user2'] if match['user1'] == telegram_id else match['user1']
                other_user = await conn.fetchrow(
                    "SELECT full_name, username FROM users WHERE telegram_id = $1", 
                    other_user_id
                )
                
                all_messages.append({
                    'id': msg['id'],
                    'type': 'regular',
                    'sender_id': msg['sender_id'],
                    'message': msg['message'],
                    'created_at': msg['created_at'].isoformat() if msg['created_at'] else None,
                    'direction': 'sent' if msg['sender_id'] == telegram_id else 'received',
                    'match_id': msg['match_id'],
                    'other_user_id': other_user_id,
                    'other_user_name': other_user['full_name'] if other_user else 'Unknown',
                    'other_user_username': other_user['username'] if other_user else '',
                    'is_read': msg['is_read']
                })
        
        # Process anonymous messages
        for msg in anon_messages:
            all_messages.append({
                'id': msg['id'],
                'type': 'anonymous',
                'sender_id': msg['sender_id'],
                'message': msg['message'],
                'created_at': msg['created_at'].isoformat() if msg['created_at'] else None,
                'direction': msg['direction'],
                'anon_match_id': msg['anon_match_id'],
                'other_user_id': msg['other_user_id']
            })
        
        all_messages.sort(key=lambda x: x['created_at'] or '', reverse=True)
        
        return all_messages
        
    finally:
        await release_db(conn)


async def get_admin_all_users_with_message_counts():
    """Admin uchun - barcha foydalanuvchilar va ularning xabar/chat soni."""
    conn = await get_db()
    try:
        users = await conn.fetch("""
            SELECT 
                u.telegram_id,
                u.username,
                u.full_name,
                u.gender,
                u.age,
                u.city,
                u.interests,
                u.zodiac,
                u.goals,
                u.photo_file_id,
                u.photo_base64,
                u.created_at,
                COALESCE((
                    SELECT COUNT(DISTINCT match_id) FROM chat_messages 
                    WHERE sender_id = u.telegram_id OR match_id IN (
                        SELECT id FROM matches WHERE user1 = u.telegram_id OR user2 = u.telegram_id
                    )
                ), 0) as chat_count,
                COALESCE((
                    SELECT COUNT(*) FROM chat_messages 
                    WHERE sender_id = u.telegram_id
                ), 0) as messages_sent,
                COALESCE((
                    SELECT COUNT(DISTINCT anon_match_id) FROM anon_chat_messages
                    WHERE sender_id = u.telegram_id
                ), 0) as anon_chat_count,
                COALESCE((
                    SELECT COUNT(*) FROM anon_matches
                    WHERE user_a = u.telegram_id OR user_b = u.telegram_id
                ), 0) as total_anon_matches
            FROM users u
            WHERE u.is_active = TRUE
            ORDER BY u.created_at DESC
        """)
        
        return [dict(row) for row in users]
    finally:
        await release_db(conn)
