"""
    World of Tanks API interface
"""

import requests
import datetime

from config import API_URL, API_TOKEN, WOT_SERVER_REGION_CODE, MAP_SUBDOMAIN, MAP_REGIONS

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


def get_players(ids):
    r = requests.get(API_URL + '/2.0/account/info/', timeout=API_REQUEST_TIMEOUT,
                     params={
                         'application_id': API_TOKEN,
                         'account_id': ','.join(ids)
                     })
    json = r.json()
    if json['status'] == 'ok':
        return json


def get_players_membership_info(ids):
    r = requests.get(API_URL + '/wgn/clans/membersinfo/', timeout=API_REQUEST_TIMEOUT,
                     params={
                         'fields': 'clan,role,joined_at',
                         'application_id': API_TOKEN,
                         'account_id': ','.join(ids)
                     })
    json = r.json()
    if json['status'] == 'ok':
        return json


def get_clan(id):
    r = requests.get(API_URL + 'wgn/clans/info/', timeout=API_REQUEST_TIMEOUT,
                     params={
                         'application_id': API_TOKEN,
                         'clan_id': id,
                         'members_key': 'id'
                     })
    json = r.json()
    if json['status'] == 'ok':
        return json


def get_scheduled_battles(clan_id):
    try:
        r = requests.get(API_URL + '/wot/globalmap/clanbattles/',
                         params={
                            'application_id': API_TOKEN,
                            'clan_id': clan_id
                         },
                         timeout=API_REQUEST_TIMEOUT)
        if r.ok:
            return r.json()
        else:
            return None
    except Exception:
        return None


def get_provinces(clan_id):
    try:
        r = requests.get(API_URL + '/wot/globalmap/clanprovinces/',
                         params={
                            'application_id': API_TOKEN,
                            'clan_id': clan_id
                         },
                         timeout=API_REQUEST_TIMEOUT)
        if r.ok:
            return r.json()['data'][str(clan_id)]
        else:
            return None
    except Exception:
        return None


def get_battle_schedule(clan_id):
    schedule = get_scheduled_battles(clan_id)

    scheduled_battles = []
    for item in schedule['data']:
        at = datetime.datetime.fromtimestamp(item['time'])
        province = item['province_name']
        front = item['front_name']

        scheduled_battles.append({
            'province': province,
            'time': at if item['time'] else None,
            'front': front
        })

    return scheduled_battles
