

# Initialize tables
with closing(sqlite3.connect(DB)) as conn:
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS rooms (
        room_id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER UNIQUE
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS room_users (
        room_id INTEGER,
        user_id INTEGER,
        PRIMARY KEY (room_id, user_id)
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS games (
        room_id INTEGER PRIMARY KEY,
        state BLOB
    )""")
    conn.commit()

# Room management
def get_room_by_chat(chat_id):
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute("SELECT room_id FROM rooms WHERE chat_id=?", (chat_id,))
        row = c.fetchone()
        return row[0] if row else None

def create_room(chat_id):
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO rooms(chat_id) VALUES(?)", (chat_id,))
        conn.commit()
        return get_room_by_chat(chat_id)

def add_user(room_id, user_id):
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO room_users(room_id,user_id) VALUES(?,?)", (room_id, user_id))
        conn.commit()

def remove_room(room_id):
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM rooms WHERE room_id=?", (room_id,))
        c.execute("DELETE FROM room_users WHERE room_id=?", (room_id,))
        c.execute("DELETE FROM games WHERE room_id=?", (room_id,))
        conn.commit()

# Game state persistence
def save_game(room_id, game):
    blob = pickle.dumps(game)
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute("REPLACE INTO games(room_id,state) VALUES(?,?)", (room_id, blob))
        conn.commit()

def load_game(room_id):
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute("SELECT state FROM games WHERE room_id=?", (room_id,))
        row = c.fetchone()
        return pickle.loads(row[0]) if row else None


# ─── main.py ───
import os
from telegram.ext import Updater, CommandHandler
from telegram import ReplyKeyboardRemove
import server, game as G

TOKEN = os.environ['TELEGRAM_BOT_TOKEN']

updater = Updater(TOKEN, use_context=True)
dp = updater.dispatcher

# /start - create room
def handler_start(update, ctx):
    chat = update.effective_chat.id
    room = server.create_room(chat)
    update.message.reply_text(f"Room {room} created. Players can /join.", reply_markup=ReplyKeyboardRemove())

# /join - add user
def handler_join(update, ctx):
    chat = update.effective_chat.id
    room = server.get_room_by_chat(chat)
    if not room:
        return update.message.reply_text("No room. Use /start first.")
    user = update.effective_user.id
    server.add_user(room, user)
    update.message.reply_text(f"{update.effective_user.first_name} joined room {room}.")

# /begin - start game
def handler_begin(update, ctx):
    chat = update.effective_chat.id
    room = server.get_room_by_chat(chat)
    from server import DB
    users = []
    conn = __import__('sqlite3').connect(DB)
    for row in conn.execute("SELECT user_id FROM room_users WHERE room_id=?", (room,)):
        users.append(row[0])
    conn.close()
    if len(users)<4 or len(users)>6:
        return update.message.reply_text("Need 4-6 players to begin.")
    game = G.ParchiDhapGame(users)
    server.save_game(room, game)
    # DM hands & turn
    for pid, hand in game.hands.items():
        ctx.bot.send_message(pid, f"Your hand: {hand}\nIt's {ctx.bot.get_chat_member(chat, game.get_current()).user.first_name}'s turn.")
    update.message.reply_text("Game started!")

# /pass - pass a card
def handler_pass(update, ctx):
    user = update.effective_user.id
    chat = update.effective_chat.id
    room = server.get_room_by_chat(chat)
    game = server.load_game(room)
    if not game:
        return update.message.reply_text("No active game.")
    try:
        card = int(ctx.args[0])
    except:
        return update.message.reply_text("Usage: /pass <card_value>")
    try:
        hand, winner = game.pass_card(user, card)
    except ValueError as e:
        return update.message.reply_text(str(e))
    server.save_game(room, game)
    update.message.reply_text(f"You passed {card}. Your new hand: {hand}")
    nxt = game.get_current()
    ctx.bot.send_message(chat, f"{update.effective_user.first_name} passed a card to {ctx.bot.get_chat_member(chat,nxt).user.first_name}.")
    ctx.bot.send_message(nxt, f"Your hand: {game.hands[nxt]}\nIt's your turn.")
    if winner:
        ctx.bot.send_message(chat, f"🎉 {ctx.bot.get_chat_member(chat,winner).user.first_name} won!")
        server.remove_room(room)

# /stop - end game & room
handler_end = CommandHandler('stop', lambda u,c: (server.remove_room(server.get_room_by_chat(u.effective_chat.id)), u.message.reply_text('Game stopped.')))

dp.add_handler(CommandHandler('start', handler_start))
dp.add_handler(CommandHandler('join', handler_join))
dp.add_handler(CommandHandler('begin', handler_begin))
dp.add_handler(CommandHandler('pass', handler_pass))
dp.add_handler(handler_end)

updater.start_webhook(listen='0.0.0.0', port=int(os.environ.get('PORT', 8443)), url_path=TOKEN,
                      webhook_url=os.environ.get('WEBHOOK_URL')+TOKEN)
updater.idle()
