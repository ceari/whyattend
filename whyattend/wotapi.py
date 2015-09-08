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
        r = requests.get('http://' + WOT_SERVER_REGION_CODE.lower() +
                         '.wargaming.net/clans/' + str(clan_id) + '/battles/list',
                         headers={'X-Requested-With': 'XMLHttpRequest'},
                         timeout=API_REQUEST_TIMEOUT)
        if r.ok:
            return r.json()
        else:
            return None
    except Exception:
        return None


def get_provinces(clan_id):
    r = requests.get('http://' + WOT_SERVER_REGION_CODE.lower() +
                     '.wargaming.net/clans/' + str(clan_id) + '/provinces/list',
                     headers={'X-Requested-With': 'XMLHttpRequest'},
                     timeout=API_REQUEST_TIMEOUT)
    if r.ok:
        return r.json()


def get_global_map_info(region):
    r = requests.get(MAP_SUBDOMAIN +
                     '/clanwars/maps/provinces/regions/' + str(region),
                     params={'ct': 'json'},
                     headers={'X-Requested-With': 'XMLHttpRequest',
                              'Accept': 'application/json, text/javascript, text/html, */*'},
                     timeout=API_REQUEST_TIMEOUT)
    if r.ok:
        return r.json()


def get_battles(clan_id):
    regions = [get_global_map_info(rid) for rid in MAP_REGIONS]
    all_clans = dict()
    all_region_provinces = dict()
    # Merge information about the regions into single dicts
    for region in regions:
        all_clans.update(region['clans'])
        all_region_provinces.update(region['provinces'])

    # Find all battles the clan is involved in
    clan_combats = list()
    for prov_id in all_region_provinces:
        province = all_region_provinces[prov_id]
        if 'combats' in province and len(province['combats']) > 0:
            p_combats = province['combats']
            for combat_id in p_combats:
                if str(clan_id) in p_combats[combat_id]['combatants'].keys():
                    combat = p_combats[combat_id]
                    combat.update({
                        'province_id': prov_id,  # Add province ID to the combat dictionary
                    })
                    clan_combats.append(combat)

    return clan_combats, all_clans


def get_battle_schedule(clan_id):
    schedule = get_scheduled_battles(clan_id)
    #battles, clans = get_battles(clan_id)

    scheduled_battles = []
    for item in schedule['items']:
        province_ids = [p['id'] for p in item['provinces']]
        provinces = [{'id': p['id'], 'name': p['name']} for p in item['provinces']]
        at = datetime.datetime.fromtimestamp(item['time'])
        maps = [m for m in item['arenas']]
        #
        # enemies = list()
        # enemies_set = set()
        # # find matching battle info from map information and extract enemy clans
        # for battle in battles:
        #     if battle['province_id'] in province_ids:
        #         for cid in battle['combatants']:
        #             if cid == str(clan_id):
        #                 continue
        #             if battle['combatants'][cid]['at'] != item['time'] and battle['at'] != item['time']:
        #                 continue
        #             if not clans[cid]['tag'] in enemies_set:
        #                 enemies.append({
        #                     'tag': clans[cid]['tag'],
        #                     'url': clans[cid]['url'],
        #                     'clan_id': cid
        #                 })
        #                 enemies_set.add(clans[cid]['tag'])

        scheduled_battles.append({
            'provinces': provinces,
            'time': at if item['time'] else None,
            'maps': maps,
            #'enemies': enemies,
            'started': item['started']
        })

    return scheduled_battles
