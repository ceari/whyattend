import requests
import sys
import pprint
sys.path.append(".")
sys.path.append("..")


r = requests.get("https://api.worldoftanks.eu/wot/encyclopedia/tanks/?application_id=demo")

mapping = {}
d = r.json()
for val in d['data'].itervalues():
    vehicle_name = val['name'].split(':')[1]
    mapping[vehicle_name] = {'tier': val['level']}

pprint.pprint(mapping)
