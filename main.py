import aiosqlite
import time
import json
import random
from vkbottle.bot import Bot, Message

# ================= КОНФИГ =================
TOKEN = "vk1.a.EgkR2bJaDuQLgr_339kosMO2KLAVopbKQYXvGml6NEMvsTrqxfsYkojqfWcWk0WKxNOZVyAexK6CgA_vn7bPYjSoWUzu1v2oTGx2l2dB_QSatccPglzh0WPxBwwoK6GDzGe5QQuYbwy_M532DgIDvaq0Py2CyWfmTLjmrYOPGg82UFo3mEnHbSmz6ZBxnK2sZNNYK8zVe0toP8ftpJz18A"
OWNER_ID = 865505970  # Твой ID цифрами
DB_FILE = "mega_bot.db"

# ================= ИЕРАРХИЯ РОЛЕЙ =================
# Уровень доступа: (Название, Тег)
ROLES = {
    0: ("Игрок", "user"),
    1: ("Младший Модератор", "ml_mod"),
    2: ("Модератор", "mod"),
    3: ("Старший Модератор", "st_mod"),
    4: ("Администратор", "admin"),
    5: ("Старший Администратор", "st_admin"),
    6: ("Заместитель Руководителя", "zam"),
    7: ("Руководитель", "leader"),
    999: ("ВЛАДЕЛЕЦ", "owner")
}

# Обратный маппинг для команд
ROLE_KEY_TO_LVL = {
    "user": 0, "ml_mod": 1, "mod": 2, "st_mod": 3,
    "admin": 4, "st_admin": 5, "zam": 6, "leader": 7
}

bot = Bot(token=TOKEN)

# ================= БАЗА ДАННЫХ =================
async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        # Пользователи
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                nickname TEXT,
                balance INTEGER DEFAULT 1000,
                role_level INTEGER DEFAULT 0,
                clan_id INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0,
                reg_date INTEGER
            )
        """)
        # Кланы
        await db.execute("""
            CREATE TABLE IF NOT EXISTS clans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER,
                name TEXT,
                balance INTEGER DEFAULT 0
            )
        """)
        # Репорты
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                text TEXT,
                status TEXT DEFAULT 'open'
            )
        """)
        # Промокоды
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promos (
                code TEXT PRIMARY KEY,
                reward INTEGER,
                activations INTEGER
            )
        """)
        # Таблица использованных промо (чтобы не юзали дважды)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS used_promos (
                user_id INTEGER,
                code TEXT
            )
        """)
        await db.commit()

# --- Хелперы БД ---
async def get_user(user_id):
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()

async def create_user(user_id, name):
    async with aiosqlite.connect(DB_FILE) as db:
        lvl = 999 if user_id == OWNER_ID else 0
        await db.execute("INSERT OR IGNORE INTO users (user_id, nickname, role_level, reg_date) VALUES (?, ?, ?, ?)", 
                         (user_id, name, lvl, int(time.time())))
        await db.commit()

async def execute(query, args=()):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(query, args)
        await db.commit()

# ================= ПРОВЕРКИ =================
async def check_auth(message: Message):
    user = await get_user(message.from_id)
    if not user:
        user_info = await bot.api.users.get(message.from_id)
        name = f"{user_info[0].first_name} {user_info[0].last_name}"
        await create_user(message.from_id, name)
        await message.answer(f"✅ Аккаунт создан! Добро пожаловать, {name}.")
        return await get_user(message.from_id)
    
    if user['is_banned']:
        await message.answer("🚫 Ваш аккаунт заблокирован.")
        return None
    return user

def get_role_name(lvl):
    return ROLES.get(lvl, ("Неизвестно", "unknown"))[0]

# ================= ОБЩИЕ КОМАНДЫ =================

@bot.on.message(text=["меню", "помощь", "help"])
async def menu(message: Message):
    txt = (
        "📚 **Помощь по боту:**\n"
        "👤 Профиль\n"
        "🏆 Топ игроков\n"
        "🏰 Кланы (помощь)\n"
        "🎁 Промо <код>\n"
        "🆘 Репорт <текст>\n\n"
        "👮 **Для сотрудников:** пиши `Админ`"
    )
    await message.answer(txt)

