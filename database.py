import asyncpg
import json
from config import DATABASE_URL


async def get_db():
    return await asyncpg.connect(DATABASE_URL)


async def init_db():
    conn = await get_db()
    try:
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
            CREATE TABLE IF NOT EXISTS likes (
                id BIGSERIAL PRIMARY KEY,
                from_user BIGINT NOT NULL,
                to_user BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(from_user, to_user)
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                id BIGSERIAL PRIMARY KEY,
                user1 BIGINT NOT NULL,
                user2 BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(user1, user2)
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS blocks (
                id BIGSERIAL PRIMARY KEY,
                blocker BIGINT NOT NULL,
                blocked BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(blocker, blocked)
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS invites (
                id BIGSERIAL PRIMARY KEY,
                inviter_id BIGINT NOT NULL,
                invited_id BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(inviter_id, invited_id)
            )
        """)

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
    finally:
        await conn.close()


async def save_user(telegram_id, data):
    conn = await get_db()
    try:
        await conn.execute("""
            INSERT INTO users (telegram_id, username, full_name, gender, age, city, interests, zodiac, goals, photo_file_id, photo_base64)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            ON CONFLICT (telegram_id) DO UPDATE SET
                username = EXCLUDED.username,
                full_name = EXCLUDED.full_name,
                gender = EXCLUDED.gender,
                age = EXCLUDED.age,
                city = EXCLUDED.city,
                interests = EXCLUDED.interests,
                zodiac = EXCLUDED.zodiac,
                goals = EXCLUDED.goals,
                photo_file_id = EXCLUDED.photo_file_id,
                photo_base64 = EXCLUDED.photo_base64,
                is_active = TRUE
        """,
            telegram_id,
            data.get("username"),
            data.get("full_name"),
            data.get("gender"),
            data.get("age"),
            data.get("city"),
            data.get("interests", []),
            data.get("zodiac"),
            data.get("goals", []),
            data.get("photo_file_id"),
            data.get("photo_base64")
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


async def search_users(telegram_id, filters):
    conn = await get_db()
    try:
        blocked_ids = await conn.fetch(
            "SELECT blocked FROM blocks WHERE blocker = $1 UNION SELECT blocker FROM blocks WHERE blocked = $1",
            telegram_id
        )
        excluded = [r["blocked"] for r in blocked_ids] + [telegram_id]

        query = """
            SELECT telegram_id, username, full_name, gender, age, city, interests, zodiac, goals, photo_file_id, photo_base64
            FROM users
            WHERE telegram_id != ALL($1::bigint[])
            AND is_active = TRUE
        """
        params = [excluded]
        idx = 2

        if filters.get("gender"):
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
            query += f" AND city ILIKE ${idx}"
            params.append(f"%{filters['city']}%")
            idx += 1

        if filters.get("goals"):
            query += f" AND goals && ${idx}::text[]"
            params.append(filters["goals"])
            idx += 1

        query += " LIMIT 20"
        rows = await conn.fetch(query, *params)

        # can_write tekshiruvi
        match_rows = await conn.fetch(
            "SELECT user1, user2 FROM matches WHERE user1 = $1 OR user2 = $1",
            telegram_id
        )
        match_ids = set()
        for mr in match_rows:
            other = mr['user1'] if mr['user2'] == telegram_id else mr['user2']
            match_ids.add(other)

        inviter_row = await conn.fetchrow(
            "SELECT invited_friends FROM users WHERE telegram_id = $1", telegram_id
        )
        inviter_count = inviter_row['invited_friends'] if inviter_row else 0

        result = []
        for row in rows:
            user = dict(row)
            user['can_write'] = user['telegram_id'] in match_ids or inviter_count >= 2
            result.append(user)
        return result
    finally:
        await conn.close()


async def add_like(from_user, to_user):
    conn = await get_db()
    try:
        await conn.execute(
            "INSERT INTO likes (from_user, to_user) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            from_user, to_user
        )
        # Check mutual like
        mutual = await conn.fetchrow(
            "SELECT id FROM likes WHERE from_user = $1 AND to_user = $2",
            to_user, from_user
        )
        if mutual:
            u1, u2 = min(from_user, to_user), max(from_user, to_user)
            await conn.execute(
                "INSERT INTO matches (user1, user2) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                u1, u2
            )
            return True  # Match!
        return False
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


async def register_invite(inviter_id, invited_id):
    conn = await get_db()
    try:
        existing = await conn.fetchrow(
            "SELECT id FROM invites WHERE inviter_id = $1 AND invited_id = $2",
            inviter_id, invited_id
        )
        if existing:
            return False

        already_invited = await conn.fetchrow(
            "SELECT id FROM invites WHERE invited_id = $1",
            invited_id
        )
        if already_invited:
            return False

        await conn.execute(
            "INSERT INTO invites (inviter_id, invited_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            inviter_id, invited_id
        )

        await conn.execute(
            "INSERT INTO users (telegram_id, invited_friends, is_active) VALUES ($1, 1, TRUE) "
            "ON CONFLICT (telegram_id) DO UPDATE SET invited_friends = users.invited_friends + 1",
            inviter_id
        )
        return True
    finally:
        await conn.close()


async def get_invite_count(telegram_id):
    conn = await get_db()
    try:
        row = await conn.fetchrow(
            "SELECT invited_friends FROM users WHERE telegram_id = $1", telegram_id
        )
        return row["invited_friends"] if row else 0
    finally:
        await conn.close()


async def get_all_users():
    conn = await get_db()
    try:
        rows = await conn.fetch(
            "SELECT telegram_id, username, full_name, gender, age, city, interests, zodiac, goals, photo_file_id, photo_base64, invited_friends, created_at "
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
    """Check if from_user can write to to_user"""
    conn = await get_db()
    try:
        # Match mavjudmi?
        u1, u2 = min(from_user, to_user), max(from_user, to_user)
        match = await conn.fetchrow(
            "SELECT id FROM matches WHERE user1 = $1 AND user2 = $2", u1, u2
        )
        if match:
            return True

        # 2 ta do'st taklif qilganmi?
        count = await conn.fetchrow(
            "SELECT invited_friends FROM users WHERE telegram_id = $1", from_user
        )
        if count and count["invited_friends"] >= 2:
            return True

        return False
    finally:
        await conn.close()


# ========== CHAT & MATCH FUNCTIONS ==========

async def get_pending_likes(telegram_id):
    """Get users who liked telegram_id but not matched yet"""
    conn = await get_db()
    try:
        rows = await conn.fetch("""
            SELECT u.telegram_id, u.username, u.full_name, u.gender, u.age, u.city, 
                   u.interests, u.zodiac, u.goals, u.photo_file_id, u.photo_base64, l.created_at
            FROM likes l
            JOIN users u ON u.telegram_id = l.from_user
            WHERE l.to_user = $1
            AND NOT EXISTS (
                SELECT 1 FROM matches m 
                WHERE (m.user1 = l.from_user AND m.user2 = l.to_user)
                OR (m.user1 = l.to_user AND m.user2 = l.from_user)
            )
            ORDER BY l.created_at DESC
        """, telegram_id)
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def accept_like(telegram_id, from_user):
    """Accept a like from from_user, create match, return match_id"""
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
    """Reject a like from from_user and remove the pending like."""
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
    """Get all matches for user with other user details"""
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


async def mark_messages_read(match_id, reader_id):
    conn = await get_db()
    try:
        await conn.execute(
            "UPDATE chat_messages SET is_read = TRUE WHERE match_id = $1 AND sender_id != $2",
            match_id, reader_id
        )
    finally:
        await conn.close()
