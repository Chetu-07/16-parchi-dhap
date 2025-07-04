import logging
import random
from typing import Dict, List, Optional, Set
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

# Game state storage
games: Dict[int, 'ParchiDhapGame'] = {}

class ParchiDhapGame:
    def __init__(self, chat_id: int, n: int = 4):
        self.chat_id = chat_id
        self.n = n  # Number of card sets (4 to 6)
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
        
        # Create deck with n sets of 4 cards each
        self.create_deck()
    
    def create_deck(self):
        """Create a deck with n*4 cards (n sets of 4 identical cards)"""
        self.deck = []
        for i in range(1, self.n + 1):
            for _ in range(4):
                self.deck.append(i)
        random.shuffle(self.deck)
    
    def add_player(self, user_id: int, name: str) -> bool:
        """Add a player to the game"""
        if user_id not in self.players and len(self.players) < self.n:
            self.players.append(user_id)
            self.player_names[user_id] = name
            return True
        return False
    
    def start_game(self) -> bool:
        """Start the game if we have enough players"""
        if len(self.players) >= 4 and not self.game_started:
            self.deal_cards()
            self.game_started = True
            return True
        return False
    
    def deal_cards(self):
        """Deal 4 cards to each player"""
        cards_per_player = 4
        for i, player_id in enumerate(self.players):
            start_idx = i * cards_per_player
            end_idx = start_idx + cards_per_player
            self.player_cards[player_id] = self.deck[start_idx:end_idx]
    
    def get_current_player(self) -> int:
        """Get the current player's ID"""
        return self.players[self.current_player_index]
    
    def get_next_player(self) -> int:
        """Get the next player's ID"""
        next_index = (self.current_player_index + 1) % len(self.players)
        return self.players[next_index]
    
    def give_card(self, card: int) -> bool:
        """Current player gives a card to the next player"""
        current_player = self.get_current_player()
        next_player = self.get_next_player()
        
        if card in self.player_cards[current_player]:
            self.pending_card = card
            self.pending_from_player = current_player
            return True
        return False
    
    def receive_card(self, accept: bool) -> bool:
        """Next player receives the card"""
        if self.pending_card is None:
            return False
        
        current_player = self.get_current_player()
        next_player = self.get_next_player()
        
        if accept:
            # Next player accepts the card
            self.player_cards[current_player].remove(self.pending_card)
            self.player_cards[next_player].append(self.pending_card)
            
            # Check if current player won
            if self.check_win(current_player):
                self.winner = current_player
                self.game_finished = True
                return True
        
        # Move to next player
        self.current_player_index = (self.current_player_index + 1) % len(self.players)
        self.pending_card = None
        self.pending_from_player = None
        
        return True
    
    def check_win(self, player_id: int) -> bool:
        """Check if player has won (all cards are the same)"""
        cards = self.player_cards[player_id]
        if len(cards) == 0:
            return False
        return len(set(cards)) == 1
    
    def get_game_status(self) -> str:
        """Get current game status"""
        if not self.game_started:
            return f"Game not started. Players: {len(self.players)}/{self.n}"
        
        if self.game_finished:
            winner_name = self.player_names[self.winner]
            return f"🎉 Game finished! Winner: {winner_name}"
        
        current_player_name = self.player_names[self.get_current_player()]
        if self.pending_card:
            next_player_name = self.player_names[self.get_next_player()]
            return f"Waiting for {next_player_name} to accept/reject card {self.pending_card} from {current_player_name}"
        else:
            return f"Current turn: {current_player_name}"

# Bot commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    await update.message.reply_text(
        "Welcome to 16 Parchi Dhap! 🎮\n\n"
        "Commands:\n"
        "/newgame <n> - Start a new game (n = 4 to 6)\n"
        "/join - Join the current game\n"
        "/startgame - Start the game when ready\n"
        "/status - Check game status\n"
        "/cards - View your cards\n"
        "/help - Show this help message"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command"""
    await update.message.reply_text(
        "🎮 16 Parchi Dhap Rules:\n\n"
        "1. Each player gets 4 cards\n"
        "2. Goal: Get all 4 cards of the same number\n"
        "3. On your turn, give one card to the next player\n"
        "4. The next player must accept it and give you a different card\n"
        "5. First player to get all matching cards wins!\n\n"
        "Commands:\n"
        "/newgame <n> - Start new game (4-6 players)\n"
        "/join - Join game\n"
        "/startgame - Begin the game\n"
        "/status - Game status\n"
        "/cards - Your cards"
    )

async def new_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create a new game"""
    chat_id = update.effective_chat.id
    
    # Parse n parameter
    try:
        n = int(context.args[0]) if context.args else 4
        if n < 4 or n > 6:
            await update.message.reply_text("Number of card sets must be between 4 and 6!")
            return
    except (IndexError, ValueError):
        n = 4
    
    if chat_id in games:
        await update.message.reply_text("A game is already active in this chat!")
        return
    
    games[chat_id] = ParchiDhapGame(chat_id, n)
    await update.message.reply_text(f"New game created with {n} card sets! Use /join to join the game.")