@bot.on.message(text="Профиль")
async def profile(message: Message):
    u = await check_auth(message)
    if not u: return

    role_name = get_role_name(u['role_level'])
    clan_txt = "Нет"
    if u['clan_id']:
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute("SELECT name FROM clans WHERE id = ?", (u['clan_id'],)) as cur:
                clan = await cur.fetchone()
                if clan: clan_txt = clan[0]

    txt = (
        f"📝 Профиль @id{u['user_id']} ({u['nickname']})\n"
        f"💵 Баланс: {u['balance']:,}$\n"
        f"🛡 Должность: {role_name}\n"
        f"🏰 Клан: {clan_txt}\n"
        f"📅 Регистрация: {time.strftime('%d.%m.%Y', time.localtime(u['reg_date']))}"
    )
    await message.answer(txt)

@bot.on.message(text="Топ игроков")
async def top_players(message: Message):
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT nickname, balance FROM users ORDER BY balance DESC LIMIT 10") as cur:
            rows = await cur.fetchall()
    
    txt = "🏆 **Богатейшие люди:**\n"
    for i, row in enumerate(rows, 1):
        txt += f"{i}. {row['nickname']} — {row['balance']:,}$\n"
    await message.answer(txt)

# ================= КЛАНОВАЯ СИСТЕМА =================

@bot.on.message(text="Кланы")
async def clans_help(message: Message):
    txt = (
        "🏰 **Клановая система:**\n"
        "🔸 `Клан создать <название>` (Стоит 100к)\n"
        "🔸 `Клан инфо` — информация о клане\n"
        "🔸 `Клан топ` — рейтинг кланов\n"
        "🔸 `Клан деп <сумма>` — положить в общак"
    )
    await message.answer(txt)

@bot.on.message(text="Клан создать <name>")
async def clan_create(message: Message, name: str):
    u = await check_auth(message)
    if not u: return
    
    if u['clan_id']: return await message.answer("❌ Вы уже в клане!")
    if u['balance'] < 100000: return await message.answer("❌ Создание клана стоит 100,000$")
    
    await execute("UPDATE users SET balance = balance - 100000 WHERE user_id = ?", (u['user_id'],))
    
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("INSERT INTO clans (owner_id, name) VALUES (?, ?)", (u['user_id'], name))
        clan_id = cursor.lastrowid
        await db.commit()
    
    await execute("UPDATE users SET clan_id = ? WHERE user_id = ?", (clan_id, u['user_id']))
    await message.answer(f"✅ Клан «{name}» успешно создан!")

@bot.on.message(text="Клан инфо")
async def clan_info(message: Message):
    u = await check_auth(message)
    if not u: return
    if not u['clan_id']: return await message.answer("❌ Вы не в клане.")

    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM clans WHERE id = ?", (u['clan_id'],)) as cur:
            clan = await cur.fetchone()
    
    txt = (
        f"🏰 Клан: {clan['name']}\n"
        f"👑 Владелец: @id{clan['owner_id']}\n"
        f"💰 Казна: {clan['balance']:,}$"
    )
    await message.answer(txt)

@bot.on.message(text="Клан топ")
async def clan_top(message: Message):
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT name, balance FROM clans ORDER BY balance DESC LIMIT 5") as cur:
            rows = await cur.fetchall()
            
    txt = "🏆 **Топ 5 Кланов:**\n"
    for i, c in enumerate(rows, 1):
        txt += f"{i}. {c['name']} — 💰 {c['balance']:,}\n"
    await message.answer(txt)

@bot.on.message(text="Клан деп <amount:int>")
async def clan_deposit(message: Message, amount: int):
    u = await check_auth(message)
    if not u or not u['clan_id']: return await message.answer("❌ Вы не в клане.")
    if amount <= 0 or u['balance'] < amount: return await message.answer("❌ Не хватает денег.")

    await execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, u['user_id']))
    await execute("UPDATE clans SET balance = balance + ? WHERE id = ?", (amount, u['clan_id']))
    await message.answer(f"✅ Вы внесли {amount}$ в казну клана.")

