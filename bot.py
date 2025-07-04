import logging
import random
from typing import Dict, List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import os
from collections import defaultdict

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

games: Dict[int, 'ParchiDhapGame'] = {}

class ParchiDhapGame:
    def __init__(self, chat_id: int, n: int = 4):
        self.chat_id = chat_id
        self.n = n
        self.players: List[int] = []
        self.player_names: Dict[int, str] = {}
        self.deck: List[int] = []
        self.player_cards: Dict[int, List[int]] = {}
        self.current_player_index = 0
        self.game_started = False
        self.pending_card: Optional[int] = None
        self.pending_from_player: Optional[int] = None
        self.game_finished = False
        self.winner: Optional[int] = None
        self.create_deck()

    def create_deck(self):
        self.deck = [i for i in range(1, self.n + 1) for _ in range(4)]
        random.shuffle(self.deck)

    def add_player(self, user_id: int, name: str) -> bool:
        if user_id not in self.players and len(self.players) < self.n:
            self.players.append(user_id)
            self.player_names[user_id] = name
            return True
        return False

    def start_game(self) -> bool:
        if len(self.players) >= 4 and not self.game_started:
            self.deal_cards()
            self.game_started = True
            return True
        return False

    def deal_cards(self):
        for i, pid in enumerate(self.players):
            self.player_cards[pid] = self.deck[i*4:(i+1)*4]

    def get_current_player(self) -> int:
        return self.players[self.current_player_index]

    def get_next_player(self) -> int:
        return self.players[(self.current_player_index + 1) % len(self.players)]

    def give_card(self, card: int) -> bool:
        cp = self.get_current_player()
        if card in self.player_cards[cp]:
            self.pending_card = card
            self.pending_from_player = cp
            return True
        return False

    def receive_card(self, accept: bool) -> bool:
        if self.pending_card is None:
            return False
        cp = self.get_current_player()
        np = self.get_next_player()
        if accept:
            self.player_cards[cp].remove(self.pending_card)
            self.player_cards[np].append(self.pending_card)
            if self.check_win(cp):
                self.winner = cp
                self.game_finished = True
                return True
        self.current_player_index = (self.current_player_index + 1) % len(self.players)
        self.pending_card = None
        self.pending_from_player = None
        return True

    def check_win(self, pid: int) -> bool:
        cards = self.player_cards[pid]
        return bool(cards) and len(set(cards)) == 1

    def get_game_status(self) -> str:
        if not self.game_started:
            return f"Game not started. Players: {len(self.players)}/{self.n}"
        if self.game_finished:
            return f"🎉 Game finished! Winner: {self.player_names[self.winner]}"
        cur = self.player_names[self.get_current_player()]
        if self.pending_card:
            nxt = self.player_names[self.get_next_player()]
            return f"Waiting for {nxt} to accept/reject card {self.pending_card} from {cur}"
        return f"Current turn: {cur}"

# Bot commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to 16 Parchi Dhap! 🎮\n\n"
        "Commands:\n"
        "/newgame <n> - New game (4-6 sets)\n"
        "/join - Join game\n"
        "/startgame - Begin\n"
        "/status - Status\n"
        "/cards - Your cards\n"
        "/cancel - Cancel game\n"
        "/stop - Stop bot"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎮 Rules:\n"
        "1. 4 cards each\n"
        "2. Collect 4 of a kind\n"
        "3. Give one on your turn\n"
        "4. Receiver swaps\n"
        "5. First to 4 wins\n"
        "Commands: /newgame, /join, /startgame, /status, /cards, /cancel, /stop"
    )

async def new_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    try:
        n = int(context.args[0])
    except:
        n = 4
    if n < 4 or n > 6:
        return await update.message.reply_text("Sets must be 4-6.")
    if cid in games:
        return await update.message.reply_text("Game already active.")
    games[cid] = ParchiDhapGame(cid, n)
    await update.message.reply_text(f"New game with {n} sets. /join to enter or /cancel.")

