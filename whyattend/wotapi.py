"""
    World of Tanks API interface
"""

import requests
import datetime

from config import API_URL, API_TOKEN, WOT_SERVER_REGION_CODE


def get_player(id):
    r = requests.get('http://api.worldoftanks.eu/2.0/account/info/?application_id=d0a293dc77667c9328783d489c8cef73&account_id=' + id,
                 timeout=10)
    json = r.json()
    if json['status'] == 'ok':
        return json



def get_clan(id):
    r = requests.get('http://api.worldoftanks.eu/2.0/clan/info/?application_id=d0a293dc77667c9328783d489c8cef73&clan_id=' + id,
                     timeout=10)
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
                         timeout=10)
        if r.ok and r.json()['result'] == 'success':
            return r.json()
        else:
            return None
    except Exception as e:
        print e
        return None