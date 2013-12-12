"""
    Script that goes through all .wotreplay files in a folder
    and tries to find CW replays that were not uploaded to the tracker yet
    by comparing the list of players, enemy clan and map name.
"""

import os, hashlib, urllib2, json, sys

sys.path += ['.', '..']

from whyattend import replays

TRACKER_URL = 'http://localhost:5000'

if __name__ == '__main__':
    checksums = json.load(urllib2.urlopen(TRACKER_URL + '/api/battle-checksums'))['hashes']

    for root, subfolders, files in os.walk('/tmp/'):
        for file in files:
            if not file.endswith('.wotreplay'): continue
            try:
                replay_blob = open(os.path.join(root, file), 'rb').read()
                replay = replays.parse_replay(replay_blob)
                if not replays.is_cw(replay): continue

                hash = hashlib.sha1()
                hash.update(''.join(sorted(replays.player_team(replay))))
                hash.update(replays.guess_enemy_clan(replay))
                hash.update(replay['first']['mapName'])

                if hash.hexdigest() not in checksums:
                    print file, 'is an unknown CW replay!'
                else:
                    print file, 'already in tracker'
            except Exception as e:
                print "Error processing " + file + " " + str(e)