async def cancel_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if cid in games:
        del games[cid]
        return await update.message.reply_text("Game canceled.")
    await update.message.reply_text("No active game.")

async def stop_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot is shutting down... 🌙")
    context.application.stop()

async def join_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    uid = update.effective_user.id
    name = update.effective_user.first_name
    if cid not in games:
        return await update.message.reply_text("No game. /newgame first.")
    game = games[cid]
    if game.game_started:
        return await update.message.reply_text("Game started.")
    if game.add_player(uid, name):
        await update.message.reply_text(f"{name} joined ({len(game.players)}/{game.n}).")
    else:
        await update.message.reply_text("Already joined or full.")

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if cid not in games:
        return await update.message.reply_text("No game.")
    game = games[cid]
    if not game.start_game():
        return await update.message.reply_text(f"Need 4+ players ({len(game.players)} now).")
    cp = game.icipant_names[game.get_current_player()]
    await update.message.reply_text(f"Game started! {cp}'s turn.")
    for pid in game.players:
        cards = ", ".join(map(str, game.player_cards[pid]))
        try:
            await context.bot.send_message(pid, f"Your cards: {cards}")
        except:
            pass

async def show_cards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    uid = update.effective_user.id
    if cid not in games:
        return await update.message.reply_text("No game.")
    game = games[cid]
    if uid not in game.players:
        return await update.message.reply_text("Not in game.")
    if not game.game_started:
        return await update.message.reply_text("Game not started.")
    cards = game.player_cards[uid]
    kb = []
    if uid == game.get_current_player() and not game.pending_card:
        kb = [[InlineKeyboardButton(f"Give {c}", callback_data=f"give_{c}")] for c in set(cards)]
    await update.message.reply_text(
        f"Cards: {', '.join(map(str,cards))}",
        reply_markup=InlineKeyboardMarkup(kb) if kb else None
    )

async def game_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if cid not in games:
        return await update.message.reply_text("No game.")
    await update.message.reply_text(games[cid].get_game_status())

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    cid = q.message.chat.id
    uid = q.from_user.id
    if cid not in games:
        return await q.edit_message_text("No game.")
    game = games[cid]
    data = q.data
    if d.startswith("give_"):
        c = int(data.split("_")[1])
        if uid != game.get_current_player():
            return await q.edit_message_text("Not your turn.")
        if game.give_card(c):
            np = game.get_next_player()
            await q.edit_message_text(f"Gave {c} to {game.player_names[np]}")
            kb = [
                [InlineKeyboardButton("Accept", callback_data="accept")],
                [InlineKeyboardButton("Reject", callback_data="reject")]
            ]
            await context.bot.send_message(np, f"Receive {c}?", reply_markup=InlineKeyboardMarkup(kb))
        else:
            await q.edit_message_text("Invalid.")
    elif data in ("accept","reject"):
        if uid != game.get_next_player():
            return await q.edit_message_text("Not for you.")
        ok = data == "accept"
        game.receive_card(ok)
        if game.game_finished:
            win = game.player_names[game.winner]
            await q.edit_message_text(f"🎉 {win} wins!")
            await context.bot.send_message(cid, f"🎉 {win} wins!")
            del games[cid]
        else:
            await q.edit_message_text("Accepted." if ok else "Rejected.")
            await context.bot.send_message(cid, f"Turn: {game.player_names[game.get_current_player()]}")

if __name__ == "__main__":
    TOKEN = os.getenv("BOT_TOKEN")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("newgame", new_game))
    app.add_handler(CommandHandler("join", join_game))
    app.add_handler(CommandHandler("startgame", start_game))
    app.add_handler(CommandHandler("cards", show_cards))
    app.add_handler(CommandHandler("status", game_status))
    app.add_handler(CommandHandler("cancel", cancel_game))
    app.add_handler(CommandHandler("stop", stop_bot))
    app.add_handler(CallbackQueryHandler(button_callback))
    logger.info("Bot started in polling mode")
    app.run_polling()
