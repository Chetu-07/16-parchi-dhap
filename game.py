# ─── game.py ───
import random

class ParchiDhapGame:
    def __init__(self, players):
        self.players = players[:]           # user_ids list
        self.n = len(players)
        deck = []
        for v in range(1, self.n+1):
            deck += [v]*4
        random.shuffle(deck)
        self.hands = {pid: [deck.pop() for _ in range(4)] for pid in players}
        self.previous_card = None
        self.current_index = 0
        self.winner = None

    def get_current(self): return self.players[self.current_index]

    def pass_card(self, user_id, card):
        if user_id != self.get_current():
            raise ValueError('Not your turn')
        hand = self.hands[user_id]
        if card not in hand:
            raise ValueError('You do not have that card')
        hand.remove(card)
        if self.previous_card is not None:
            hand.append(self.previous_card)
        self.previous_card = card
        if len(set(hand))==1:
            self.winner = user_id
        self.current_index = (self.current_index+1) % self.n
        return hand, self.winner
