"""
    Replay Parsing
    ~~~~~~~~~~~~~~

    World of Tanks replay parsing and information extraction
"""

import json
import struct
import pickle

from .constants import WOT_TANKS


def parse_replay(replay_blob):
    """
        Parse the replay file and return the extracted information as Python dictionary
    """
    num_blocks = struct.unpack('I', replay_blob[4:8])[0]
    first_chunk_length = struct.unpack('I', replay_blob[8:12])[0]
    first_chunk = replay_blob[12:12 + first_chunk_length]
    second_chunk_length = struct.unpack('I', replay_blob[12 + first_chunk_length:12 + first_chunk_length + 4])[0]
    second_chunk_start = 12 + first_chunk_length + 4
    second_chunk = replay_blob[second_chunk_start:second_chunk_start + second_chunk_length]

    try:
        first_chunk = json.loads(first_chunk.decode('utf-8'))
    except UnicodeDecodeError:
        # if we can't decode the first chunk, this is probably not even a wotreplay file
        return None

    try:
        second_chunk = json.loads(second_chunk.decode('utf-8'))
    except UnicodeDecodeError:
        # Second chunk does not exist if the battle was left before it ended
        second_chunk = None

    # after the second JSON chunk there is a Python serialized dictionary (pickle)
    the_pickle = None
    if num_blocks == 3:
        try:
            pickle_start = second_chunk_start + second_chunk_length + 4
            pickle_length = struct.unpack('I',
                                          replay_blob[
                                               second_chunk_start +
                                               second_chunk_length:second_chunk_start + second_chunk_length + 4])[0]
            the_pickle = pickle.loads(replay_blob[pickle_start:pickle_start + pickle_length])
        except pickle.UnpicklingError:
            the_pickle = None

    return {'first': first_chunk,
            'second': second_chunk,
            'pickle': the_pickle}


def players_list(replay_json, team):
    """ Return the list of players of a team
    :param replay_json:
    :param team: 1 for first, 2 for second team
    :return:
    """
    vehicles = [v for v in replay_json['second'][1].values() if v['team'] == team]
    for v in vehicles:
        if len(v['vehicleType'].split(":")) == 2:
            v['vehicleType'] = v['vehicleType'].split(":")[1].replace("_", " ")
        else:
            # not spotted?
            v['vehicleType'] = None
    return vehicles


def player_won(replay_json):
    own_team = replay_json['first']['vehicles'].values()[0]['team']
    return replay_json['second'][0]['common']['winnerTeam'] == own_team


def player_team(replay_json):
    own_team = replay_json['first']['vehicles'].values()[0]['team']
    return [v['name'] for v in replay_json['first']['vehicles'].values() if v['team'] == own_team]


def is_cw(replay_json):
    """
        Returns whether the replay is probably from a clan war, i.e.
        all players of each team belong to the same clan
    :param replay_json:
    :return:
    """
    team_one = players_list(replay_json, 1)
    team_two = players_list(replay_json, 2)
    return len(set(p['clanAbbrev'] for p in team_one)) == 1 and len(set(p['clanAbbrev'] for p in team_two)) == 1 \
        and guess_clan(replay_json) != guess_enemy_clan(replay_json)


def guess_clan(replay_json):
    """ Attempt to guess the friendly clan name from the replay.
        Use is_cw(replay_json) before calling this to confirm it was a clan war.
    :param replay_json:
    :return:
    """
    # first chunk should only contain the own team, so first player's clan is the friendly clan
    return replay_json['first']['vehicles'].values()[0]['clanAbbrev']


def guess_enemy_clan(replay_json):
    """ Attempt to guess the enemy clan name from the replay.
        Use is_cw(replay_json) before calling this to confirm it was a clan war.

    :param replay_json:
    :return:
    """
    friendly_team = replay_json['first']['vehicles'].values()[0]['team']
    return players_list(replay_json, 1 if friendly_team == 2 else 2)[0]['clanAbbrev']


def score(replay_json):
    own_team = replay_json['first']['vehicles'].values()[0]['team']
    own_team_deaths = 0
    enemy_team_deaths = 0
    for v in replay_json['second'][0]['vehicles'].itervalues():
        if v['deathReason'] != -1:
            if v['team'] == own_team:
                own_team_deaths += 1
            else:
                enemy_team_deaths += 1
    return enemy_team_deaths, own_team_deaths


def player_performance(json_second, vehicles, players):
    tank_info_by_player_name = {}
    for k, v in json_second[1].iteritems():
        if not v['vehicleType']:
             # unrevealed enemy tank?
            continue
        # extract the tank text_id of the player
        tank_id = v['vehicleType'].split(':')[1]
        tank_info_by_player_name[v['name']] = WOT_TANKS.get(tank_id, {'tier': 10})

    perf = dict()
    for k, v in vehicles.iteritems():
        if str(str(v['accountDBID'])) in players:
            player_name = players[str(v['accountDBID'])]['name']
        else:
            player_name = players[v['accountDBID']]['name']
        if not player_name in tank_info_by_player_name:
            continue
        perf[str(v['accountDBID'])] = {
            'tank_info': tank_info_by_player_name[player_name],
            'damageDealt': v['damageDealt'],
            'potentialDamageReceived': v['potentialDamageReceived'],
            'xp': v['xp'],
            'kills': v['kills'],
            'shots': v['shots'],
            'pierced': v['piercings'] if 'piercings' in v else v['pierced'],
            'capturePoints': v['capturePoints'],
            'droppedCapturePoints': v['droppedCapturePoints'],
            'spotted': v['spotted'],
            'survived': v['deathReason'] == -1,     # no death reason = survived?
            'damageAssistedRadio': v['damageAssistedRadio'],
        }
    return perf
