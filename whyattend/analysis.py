import math
from collections import namedtuple, defaultdict

from . import replays

PlayerPerformance = namedtuple('PlayerPerformance',
                               ['battle_count', 'avg_dmg', 'avg_kills', 'avg_spotted', 'survival_rate',
                                'avg_spot_damage', 'avg_pot_damage', 'win_rate', 'wn7', 'avg_decap',
                                'avg_tier'])


def player_performance(battles, players):
    """ Player statistics from replay files of given battles and players: damage done, spots, wn7, ... """
    battle_count = defaultdict(int)
    dmg = defaultdict(float)
    kills = defaultdict(int)
    survived = defaultdict(int)
    spotted = defaultdict(int)
    spot_damage = defaultdict(float)
    potential_damage = defaultdict(float)
    wins = defaultdict(int)
    decap = defaultdict(int)
    tier = defaultdict(int)
    for battle in battles:
        replay_data = battle.replay.unpickle()
        if replay_data['first']['clientVersionFromExe'] == '0, 8, 11 0':
            players_perf = replays.player_performance(replay_data['second'], replay_data['second'][0]['vehicles'],
                                                      replay_data['second'][0]['players'])
        else:
            if not replay_data or not 'pickle' in replay_data or not replay_data['pickle']:
                continue
            if not isinstance(replay_data['pickle']['vehicles'], dict):
                continue
            players_perf = replays.player_performance(replay_data['second'], replay_data['pickle']['vehicles'],
                                                      replay_data['pickle']['players'])

        for player in battle.get_players():
            if not player in players:
                continue
            if not str(player.wot_id) in players_perf:
                # Replay/Players mismatch (account sharing?), skip
                continue
            perf = players_perf[str(player.wot_id)]
            battle_count[player] += 1
            dmg[player] += perf['damageDealt']
            spot_damage[player] += perf['damageAssistedRadio']
            kills[player] += perf['kills']
            survived[player] += 1 if perf['survived'] else 0
            potential_damage[player] += perf['potentialDamageReceived']
            wins[player] += 1 if battle.victory else 0
            spotted[player] += perf['spotted']
            decap[player] += perf['droppedCapturePoints']
            tier[player] += perf['tank_info']['tier']

    avg_dmg = defaultdict(float)
    avg_kills = defaultdict(float)
    survival_rate = defaultdict(float)
    avg_spotted = defaultdict(float)
    avg_spot_damage = defaultdict(float)
    avg_pot_damage = defaultdict(float)
    win_rate = defaultdict(float)
    avg_decap = defaultdict(float)
    avg_tier = defaultdict(float)
    for p in players:
        if battle_count[p] > 0:
            bc = float(battle_count[p])
            avg_dmg[p] = dmg[p] / bc
            avg_kills[p] = kills[p] / bc
            survival_rate[p] = survived[p] / bc
            avg_spotted[p] = spotted[p] / bc
            avg_spot_damage[p] = spot_damage[p] / bc
            avg_pot_damage[p] = potential_damage[p] / bc
            win_rate[p] = wins[p] / bc
            avg_decap[p] = decap[p] / bc
            avg_tier[p] = tier[p] / bc

    wn7 = defaultdict(float)
    for p in players:
        if battle_count[p] == 0:
            continue
        tier = avg_tier[p]
        wn7[p] = (1240.0 - 1040.0 / ((min(6, tier)) ** 0.164)) * avg_kills[p] \
                 + avg_dmg[p] * 530.0 / (184.0 * math.exp(0.24 * tier) + 130.0) \
                 + avg_spotted[p] * 125.0 * min(tier, 3) / 3.0 \
                 + min(avg_decap[p], 2.2) * 100.0 \
                 + ((185 / (0.17 + math.exp((win_rate[p] * 100.0 - 35.0) * -0.134))) - 500.0) * 0.45 \
                 - ((5.0 - min(tier, 5)) * 125.0) / (
            1.0 + math.exp(( tier - (battle_count[p] / 220.0) ** (3.0 / tier) ) * 1.5))

    result = PlayerPerformance(
        battle_count=battle_count,
        avg_dmg=avg_dmg,
        avg_kills=avg_kills,
        avg_spotted=avg_spotted,
        survival_rate=survival_rate,
        avg_spot_damage=avg_spot_damage,
        avg_pot_damage=avg_pot_damage,
        win_rate=win_rate,
        avg_decap=avg_decap,
        avg_tier=avg_tier,
        wn7=wn7
    )
    return result