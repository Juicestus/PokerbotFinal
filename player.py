'''
Strategy    K2
'''
from skeleton.actions import FoldAction, CallAction, CheckAction, RaiseAction
from skeleton.states import GameState, TerminalState, RoundState
from skeleton.states import NUM_ROUNDS, STARTING_STACK, BIG_BLIND, SMALL_BLIND
from skeleton.bot import Bot
from skeleton.runner import parse_args, run_bot

import eval7

import random
from collections import Counter

class Player(Bot):
    '''
    A pokerbot that uses heuristic-based strategy for the 3-card variant.
    '''

    def __init__(self):
        '''
        Called when a new game starts. Called exactly once.
        '''
        self.opponent_actions = []
        self.hand_history = []
        self.RANKS = '23456789TJQKA'

    def handle_new_round(self, game_state, round_state, active):
        '''
        Called when a new round starts.
        '''
        self.opponent_actions = []
        self.my_cards = round_state.hands[active]
        self.big_blind = bool(active)
        self.round_num = game_state.round_num

    def handle_round_over(self, game_state, terminal_state, active):
        '''
        Called when a round ends.
        '''
        my_cards = terminal_state.previous_state.hands[active]
        opp_cards = terminal_state.previous_state.hands[1-active]
        board_cards = terminal_state.previous_state.deck[:terminal_state.previous_state.street]
        my_delta = terminal_state.deltas[active]
        
        # Store hand result for potential future analysis
        self.hand_history.append({
            'my_cards': my_cards,
            'opp_cards': opp_cards if opp_cards else [],
            'board_cards': board_cards,
            'result': my_delta
        })

    def rank_to_value(self, rank):
        """Convert card rank to numeric value."""
        return self.RANKS.index(rank)

    def evaluate_hand_strength(self, my_cards, board_cards):
        assert len(board_cards) in [0, 2, 4]
        k = 3
        MC_ITER = 1000
        my_cards = [eval7.Card(card) for card in my_cards]
        board_cards = [eval7.Card(card) for card in board_cards]
        deck = eval7.Deck()
        for card in my_cards + board_cards:
            deck.cards.remove(card)
            
        score = 0
        for _ in range(MC_ITER):
            deck.shuffle()
            draw_number = 3 + (4 - len(board_cards))
            draw = deck.peek(draw_number)
            print(draw)
            opp_draw = draw[:k] # give the opp first 3
            board_draw = draw[k:]  
            
            my_hand = my_cards + board_cards + board_draw
            opp_hand = opp_draw + board_cards + board_draw
            
            my_value = eval7.evaluate(my_hand)
            opp_value = eval7.evaluate(opp_hand)
            
            if my_value > opp_value:
                score += 1
            elif my_value < opp_value:
                score += 0
            else:
                score += 0.5
        win_rate = score / MC_ITER
        # print(f"win rate: {win_rate}")
        return win_rate
        

    def get_action(self, game_state, round_state, active):
        '''
        Where the magic happens - your code should implement this function.
        Called any time the engine needs an action from your bot.
        '''
        legal_actions = round_state.legal_actions()
        street = round_state.street  # 0, 3, 4, or 5 representing pre-flop, flop, turn, or river respectively
        my_cards = round_state.hands[active]
        board_cards = round_state.deck[:street]
        my_pip = round_state.pips[active]
        opp_pip = round_state.pips[1-active]
        my_stack = round_state.stacks[active]
        opp_stack = round_state.stacks[1-active]
        continue_cost = opp_pip - my_pip
        my_contribution = STARTING_STACK - my_stack
        opp_contribution = STARTING_STACK - opp_stack
        pot = my_contribution + opp_contribution
        
        # Calculate my position (0 if first to act, 1 if second)
        position = 0 if active == round_state.button else 1
        
        # Convert betting round to match our strategy
        betting_round = 0 if street == 0 else (1 if street == 3 else 2)
        
        # Evaluate hand strength
        hand_strength = self.evaluate_hand_strength(my_cards, board_cards)
        
        # Implement basic strategy based on hand strength and betting round
        if betting_round == 0:  # Preflop
            return self._preflop_strategy(legal_actions, hand_strength, pot, continue_cost, my_pip, my_stack, position, round_state)
        else:  # Postflop
            return self._postflop_strategy(legal_actions, hand_strength, pot, continue_cost, my_pip, my_stack, position, betting_round, round_state)
    
    def _preflop_strategy(self, legal_actions, hand_strength, pot, continue_cost, my_pip, my_stack, position, round_state):
        """Strategy for the first betting round (preflop)."""
        # Very strong hand
        if hand_strength > 0.8:
            if continue_cost > 0:
                # Someone has bet, re-raise
                if RaiseAction in legal_actions:
                    min_raise, max_raise = round_state.raise_bounds()
                    raise_amount = min(min_raise + (max_raise - min_raise) // 2, max_raise)
                    return RaiseAction(raise_amount)
                return CallAction()
            else:
                # No bet yet, open with a raise
                if RaiseAction in legal_actions:
                    min_raise, max_raise = round_state.raise_bounds()
                    raise_amount = min(min_raise + (max_raise - min_raise) // 3, max_raise)
                    return RaiseAction(raise_amount)
                return CheckAction()
        
        # Strong hand
        elif hand_strength > 0.6:
            if continue_cost > 0:
                # Call moderate bets, re-raise small bets
                if continue_cost < pot / 4 and RaiseAction in legal_actions:
                    min_raise, max_raise = round_state.raise_bounds()
                    return RaiseAction(min_raise)
                elif continue_cost < pot / 2:
                    return CallAction()
                else:
                    if random.random() < 0.4:  # Sometimes call big bets
                        return CallAction()
                    return FoldAction()
            else:
                # No bet yet, open with a raise
                if RaiseAction in legal_actions:
                    min_raise, max_raise = round_state.raise_bounds()
                    return RaiseAction(min_raise)
                return CheckAction()
        
        # Medium hand
        elif hand_strength > 0.4:
            if position == 1:  # In position (acting second)
                if continue_cost > 0:
                    # Call small bets, fold to large bets
                    if continue_cost < pot / 3:
                        return CallAction()
                    else:
                        return FoldAction()
                else:
                    # No bet yet, sometimes raise
                    if random.random() < 0.7 and RaiseAction in legal_actions:  # 70% chance to raise
                        min_raise, max_raise = round_state.raise_bounds()
                        return RaiseAction(min_raise)
                    return CheckAction()
            else:  # Out of position
                if continue_cost > 0:
                    # Call small bets, fold to large bets
                    if continue_cost < pot / 4:
                        return CallAction()
                    else:
                        return FoldAction()
                else:
                    # Check or make a small raise
                    if random.random() < 0.5 and RaiseAction in legal_actions:  # 50% chance to raise
                        min_raise, max_raise = round_state.raise_bounds()
                        return RaiseAction(min_raise)
                    return CheckAction()
        
        # Weak hand
        else:
            if position == 1:  # In position (acting second)
                if continue_cost > 0:
                    # Call very small bets occasionally, otherwise fold
                    if continue_cost < pot / 5 and random.random() < 0.3:
                        return CallAction()
                    else:
                        return FoldAction()
                else:
                    # Check most of the time, occasionally bluff
                    if random.random() < 0.2 and RaiseAction in legal_actions:  # 20% chance to bluff
                        min_raise, max_raise = round_state.raise_bounds()
                        return RaiseAction(min_raise)
                    return CheckAction()
            else:  # Out of position
                if continue_cost > 0:
                    # Usually fold, occasionally call very small bets
                    if continue_cost < pot / 6 and random.random() < 0.2:
                        return CallAction()
                    else:
                        return FoldAction()
                else:
                    # Usually check, occasionally bluff
                    if random.random() < 0.1 and RaiseAction in legal_actions:  # 10% chance to bluff
                        min_raise, max_raise = round_state.raise_bounds()
                        return RaiseAction(min_raise)
                    return CheckAction()
    
    def _postflop_strategy(self, legal_actions, hand_strength, pot, continue_cost, my_pip, my_stack, position, betting_round, round_state):
        """Strategy for betting rounds after the flop."""
        # Adjust strategy based on the betting round
        aggression_factor = 1.0
        if betting_round == 2:  # Final betting round
            # Be more aggressive/passive based on hand strength in the final round
            aggression_factor = 1.5 if hand_strength > 0.5 else 0.7
        
        # Very strong hand
        if hand_strength > 0.8:
            # Value bet strong hands
            if continue_cost > 0:
                # Someone has bet, raise unless it's too big
                if continue_cost > pot * 0.75:
                    return CallAction()
                elif RaiseAction in legal_actions:
                    min_raise, max_raise = round_state.raise_bounds()
                    raise_amount = min(min_raise + (max_raise - min_raise) // 2, max_raise)
                    return RaiseAction(raise_amount)
                return CallAction()
            else:
                # No bet yet, bet around 2/3 of the pot
                if RaiseAction in legal_actions:
                    min_raise, max_raise = round_state.raise_bounds()
                    bet_size = min(int(pot * 0.66 * aggression_factor) + my_pip, max_raise)
                    bet_size = max(bet_size, min_raise)  # Ensure minimum raise
                    return RaiseAction(bet_size)
                return CheckAction()
        
        # Strong hand
        elif hand_strength > 0.6:
            if continue_cost > 0:
                # Call moderate bets, raise small bets
                if continue_cost < pot / 3 and RaiseAction in legal_actions:
                    min_raise, max_raise = round_state.raise_bounds()
                    return RaiseAction(min_raise)
                elif continue_cost < pot * 0.75:
                    return CallAction()
                else:
                    return FoldAction()
            else:
                # No bet yet, bet around half the pot
                if RaiseAction in legal_actions:
                    min_raise, max_raise = round_state.raise_bounds()
                    bet_size = min(int(pot * 0.5 * aggression_factor) + my_pip, max_raise)
                    bet_size = max(bet_size, min_raise)  # Ensure minimum raise
                    return RaiseAction(bet_size)
                return CheckAction()
        
        # Medium hand
        elif hand_strength > 0.4:
            if continue_cost > 0:
                # Call small bets, fold to large bets
                pot_odds = continue_cost / (pot + continue_cost)
                if pot_odds < hand_strength * 1.2:  # Adjust based on implied odds
                    return CallAction()
                else:
                    return FoldAction()
            else:
                # Check or make a small bet
                if (position == 1 or random.random() < 0.4 * aggression_factor) and RaiseAction in legal_actions:
                    min_raise, max_raise = round_state.raise_bounds()
                    bet_size = min(int(pot * 0.3) + my_pip, max_raise)
                    bet_size = max(bet_size, min_raise)  # Ensure minimum raise
                    return RaiseAction(bet_size)
                return CheckAction()
        
        # Weak hand
        else:
            if continue_cost > 0:
                # Usually fold, call only if getting great pot odds
                pot_odds = continue_cost / (pot + continue_cost)
                if pot_odds < hand_strength * 1.5 and continue_cost < pot / 4:
                    return CallAction()
                else:
                    return FoldAction()
            else:
                # Usually check, occasionally bluff
                bluff_threshold = 0.2 * aggression_factor
                if position == 1 and random.random() < bluff_threshold and RaiseAction in legal_actions:
                    min_raise, max_raise = round_state.raise_bounds()
                    bet_size = min(int(pot * 0.5) + my_pip, max_raise)
                    bet_size = max(bet_size, min_raise)  # Ensure minimum raise
                    return RaiseAction(bet_size)
                return CheckAction()


if __name__ == '__main__':
    run_bot(Player(), parse_args())