# ================= РЕПОРТЫ И ПРОМОКОДЫ =================

@bot.on.message(text="Репорт <text>")
async def send_report(message: Message, text: str):
    u = await check_auth(message)
    if not u: return
    
    await execute("INSERT INTO reports (user_id, text) VALUES (?, ?)", (u['user_id'], text))
    await message.answer("✅ Ваша жалоба отправлена администрации. Ожидайте ответа.")
    
    # Оповещение админов (можно сделать рассылку, но пока просто лог)
    print(f"[REPORT] New report from {u['user_id']}: {text}")

@bot.on.message(text="Промо <code_txt>")
async def use_promo(message: Message, code_txt: str):
    u = await check_auth(message)
    if not u: return
    
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM promos WHERE code = ?", (code_txt,)) as cur:
            promo = await cur.fetchone()
        
        if not promo: return await message.answer("❌ Неверный промокод.")
        if promo['activations'] <= 0: return await message.answer("❌ Промокод закончился.")

        async with db.execute("SELECT * FROM used_promos WHERE user_id = ? AND code = ?", (u['user_id'], code_txt)) as cur:
            if await cur.fetchone(): return await message.answer("❌ Вы уже активировали этот код.")

        # Активация
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (promo['reward'], u['user_id']))
        await db.execute("UPDATE promos SET activations = activations - 1 WHERE code = ?", (code_txt,))
        await db.execute("INSERT INTO used_promos VALUES (?, ?)", (u['user_id'], code_txt))
        await db.commit()
        
    await message.answer(f"✅ Промокод активирован! Вы получили {promo['reward']}$")

# ================= АДМИН ПАНЕЛЬ =================

@bot.on.message(text=["админ", "admin"])
async def admin_panel(message: Message):
    u = await check_auth(message)
    if not u or u['role_level'] < 1: return # Доступ только с 1 уровня
    
    lvl = u['role_level']
    txt = f"👮 **Панель сотрудника ({get_role_name(lvl)}):**\n\n"
    
    if lvl >= 1: # Мл. Модер
        txt += "🔹 `!check <id>` — Инфо об игроке\n"
        txt += "🔹 `!reports` — Список жалоб\n"
        txt += "🔹 `!ans <id_репорта> <ответ>` — Ответить\n"
    
    if lvl >= 2: # Модератор
        txt += "🔸 `!kick <id>` — Кикнуть из беседы (эмуляция)\n"
        txt += "🔸 `!ban <id>` — Забанить бота\n"
        txt += "🔸 `!unban <id>` — Разбанить\n"
        
    if lvl >= 4: # Админ
        txt += "♦ `!give <id> <сумма>` — Выдать деньги\n"
        
    if lvl >= 6: # Зам
        txt += "⭐ `!newpromo <код> <сумма> <кол-во>` — Создать промо\n"
        
    if lvl >= 7: # Лидер
        txt += "👑 `!setrole <id> <role_code>` — Назначить должность\n"
        txt += "Доступные коды: ml_mod, mod, st_mod, admin, st_admin, zam, leader"

    await message.answer(txt)

# --- РЕАЛИЗАЦИЯ КОМАНД ПО УРОВНЯМ ---

@bot.on.message(text="!check <target_id:int>")
async def adm_check(message: Message, target_id: int):
    u = await check_auth(message)
    if u['role_level'] < 1: return
    
    t = await get_user(target_id)
    if not t: return await message.answer("Игрок не найден.")
    await message.answer(f"🔍 Инфо:\nНик: {t['nickname']}\nБаланс: {t['balance']}\nБан: {t['is_banned']}")

@bot.on.message(text="!reports")
async def adm_reports(message: Message):
    u = await check_auth(message)
    if u['role_level'] < 1: return
    
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM reports WHERE status = 'open' LIMIT 5") as cur:
            reps = await cur.fetchall()
            
    if not reps: return await message.answer("✅ Жалоб нет.")
    
    txt = "🆘 **Активные жалобы:**\n"
    for r in reps:
        txt += f"ID: {r['id']} | От @id{r['user_id']} | Текст: {r['text']}\n"
    await message.answer(txt)

