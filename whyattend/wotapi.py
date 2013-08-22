"""
    World of Tanks API interface
"""

import requests
import datetime

from config import API_URL, API_TOKEN


def get_player(id):
    try:
        r = requests.get(API_URL + 'uc/accounts/'+id+'/api/1.8/', params={'source_token': API_TOKEN})
        json = r.json()
        if json['status'] == 'ok' and json['status_code'] == 'NO_ERROR':
            return json
    except:
        return None

def get_clan(id):
    try:
        r = requests.get(API_URL + 'community/clans/' + id + '/api/1.1/', params={'source_token': API_TOKEN})
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