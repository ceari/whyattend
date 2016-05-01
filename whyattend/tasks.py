"""
    Asynchronous tasks
    ~~~~~~~~~~~~~~~~~~

    Tasks can be executed by Celery workers that were started
    with `celery -A whyattend.tasks worker`

    To start a task asynchronously, run
      t = task_function.delay(args)
    and retrieve the result later with
      res = t.wait()

    The tasks are rate-limited to avoid errors from the WoT API.
"""

import datetime
import logging

from celery import Celery
from celery.utils.log import get_task_logger

from . import config, wotapi
from .model import Player, WebappData, db_session

celery = Celery(broker=config.CELERY_BROKER_URL)
celery.conf.update({'CELERY_RESULT_BACKEND': config.CELERY_RESULT_BACKEND})

logger = get_task_logger(__name__)
logger.setLevel(logging.INFO)


@celery.task(rate_limit='5/s')
def get_player_info(player_wot_id):
    logger.info("get_player_info(" + player_wot_id + ")")
    return wotapi.get_player(player_wot_id)


@celery.task(rate_limit='1/s')
def get_clan_info(clan_id):
    logger.info("get_clan(" + clan_id + ")")
    return wotapi.get_clan(clan_id)


@celery.task(rate_limit='1/m')
def synchronize_players(clan_id):
    logger.info("synchronize_players(" + clan_id + ")")
    logger.info("Clan member synchronization triggered for " + str(clan_id))
    webapp_data = WebappData.get()
    webapp_data.last_sync_attempt = datetime.datetime.now()
    db_session.add(webapp_data)
    db_session.commit()
    db_session.remove()

    clan_info = get_clan_info.delay(str(clan_id)).wait()
    logger.info("Synchronizing " + clan_info['data'][str(clan_id)]['abbreviation'])
    processed = set()
    for player_id in clan_info['data'][str(clan_id)]['members']:
        player = clan_info['data'][str(clan_id)]['members'][player_id]
        player_data = get_player_info.delay(str(player['account_id'])).wait()
        p = Player.query.filter_by(wot_id=str(player['account_id'])).first()
        if not player_data:
            if p:
                processed.add(p.id)  # skip this guy later when locking players
            continue  # API Error?

        since = datetime.datetime.fromtimestamp(
            float(player_data['data'][str(player['account_id'])]['clan']['since']))

        if p:
            # Player exists, update information
            processed.add(p.id)
            p.locked = False
            p.clan = clan_info['data'][str(clan_id)]['abbreviation']
            p.role = player['role']  # role might have changed
            p.member_since = since  # might have rejoined
        else:
            # New player
            p = Player(str(player['account_id']),
                       'https://eu.wargaming.net/id/' + str(player['account_id']) + '-' + player[
                           'account_name'] + '/',
                       since,
                       player['account_name'],
                       clan_info['data'][str(clan_id)]['abbreviation'],
                       player['role'])
            logger.info('Adding player ' + player['account_name'])
        db_session.add(p)

    # Lock players which are no longer in the clan
    for player in Player.query.filter_by(clan=clan_info['data'][str(clan_id)]['abbreviation']):
        if player.id in processed or player.id is None or player.locked:
            continue
        logger.info("Locking player " + player.name)
        player.locked = True
        player.lock_date = datetime.datetime.now()
        db_session.add(player)

    try:
        db_session.commit()
        webapp_data.last_successful_sync = datetime.datetime.now()
        db_session.add(webapp_data)
        logger.info("Clan member synchronization successful")
    except Exception as e:
        logger.warning("Clan member synchronization failed. Rolling back database transaction:")
        logger.exception(e)
        db_session.rollback()
    finally:
        db_session.remove()

    return True
