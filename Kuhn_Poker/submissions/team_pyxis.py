import random

class MenteeKuhnBot:
    """
    INSTRUCTIONS:
    1. Rename this class to your Team Name (e.g.,TeamAlphaBot).
    2. Do NOT change the get_action signature.
    3. Return exactly 'p' (Pass/Fold) or 'b' (Bet/Call).
    """
    def __init__(self):
        self.name="Team_Pyxis"
 
        # we are P1 when history in ('','pb'); P2 when history in ('p','b')
        self.opening_action_opponent={'J':0,'Q':0,'K':0}
        self.opening_bet_opponent={'J':0,'Q':0,'K':0}

        self.check_then_opponent={'J':0,'Q':0,'K':0}
        self.check_then_opponent_bets ={'J':0,'Q':0,'K':0}
 
        # state when we check as p1
        self.we_p1_check=False
        self.card_when_we_p1_check=None
 
    def get_action(self,state) -> str:
        card=state.my_card
        history=state.history
 
        # no history and hand ended as pp
        if history=='' and self.we_p1_check:
            self.check_then_opponent[self.card_when_we_p1_check]+=1
            self.we_p1_check=False
            self.card_when_we_p1_check=None
 
        if history in ('b','p'):
            #we are p2
            self.opening_action_opponent[card]+=1
            if history=='b':
                self.opening_bet_opponent[card]+=1
        elif history=='pb' and self.we_p1_check:
            #we are p1 and opponent bets after we check
            c=self.card_when_we_p1_check
            self.check_then_opponent[c]+=1
            self.check_then_opponent_bets[c]+=1

        if history=='':
            action=self.we_first_move(card)
            # if we check as p1
            if action=='p':
                self.we_p1_check=True
                self.card_when_we_p1_check=card
        elif history=='p':
            action=self.we_move_after_p(card)
        elif history=='b':
            action=self.we_move_after_b(card)
        elif history=='pb':
            action=self.we_move_after_pb(card)
            #updating check track
            self.we_p1_check=False
        else:
            #fallback
            action='p'
 
        return action
 
    #smoothened opening card rate for opponent
    def opponent_card_rate_smoothened(self,card):
        return self.smoothening(self.opening_bet_opponent[card],self.opening_action_opponent[card],prior=0.5,strength=6)

    #smoothened bet rate for opponent
    def opponent_bet_rate_smoothened(self,card):
        return self.smoothening(self.check_then_opponent_bets[card],self.check_then_opponent[card],prior=0.5,strength=6)

    """
    opponent_card_rate_smoothened(Q) = Opponent has K or J 
    => opponent_card_rate_smoothened(Q) = P(bet with K) + P(bluff with J) = 1/2 + bluff_J/2
    bluff_J = 2*opponent_card_rate_smoothened(Q)-1
    if bluff_J is close to 0, opponent almost never bluffs with J so we fold Q; if bluff_J is close to 1, opponent almost always bluffs with J so we call Q.
    """

    def bluff_J_opponent_action(self):
        return max(0.0,2*self.opponent_card_rate_smoothened('Q')-1)
 
    def bluff_J_opponent_bet(self):
        return max(0.0,2*self.opponent_bet_rate_smoothened('Q')-1)
  
    @staticmethod
    def we_call_q_probability(bluff_J):
        if bluff_J<=1/3:
            return 0.0
        return min(0.85,(bluff_J-1/3)*1.8)
 
    def we_p1_bluff_j(self):
        n_J=self.opening_action_opponent['J']
        n_K=self.opening_action_opponent['K']
        if n_J<10 or n_K<10:
            return 1/3 #nash
 
        r_J=self.opponent_card_rate_smoothened('J')
        r_K=self.opponent_card_rate_smoothened('K')
 
        if r_J>0.65:#opponent K,Q > 65% of time, so we fallback on bluffs
            return 0.05
        if r_K<0.10:#opponent K less than 10% of time, so we bluff more
            return 0.75
        return 1/3 #nash
 
    def we_p2_bluff_j(self):
        if self.opening_action_opponent['J']<6:
            return 0.85#we mostly get K, Q so we can bluff more OR initial scenario, so we bluff more
 
        r_J=self.opponent_card_rate_smoothened('J')
        if r_J>0.80:# we have more jack so we bluff less
            return 0.60
        return 0.90
 
    def we_first_move(self,card):
        if card=='K':
            return 'b'
        if card=='Q':
            return 'p'
        #J is bluff
        return self.randomiser(self.we_p1_bluff_j(),'b','p')
 
    def we_move_after_p(self,card):
        if card=='K':
            return 'b'
        if card=='Q':
            return 'p'
        #J is bluff
        return self.randomiser(self.we_p2_bluff_j(),'b','p')
 
    def we_move_after_b(self,card):
        if card=='K':
            return 'b'
        if card=='J':
            return 'p'
        #Q probability
        return self.randomiser(self.we_call_q_probability(self.bluff_J_opponent_action()),'b','p')
 
    def we_move_after_pb(self,card):
        if card=='K':
            return 'b'
        if card=='J':
            return 'p'
        #Q probability
        return self.randomiser(self.we_call_q_probability(self.bluff_J_opponent_bet()),'b','p')
 
 
    def smoothening(self,successes,trials,prior,strength):
        # empirically distribute phantom "strength" number of observations about prior
        return (successes + prior*strength) / (trials + strength)
 
    def randomiser(self,probability,action_if_true,action_if_false):
        probability=max(0.0,min(1.0,probability))
        return action_if_true if random.random()<probability else action_if_false
 