@bot.on.message(text="!ans <rep_id:int> <text>")
async def adm_ans(message: Message, rep_id: int, text: str):
    u = await check_auth(message)
    if u['role_level'] < 1: return
    
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM reports WHERE id = ?", (rep_id,)) as cur:
            rep = await cur.fetchone()
            
        if not rep: return await message.answer("Репорт не найден.")
        
        await db.execute("UPDATE reports SET status = 'closed' WHERE id = ?", (rep_id,))
        await db.commit()
    
    # Отправляем ответ пользователю
    try:
        await bot.api.messages.send(
            user_id=rep['user_id'], 
            random_id=random.randint(1, 1e9),
            message=f"🔔 **Ответ на ваш репорт:**\n{text}\n\nС уважением, {get_role_name(u['role_level'])}"
        )
        await message.answer(f"✅ Ответ отправлен.")
    except:
        await message.answer(f"⚠ Ответ сохранен, но у игрока закрыта личка.")

@bot.on.message(text="!ban <target_id:int>")
async def adm_ban(message: Message, target_id: int):
    u = await check_auth(message)
    if u['role_level'] < 2: return # Модератор+
    
    t = await get_user(target_id)
    if t['role_level'] >= u['role_level']:
        return await message.answer("❌ Вы не можете забанить старшего по званию!")
        
    await execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (target_id,))
    await message.answer(f"🚫 Игрок @id{target_id} заблокирован Модератором.")

@bot.on.message(text="!unban <target_id:int>")
async def adm_unban(message: Message, target_id: int):
    u = await check_auth(message)
    if u['role_level'] < 2: return
    
    await execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (target_id,))
    await message.answer(f"✅ Игрок @id{target_id} разбанен.")

@bot.on.message(text="!give <target_id:int> <amount:int>")
async def adm_give(message: Message, target_id: int, amount: int):
    u = await check_auth(message)
    if u['role_level'] < 4: return # Админ+
    
    await execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_id))
    await message.answer(f"💸 Выдано {amount}$ игроку @id{target_id}")

@bot.on.message(text="!newpromo <code_txt> <amount:int> <activations:int>")
async def adm_newpromo(message: Message, code_txt: str, amount: int, activations: int):
    u = await check_auth(message)
    if u['role_level'] < 6: return # Зам+
    
    try:
        await execute("INSERT INTO promos VALUES (?, ?, ?)", (code_txt, amount, activations))
        await message.answer(f"🎁 Промокод `{code_txt}` на {amount}$ ({activations} шт) создан!")
    except:
        await message.answer("❌ Такой код уже есть.")

@bot.on.message(text="!setrole <target_id:int> <role_code>")
async def adm_setrole(message: Message, target_id: int, role_code: str):
    u = await check_auth(message)
    if u['role_level'] < 7 and u['user_id'] != OWNER_ID: return # Лидер+
    
    if role_code not in ROLE_KEY_TO_LVL:
        return await message.answer(f"Доступные коды: {', '.join(ROLE_KEY_TO_LVL.keys())}")
    
    new_lvl = ROLE_KEY_TO_LVL[role_code]
    
    # Защита: нельзя выдать роль выше своей (если ты не Владелец)
    if u['user_id'] != OWNER_ID and new_lvl >= u['role_level']:
        return await message.answer("❌ Вы не можете выдать роль равную или выше вашей.")

    await execute("UPDATE users SET role_level = ? WHERE user_id = ?", (new_lvl, target_id))
    await message.answer(f"✅ Пользователю @id{target_id} назначена роль: {ROLES[new_lvl][0]}")

# ================= ЗАПУСК =================
if __name__ == "__main__":
    print("🚀 MEGA BOT 2.0 Запущен!")
    loop = bot.loop
    loop.run_until_complete(init_db())
    bot.run_forever()
      
