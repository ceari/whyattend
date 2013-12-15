""" Replay import
    ~~~~~~~~~~~~~

    Import replays from the webapp upload folder into DB by matching
    them against the battles present in the database. The script does not
    overwrite existing replay blobs in the database.

    The whyattend package and (local_)config.py have to be in the PYTHONPATH.
"""

import os, datetime

from whyattend.model import db_session, Battle
from whyattend import config, replays

if __name__ == '__main__':
    for root, subfolders, files in os.walk(config.UPLOAD_FOLDER):
        for file in files:
            try:
                replay_blob = open(os.path.join(root, file), 'rb').read()
                replay = replays.parse_replay(replay_blob)
                if not replay['first'] or not replay['second']:
                    print "Skipping incomplete replay " + file
                    continue
                if not replays.is_cw(replay):
                    print "Skipping non-CW-replay " + file
                    continue
                date = datetime.datetime.strptime(replay['first']['dateTime'], '%d.%m.%Y %H:%M:%S')
                clan = replays.guess_clan(replay)
                enemy_clan = replays.guess_enemy_clan(replay)

                battle = Battle.query.filter_by(clan=clan, enemy_clan=enemy_clan, date=date).first()
                if not battle:
                    print "Could not find matching battle for file " + file
                    continue
                if battle.replay.replay_blob:
                    print "Skipping battle " + str(battle.id) + " that already has a replay blob"
                    continue

                battle.replay.replay_blob = replay_blob
                print "Adding replay " + file + " for battle " + str(battle.id) + " " + battle.enemy_clan
                db_session.add(battle.replay)
                db_session.commit()
            except Exception as e:
                print "Error processing " + file + " " + str(e)






