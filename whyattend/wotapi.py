"""
    World of Tanks API interface
"""

import requests
import datetime

from config import API_URL, API_TOKEN, WOT_SERVER_REGION_CODE

# timeout for requests to WG server in seconds
API_REQUEST_TIMEOUT = 30


def get_player(id):
    r = requests.get(API_URL + '/2.0/account/info/', timeout=API_REQUEST_TIMEOUT,
                     params={
                         'application_id': API_TOKEN,
                         'account_id': id
                     })
    json = r.json()
    if json['status'] == 'ok':
        return json



def get_clan(id):
    r = requests.get(API_URL + '/2.0/clan/info/', timeout=API_REQUEST_TIMEOUT,
                     params={
                         'application_id': API_TOKEN,
                         'clan_id': id
                     })
    json = r.json()
    if json['status'] == 'ok':
        return json


def get_scheduled_battles(clan_id):
    try:
        r = requests.get('http://worldoftanks.' + WOT_SERVER_REGION_CODE.lower() +
                         '/community/clans/' + str(clan_id) + '/battles/list/',
                         params={'id': 'js-battles-table'},
                         headers={'X-Requested-With': 'XMLHttpRequest',
                                  'Accept': 'application/json, text/javascript, text/html, */*'},
                         timeout=API_REQUEST_TIMEOUT)
        if r.ok and r.json()['result'] == 'success':
            return r.json()
        else:
            return None
    except Exception as e:
        return None

def get_provinces(clan_id):
    try:
        r = requests.get('http://worldoftanks.' + WOT_SERVER_REGION_CODE.lower() +
                         '/community/clans/' + str(clan_id) + '/provinces/list/',
                         params={'id': 'js-provinces-table'},
                         headers={'X-Requested-With': 'XMLHttpRequest',
                                  'Accept': 'application/json, text/javascript, text/html, */*'},
                         timeout=API_REQUEST_TIMEOUT)
        if r.ok and r.json()['result'] == 'success':
            return r.json()
        else:
            return None
    except Exception as e:
        return None