async def join_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Join the current game"""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    if chat_id not in games:
        await update.message.reply_text("No active game! Use /newgame to create one.")
        return
    
    game = games[chat_id]
    if game.game_started:
        await update.message.reply_text("Game has already started!")
        return
    
    if game.add_player(user_id, user_name):
        await update.message.reply_text(f"{user_name} joined the game! ({len(game.players)}/{game.n} players)")
    else:
        await update.message.reply_text("You're already in the game or it's full!")

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the game"""
    chat_id = update.effective_chat.id
    
    if chat_id not in games:
        await update.message.reply_text("No active game! Use /newgame to create one.")
        return
    
    game = games[chat_id]
    if game.start_game():
        current_player_name = game.player_names[game.get_current_player()]
        await update.message.reply_text(f"Game started! 🎮\n\nCurrent turn: {current_player_name}")
        
        # Send cards to all players
        for player_id in game.players:
            cards_str = ", ".join(str(card) for card in game.player_cards[player_id])
            try:
                await context.bot.send_message(
                    player_id,
                    f"Your cards: {cards_str}\n\nUse /cards to view your cards anytime."
                )
            except Exception as e:
                logger.error(f"Could not send cards to player {player_id}: {e}")
    else:
        await update.message.reply_text(f"Need at least 4 players to start! Currently: {len(game.players)}")

async def show_cards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show player's cards"""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if chat_id not in games:
        await update.message.reply_text("No active game!")
        return
    
    game = games[chat_id]
    if user_id not in game.players:
        await update.message.reply_text("You're not in this game!")
        return
    
    if not game.game_started:
        await update.message.reply_text("Game hasn't started yet!")
        return
    
    cards = game.player_cards[user_id]
    cards_str = ", ".join(str(card) for card in cards)
    
    # Create keyboard for giving cards
    keyboard = []
    if user_id == game.get_current_player() and not game.pending_card:
        for card in set(cards):  # Unique cards only
            keyboard.append([InlineKeyboardButton(f"Give card {card}", callback_data=f"give_{card}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    
    message = f"Your cards: {cards_str}"
    if user_id == game.get_current_player() and not game.pending_card:
        message += "\n\nChoose a card to give to the next player:"
    
    await update.message.reply_text(message, reply_markup=reply_markup)

async def game_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show game status"""
    chat_id = update.effective_chat.id
    
    if chat_id not in games:
        await update.message.reply_text("No active game!")
        return
    
    game = games[chat_id]
    status = game.get_game_status()
    await update.message.reply_text(status)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    chat_id = query.message.chat.id
    user_id = query.from_user.id
    data = query.data
    
    if chat_id not in games:
        await query.edit_message_text("No active game!")
        return
    
    game = games[chat_id]
    
    if data.startswith("give_"):
        card = int(data.split("_")[1])
        if user_id == game.get_current_player():
            if game.give_card(card):
                next_player_name = game.player_names[game.get_next_player()]
                await query.edit_message_text(f"You gave card {card} to {next_player_name}!")
                
                # Send acceptance prompt to next player
                keyboard = [
                    [InlineKeyboardButton("Accept", callback_data="accept_card")],
                    [InlineKeyboardButton("Reject", callback_data="reject_card")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                try:
                    await context.bot.send_message(
                        game.get_next_player(),
                        f"You received card {card}! Do you want to accept it?",
                        reply_markup=reply_markup
                    )
                except Exception as e:
                    logger.error(f"Could not send message to next player: {e}")
            else:
                await query.edit_message_text("Invalid card selection!")
        else:
            await query.edit_message_text("It's not your turn!")
    
    elif data in ["accept_card", "reject_card"]:
        if user_id == game.get_next_player():
            accept = data == "accept_card"
            game.receive_card(accept)
            
            if game.game_finished:
                winner_name = game.player_names[game.winner]
                await query.edit_message_text(f"🎉 Game finished! Winner: {winner_name}")
                await context.bot.send_message(chat_id, f"🎉 Game finished! Winner: {winner_name}")
                del games[chat_id]
            else:
                action = "accepted" if accept else "rejected"
                await query.edit_message_text(f"You {action} the card!")
                
                current_player_name = game.player_names[game.get_current_player()]
                await context.bot.send_message(chat_id, f"Next turn: {current_player_name}")
        else:
            await query.edit_message_text("This is not for you!")

def main():
    """Main function"""
    # Get token from environment variable
    TOKEN = os.getenv('BOT_TOKEN', '7939689975:AAFUL_4FXaFCCIC36Z2Ma6NGQ0QI5urqe_k')
    
    # Create application
    application = Application.builder().token(TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("newgame", new_game))
    application.add_handler(CommandHandler("join", join_game))
    application.add_handler(CommandHandler("startgame", start_game))
    application.add_handler(CommandHandler("cards", show_cards))
    application.add_handler(CommandHandler("status", game_status))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Start the bot
    if os.getenv('HEROKU_APP_NAME'):
        # Running on Heroku
        PORT = int(os.environ.get('PORT', 5000))
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TOKEN,
            webhook_url=f"https://{os.getenv('HEROKU_APP_NAME')}.herokuapp.com/{TOKEN}"
        )
    else:
        # Running locally
        application.run_polling()

if __name__ == '__main__':
    main()