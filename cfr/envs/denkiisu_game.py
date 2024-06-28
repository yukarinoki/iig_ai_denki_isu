from collections import deque
from itertools import combinations
from copy import deepcopy
from copy import copy


def add_list_to_dict(target_dict, key, value):
    if key in target_dict.keys():
        target_dict[key].append(value)
    else:
        target_dict[key] = [value]


class State:
    def __init__(self, player, remaining_chairs={1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12}, players_life=[3, 3], players_score=[0, 0], configure_turn=True):
        self.player = player
        self.remaining_chairs = remaining_chairs
        self.players_life = players_life
        self.players_score = players_score
        self.configure_turn = configure_turn

    def next_state(self, is_success=False, chair_id=None):
        if self.configure_turn:
            ns = State(1 - self.player, self.remaining_chairs,
                       self.players_life, self.players_score, False)
            return ns
        else:
            if is_success:
                ns = State(self.player, self.remaining_chairs - {chair_id},
                           self.players_life, self.players_score, True)
                ns.players_score[self.player] += chair_id
                return ns
            else:
                ns = State(self.player, self.remaining_chairs,
                           self.players_life, self.players_score, True)
                ns.players_life[self.player] -= 1
                ns.players_score[self.player] = 0
                return ns

    def __hash__(self):
        return hash((self.player, tuple(self.remaining_chairs), tuple(self.players_life), tuple(self.players_score), self.configure_turn))

    def __eq__(self, other):
        if not isinstance(other, State):
            return False
        return (self.player == other.player and
                self.remaining_chairs == other.remaining_chairs and
                self.players_life == other.players_life and
                self.players_score == other.players_score and
                self.configure_turn == other.configure_turn)


class History:
    def __init__(self, configured=False, configured_chair=0, state=None):
        if configured:
            assert (configured_chair in state.remaining_chairs)

        self.configured = configured
        self.configured_chair = configured_chair
        self.state = state

    def next_history(self, action):
        if self.configured:
            if self.configured_chair == action:  # #Electrification !!
                return History(False, None, deepcopy(self.state).next_state(is_success=False))
            else:   # Successfully sat down !!
                return History(False, None, deepcopy(self.state).next_state(is_success=True, chair_id=action))
        else:       # Configure the chair
            return History(True, action, deepcopy(self.state).next_state())

    def __hash__(self):
        return hash((self.configured, self.configured_chair, self.state))

    def __eq__(self, other):
        if not isinstance(other, History):
            return False
        return (self.configured == other.configured and
                self.configured_chair == other.configured_chair and
                self.state == other.state)


class Node:
    def __init__(self, player, terminal, eu=0, chairs=None, max_life=3, winning_score=40):
        self.children = {}
        self.player = player
        self.terminal = terminal
        self.history = History(False, None, State(player, remaining_chairs=chairs, players_life=[
            max_life, max_life], players_score=[0, 0], configure_turn=True))
        self.information = self.history.state  # (state)
        self.winning_score = winning_score

        self.pi = 0
        self.pi_mi = 0  # pi_-i
        self.pi_i = 0  # pi_i
        self.true_pi_mi = 0  # pi_-i following current average strategy profile
        self.eu = eu
        self.cv = 0
        # counter-factual regret of not taking action a at history h(not information I)
        self.cfr = {}
        self.pi_i_sum = 0  # denominator of average strategy
        self.pi_sigma_sum = {}  # numerator of average strategy
        self.num_updates = 0

    def __hash__(self):
        # ハッシュ関数を定義
        return hash(self.history)

    def __eq__(self, other):
        # 同値性を定義
        return isinstance(other, Node) and self.history == other.history

    def expand_child_node(self, action, next_player, terminal=False, utility=0, all_nodes=None):
        if all_nodes is None:
            all_nodes = {}

        next_node_history = self.history.next_history(action)

        # ノードが既に存在するか確認
        is_new = False
        if next_node_history in all_nodes:
            next_node = all_nodes[next_node_history]
        else:
            next_node = Node(next_player, terminal, utility)
            self.children[action] = next_node
            self.cfr[action] = 0
            self.pi_sigma_sum[action] = 0
            next_node.history = next_node_history
            next_node.information = next_node_history.state
            next_node.winning_score = self.winning_score

            if next_node.history.state.players_life[0] <= 0 or next_node.history.state.players_life[1] <= 0:
                next_node.terminal = True
            if next_node.history.state.players_score[0] >= next_node.winning_score or next_node.history.state.players_score[1] >= self.winning_score:
                next_node.terminal = True

            if next_node.terminal == True:
                if next_node.history.state.players_score[0] >= next_node.winning_score or next_node.history.state.players_life[1] <= 0:
                    next_node.eu = 1
                else:
                    next_node.eu = -1

            all_nodes[next_node_history] = next_node
            is_new = True

        return next_node, is_new


class DenkiisuGame:
    def __init__(self):
        self.num_players = 2
        self.chairs = {i + 1 for i in range(12)}
        self.max_life = 2
        self.winning_score = 10
        self.information_sets = {player: {}
                                 for player in range(0, self.num_players)}
        self.all_nodes = {}
        self.root = self._build_game_tree()

    def _build_game_tree(self):
        stack = deque()
        next_player = 0
        root = Node(next_player, False, 0, self.chairs,
                    self.max_life, self.winning_score)
        add_list_to_dict(
            self.information_sets[next_player], root.information, root)
        self.all_nodes[root.history] = root
        stack.append(root)
        count = 0
        while stack:
            node = stack.pop()
            if node.history.state.configure_turn:
                next_player = 1 - node.player
            else:
                next_player = node.player
            for action in node.history.state.remaining_chairs:
                count += 1
                if count % 10000 == 0:
                    print(f"count: {count}")
                next_node, is_new = node.expand_child_node(
                    action, next_player, all_nodes=self.all_nodes)
                if next_node.terminal:
                    continue
                add_list_to_dict(
                    self.information_sets[next_player], next_node.information, next_node)
                if is_new:
                    stack.append(next_node)
        return root


if __name__ == "__main__":
    kuhn_poker = DenkiisuGame()
