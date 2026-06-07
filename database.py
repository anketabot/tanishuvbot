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
                invited_friends INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            )
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
    finally:
        await conn.close()


async def save_user(telegram_id, data):
    conn = await get_db()
    try:
        await conn.execute("""
            INSERT INTO users (telegram_id, username, full_name, gender, age, city, interests, zodiac, goals, photo_file_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
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
            data.get("photo_file_id")
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

        liked_ids = await conn.fetch(
            "SELECT to_user FROM likes WHERE from_user = $1", telegram_id
        )
        liked = [r["to_user"] for r in liked_ids]
        excluded.extend(liked)

        query = """
            SELECT * FROM users
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
        return [dict(r) for r in rows]
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
            "SELECT id FROM invites WHERE invited_id = $1", invited_id
        )
        if existing:
            return False

        await conn.execute(
            "INSERT INTO invites (inviter_id, invited_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            inviter_id, invited_id
        )
        await conn.execute(
            "UPDATE users SET invited_friends = invited_friends + 1 WHERE telegram_id = $1",
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
