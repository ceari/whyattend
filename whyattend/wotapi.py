"""
    World of Tanks API interface
"""

import requests
import datetime

from config import API_URL, API_TOKEN, WOT_SERVER_REGION_CODE


def get_player(id):
    try:
        r = requests.get(API_URL + 'uc/accounts/' + id + '/api/1.8/', params={'source_token': API_TOKEN},
                         timeout=10)
        json = r.json()
        if json['status'] == 'ok' and json['status_code'] == 'NO_ERROR':
            return json
    except:
        return None


def get_clan(id):
    try:
        r = requests.get(API_URL + 'community/clans/' + id + '/api/1.1/', params={'source_token': API_TOKEN},
                         timeout=10)
        json = r.json()
        if json['status'] == 'ok' and json['status_code'] == 'NO_ERROR':
            return json
    except:
        return None


def get_clantag(player):
    return player['data']['clan']['clan']['abbreviation']


def get_player_clan_role(player):
    return player['data']['clan']['member']['role']


def get_member_since_date(player):
    return datetime.datetime.fromtimestamp(float(player['data']['clan']['member']['since']))


def get_scheduled_battles(clan_id):
    try:
        r = requests.get('http://worldoftanks.' + WOT_SERVER_REGION_CODE.lower() +
                         '/community/clans/' + str(clan_id) + '/battles/list/',
                         params={'id': 'js-battles-table'},
                         headers={'X-Requested-With': 'XMLHttpRequest',
                                  'Accept': 'application/json, text/javascript, text/html, */*'},
                         timeout=10)
        if r.ok and r.json()['result'] == 'success':
            return r.json()
        else:
            return None
    except Exception as e:
        print e
        return None