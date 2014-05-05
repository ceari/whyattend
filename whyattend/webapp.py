"""
    The Web Application
    ~~~~~~~~~~~~~~~~~~~

    Implementation of all request handlers and core functionality.
"""

import csv
import datetime
import os
import pickle
import logging
import hashlib
import tarfile
import calendar

from cStringIO import StringIO
from collections import defaultdict, OrderedDict
from functools import wraps
from datetime import timedelta
import jinja2
from flask import Flask, g, session, render_template, flash, redirect, request, url_for, abort, make_response, jsonify
from flask import Response
from flask_openid import OpenID
from flask_cache import Cache
from sqlalchemy import or_, and_
from sqlalchemy.orm import joinedload, joinedload_all
from werkzeug.utils import secure_filename, Headers

from . import config, replays, wotapi, util, constants, analysis
from .model import Player, Battle, BattleAttendance, Replay, BattleGroup, db_session, WebappData

# Set up Flask application
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = config.DATABASE_URI
app.config['SQLALCHEMY_ECHO'] = False
app.config['SECRET_KEY'] = config.SECRET_KEY
app.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB at a time should be plenty for replays
cache = Cache(app, config={'CACHE_TYPE': 'simple'})
oid = OpenID(app, config.OID_STORE_PATH)

app.jinja_env.undefined = jinja2.StrictUndefined

app.jinja_env.filters['pretty_date'] = util.pretty_date
app.jinja_env.filters['int'] = int
app.jinja_env.globals['datetime'] = datetime
app.jinja_env.globals['STATISTICS_VISIBLE'] = config.STATISTICS_VISIBLE

# Uncomment to set up middleware in case we are behind a reverse proxy server
# from .util import ReverseProxied
# app.wsgi_app = ReverseProxied(app.wsgi_app)

# Set up error logging
if not app.debug and config.ERROR_LOG_FILE:
    from logging.handlers import RotatingFileHandler

    file_handler = RotatingFileHandler(config.ERROR_LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5)
    file_handler.setLevel(logging.WARNING)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s '
        '[in %(pathname)s:%(lineno)d]'))
    app.logger.addHandler(file_handler)

# Set up application logging
logger = logging.getLogger(__name__)
if config.LOG_FILE:
    from logging.handlers import RotatingFileHandler

    file_handler = RotatingFileHandler(config.LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5)
    file_handler.setLevel(logging.INFO)
    logger.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s '))
    logger.addHandler(file_handler)


@app.before_request
def csrf_protect():
    if request.method == "POST":
        token = session.pop('_csrf_token', None)
        if not token or token != request.form.get('_csrf_token'):
            flash('Invalid CSRF token. Please try again or contact an administrator for help.')
            return redirect(url_for('index'))


# noinspection PyUnusedLocal
@app.teardown_appcontext
def shutdown_session(exception=None):
    """Remove the database session at the end of the request or when the application shuts down.
    This is needed to use SQLAlchemy in a declarative way."""
    db_session.remove()


def generate_csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = hashlib.sha1(os.urandom(64)).hexdigest()
    return session['_csrf_token']


app.jinja_env.globals['csrf_token'] = generate_csrf_token


# decorates a decorator function to be able to specify parameters :-)
decorator_with_args = lambda decorator: lambda *args, **kwargs: \
    lambda func: decorator(func, *args, **kwargs)


@app.before_request
def lookup_current_user():
    g.player = None
    if 'openid' in session:
        # Checking if player exists for every request might be overkill
        g.player = Player.query.filter_by(openid=session.get('openid')).first()
        if g.player and g.player.locked:
            g.player = None
            session.pop('openid', None)


# noinspection PyPep8Naming
@app.before_request
def inject_constants():
    """
        Inject some commonly used constants into the global object 'g' so they don't
        have to pass them around everywhere.
    :return:
    """
    g.clans = config.CLAN_NAMES
    g.clan_ids = config.CLAN_IDS
    g.roles = config.ROLE_LABELS
    g.PAYOUT_ROLES = config.PAYOUT_ROLES
    g.WOT_SERVER_REGION_CODE = config.WOT_SERVER_REGION_CODE
    g.DELETE_BATTLE_ROLES = config.DELETE_BATTLE_ROLES
    g.COMMANDED_ROLES = config.COMMANDED_ROLES
    g.CREATE_BATTLE_ROLES = config.CREATE_BATTLE_ROLES
    g.ADMINS = config.ADMINS
    g.ADMIN_ROLES = config.ADMIN_ROLES
    g.PLAYER_PERFORMANCE_ROLES = config.PLAYER_PERFORMANCE_ROLES
    g.RESERVE_SIGNUP_ALLOWED = config.RESERVE_SIGNUP_ALLOWED
    g.MENU_LINKS = config.MENU_LINKS
    g.MAP_URL = config.MAP_URL
    g.STORE_REPLAYS_IN_DB = config.STORE_REPLAYS_IN_DB


def require_login(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.player is None or g.player.locked:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)

    return decorated_function


def require_clan_membership(f):
    """
        Request handler decorator that only allows access to an URL
        parametrized with the clan name if the logged in user is a member
        of the clan.
    :param f:
    :return:
    """

    @wraps(f)
    def decorated_f(*args, **kwargs):
        if g.player is None:
            return redirect(url_for('login', next=request.url))

        # Has to be a request handler with 'clan' as argument (e.g. /battles/<clan>/)
        if not 'clan' in kwargs:
            abort(500)
        if g.player.clan != kwargs['clan'] and g.player.name not in config.ADMINS:
            abort(403)
        return f(*args, **kwargs)

    return decorated_f


@decorator_with_args
def require_role(f, roles):
    """
        Request handler decorator that requires the logged in user to have a certain
        role, i.e. clan commander, treasurer, ...
    :param f:
    :param roles: iterable of strings with the allowed roles
    :return:
    """

    @wraps(f)
    def decorated_f(*args, **kwargs):
        if g.player is None:
            return redirect(url_for('login', next=request.url))
        if g.player.role not in roles and g.player.name not in config.ADMINS:
            abort(403)

        return f(*args, **kwargs)

    return decorated_f


############## API request handlers

@app.route('/sync-players/')
@app.route('/sync-players/<int:clan_id>')
def sync_players(clan_id=None):
    """
        Synchronize players in the database with Wargaming servers.
    :param clan_id:
    :return:
    """
    if config.API_KEY == request.args['API_KEY']:
        if clan_id:
            clan_ids = [clan_id]
        else:
            clan_ids = config.CLAN_IDS.values()
        for clan_id in clan_ids:
            logger.info("Clan member synchronization triggered for " + str(clan_id))
            webapp_data = WebappData.get()
            webapp_data.last_sync_attempt = datetime.datetime.now()
            db_session.add(webapp_data)
            db_session.commit()
            db_session.remove()

            clan_info = wotapi.get_clan(str(clan_id))
            player_ids = clan_info['data'][str(clan_id)]['members'].keys()
            players_info = wotapi.get_players(player_ids)
            member_info_data = {}
            for i in xrange(0, len(player_ids), 20):
                member_info_data.update(wotapi.get_players_membership_info(player_ids[i:i+20])['data'])

            processed = set()
            for player_id in player_ids:
                player = clan_info['data'][str(clan_id)]['members'][player_id]
                player_data = players_info['data'][player_id]
                member_data = member_info_data[player_id]
                p = Player.query.filter_by(wot_id=str(player['account_id'])).first()
                if not player_data:
                    if p:
                        processed.add(p.id)  # skip this guy later when locking players
                    logger.info("Missing player info of " + player['account_name'])
                    continue  # API Error?

                since = datetime.datetime.fromtimestamp(
                    float(member_data['since']))

                if p:
                    # Player exists, update information
                    processed.add(p.id)
                    p.name = player['account_name']
                    p.openid = 'https://'+config.WOT_SERVER_REGION_CODE+'.wargaming.net/id/' + str(player_id) + '-' + player['account_name'] + '/'
                    p.locked = False
                    p.clan = clan_info['data'][str(clan_id)]['abbreviation']
                    p.role = player['role']  # role might have changed
                    p.member_since = since  # might have rejoined
                else:
                    # New player
                    p = Player(str(player['account_id']),
                               'https://'+config.WOT_SERVER_REGION_CODE+'.wargaming.net/id/' + str(player['account_id']) + '-' + player[
                                   'account_name'] + '/',
                               since,
                               player['account_name'],
                               clan_info['data'][str(clan_id)]['abbreviation'],
                               player['role'])
                    logger.info('Adding player ' + player['account_name'])
                db_session.add(p)

            # All players of the clan in the DB, which are no longer in the clan
            for player in Player.query.filter_by(clan=clan_info['data'][str(clan_id)]['abbreviation']):
                if player.id in processed or player.id is None or player.locked:
                    continue
                logger.info("Locking player " + player.name)
                player.locked = True
                player.lock_date = datetime.datetime.now()
                db_session.add(player)

            webapp_data.last_successful_sync = datetime.datetime.now()
            db_session.add(webapp_data)
            db_session.commit()
            logger.info("Clan member synchronization successful")

    else:
        abort(403)

    return redirect(url_for('index'))


############## Public request handlers

@app.route("/")
def index():
    """
        Front page with latest battles played and scheduled battles.
    :return:
    """
    if g.player:
        latest_battles = Battle.query.filter_by(clan=g.player.clan).order_by('date desc').limit(3)

        # Cache provinces owned for 60 seconds to avoid spamming WG's server
        @cache.memoize(timeout=60)
        def cached_provinces_owned(clan_id):
            logger.info("Querying Wargaming server for provinces owned by clan " + str(clan_id) + " " + g.player.clan)
            try:
                return wotapi.get_provinces(clan_id)
            except Exception as e:
                logger.error(str(e))
                return None

        @cache.memoize(timeout=60)
        def cached_battle_schedule(clan_id):
            logger.info("Querying Wargaming server for battle schedule of clan " + str(clan_id) + " " + g.player.clan)
            try:
                return wotapi.get_battle_schedule(clan_id)
            except Exception as e:
                print e
                logger.error(str(e))
                return None

        provinces_owned = cached_provinces_owned(config.CLAN_IDS[g.player.clan])
        total_revenue = 0
        if provinces_owned:
            for p in provinces_owned['request_data']['items']:
                total_revenue += p['revenue']
        scheduled_battles = cached_battle_schedule(config.CLAN_IDS[g.player.clan])
    else:
        latest_battles = None
        scheduled_battles = None
        provinces_owned = None
        total_revenue = 0

    return render_template('index.html', clans=config.CLAN_NAMES, latest_battles=latest_battles,
                           scheduled_battles=scheduled_battles, provinces_owned=provinces_owned,
                           total_revenue=total_revenue, datetime=datetime)


@app.route('/admin')
@require_login
@require_role(config.ADMIN_ROLES)
def admin():
    """
        Administration page.
    :return:
    """
    return render_template('admin.html', webapp_data=WebappData.get(), API_KEY=config.API_KEY)


@app.route('/help')
def help_page():
    """
        Help page.
    :return:
    """
    return render_template('help.html')


@app.route('/attributions')
def attributions():
    """
        Page with attributions and licencing information.
    :return:
    """
    return render_template('attributions.html')


@app.route('/login', methods=['GET', 'POST'])
@oid.loginhandler
def login():
    """
        Login page.
    :return:
    """
    if g.player is not None:
        return redirect(oid.get_next_url())
    if request.method == 'POST':
        openid = request.form.get('openid', "http://eu.wargaming.net/id")
        if openid:
            return oid.try_login(openid, ask_for=['nickname'])
    return render_template('login.html', next=oid.get_next_url(),
                           error=oid.fetch_error())


@oid.after_login
def create_or_login(resp):
    """
        This is called when login with OpenID succeeded and it's not
        necessary to figure out if this is the users's first login or not.
        This function has to redirect otherwise the user will be presented
        with a terrible URL which we certainly don't want.
    """
    session['openid'] = resp.identity_url
    session['nickname'] = resp.nickname
    player = Player.query.filter_by(openid=resp.identity_url, locked=False).first()
    if player is not None:
        flash(u'Signed in successfully', 'success')
        session.permanent = True
        g.player = player
        return redirect(oid.get_next_url())
    return redirect(url_for('create_profile', next=oid.get_next_url(),
                            name=resp.nickname))


@app.route('/create-profile', methods=['GET', 'POST'])
def create_profile():
    """
        If this is the user's first login, the create_or_login function
        will redirect here so that the user can set up his profile.
    """
    if g.player is not None or 'openid' not in session or 'nickname' not in session:
        return redirect(url_for('index'))
    if request.method == 'POST':
        wot_id = [x for x in session['openid'].split('/') if x][-1].split('-')[0]
        if not wot_id:
            flash(u'Error: Could not determine your player ID from the OpenID string. Contact an admin for help :-)',
                  'error')
            return render_template('create_profile.html', next_url=oid.get_next_url())

        player_data = wotapi.get_player(wot_id)
        if not player_data or not player_data['data'][str(wot_id)] or not player_data['data'][str(wot_id)]['clan']:
            flash(u'Error: Could not retrieve player information from Wargaming. Contact an admin for help :-)',
                  'error')
            return render_template('create_profile.html', next_url=oid.get_next_url())

        clan_ids_to_name = dict((v, k) for k, v in config.CLAN_IDS.iteritems())
        clan_id = str(player_data['data'][str(wot_id)]['clan']['clan_id'])
        clan = clan_ids_to_name[str(clan_id)]
        if clan_id not in config.CLAN_IDS.values():
            flash(u'You have to be in one of the clans to login', 'error')
            return render_template('create_profile.html', next_url=oid.get_next_url())

        role = player_data['data'][str(wot_id)]['clan']['role']
        member_since = datetime.datetime.fromtimestamp(float(player_data['data'][str(wot_id)]['clan']['since']))
        if not role:
            flash(u'Error: Could not retrieve player role from wargaming server', 'error')
            return render_template('create_profile.html', next_url=oid.get_next_url())

        db_session.add(Player(wot_id, session['openid'], member_since, session['nickname'], clan, role))
        db_session.commit()
        logger.info("New player profile registered [" + session['nickname'] + ", " + clan + ", " + role + "]")
        flash(u'Welcome!', 'success')
        return redirect(oid.get_next_url())
    return render_template('create_profile.html', next_url=oid.get_next_url())


@app.route('/logout')
@require_login
def logout():
    """
        Log out the current user.
    :return:
    """
    session.pop('openid', None)
    session.pop('nickname', None)
    g.player = None
    flash(
        u'You were signed out from the tracker. You have to sign out from Wargaming\'s '
        u'website yourself if you wish to do that.',
        'info')
    return redirect(oid.get_next_url())


@app.route('/battles/create/from-replay', methods=['GET', 'POST'])
@require_login
@require_role(roles=config.CREATE_BATTLE_ROLES)
def create_battle_from_replay():
    """
        Upload replay form to create battles.
    :return:
    """
    if request.method == 'POST':
        replay_file = request.files['replay']
        if replay_file and replay_file.filename.endswith('.wotreplay'):
            battle_group_id = int(request.form.get('battle_group_id', -2))
            folder = datetime.datetime.now().strftime("%d.%m.%Y")
            filename = secure_filename(g.player.name + '_' + replay_file.filename)
            if not os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], folder)):
                os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], folder))
            replay_file.save(os.path.join(app.config['UPLOAD_FOLDER'], folder, filename))
            if battle_group_id:
                return redirect(
                    url_for('create_battle', battle_group_id=battle_group_id, folder=folder, filename=filename))
            else:
                return redirect(url_for('create_battle', folder=folder, filename=filename))
    return render_template('battles/create_from_replay.html')


@app.route('/battles/add-replay/<int:battle_id>', methods=['POST'])
@require_login
def add_replay(battle_id):
    """
        Upload additional replays for battles.
    """
    battle = Battle.query.get(battle_id) or abort(404)
    battle_replay = battle.replay
    if request.method == 'POST':
        replay_file = request.files['replay']
        if replay_file and replay_file.filename.endswith('.wotreplay'):
            replay_blob = replay_file.read()
            replay = replays.parse_replay(replay_blob)

            if set(replays.player_team(replay)) != set(replays.player_team(battle_replay.unpickle())):
                flash(u'The selected replay is most likely from a different battle (list of players differs)', 'error')
                return redirect(url_for('battle_details', battle_id=battle.id))

            if replay['first']['mapName'] != battle_replay.unpickle()['first']['mapName']:
                flash(u'The selected replay is most likely for a different battle (map name differs)', 'error')
                return redirect(url_for('battle_details', battle_id=battle.id))

            if replay['first']['playerName'] == battle_replay.player_name:
                flash(u'Replay of this player already exists', 'error')
                return redirect(url_for('battle_details', battle_id=battle.id))

            for existing_replay in battle.additional_replays:
                if existing_replay.player_name == replay['first']['playerName']:
                    flash(u'Replay of this player already exists', 'error')
                    return redirect(url_for('battle_details', battle_id=battle.id))

            r = Replay(replay_blob, pickle.dumps(replay))
            r.associated_battle = battle
            r.player_name = replay['first']['playerName']
            db_session.commit()

    return redirect(url_for('battle_details', battle_id=battle.id))


@app.route('/battles/edit/<int:battle_id>', methods=['GET', 'POST'])
@require_login
@require_role(roles=config.CREATE_BATTLE_ROLES)
def edit_battle(battle_id):
    """
        Edit battle form.
    :param battle_id:
    :return:
    """
    battle = Battle.query.get(battle_id) or abort(404)
    if battle.clan != g.player.clan and g.player.name not in config.ADMINS:
        abort(403)

    all_players = Player.query.filter_by(clan=g.player.clan, locked=False).order_by('lower(name)').all()
    sorted_players = sorted(all_players, reverse=True, key=lambda p: p.player_role_value())
    date = battle.date
    map_name = battle.map_name
    province = battle.map_province
    battle_commander = battle.battle_commander
    enemy_clan = battle.enemy_clan
    battle_groups = BattleGroup.query.filter_by(clan=g.player.clan).order_by('date').all()
    battle_result = battle.outcome_repr()
    battle_group_final = battle.battle_group_final
    players = battle.get_players()
    description = battle.description
    replay = battle.replay.unpickle()
    duration = battle.duration
    if battle.battle_group:
        battle_group_description = battle.battle_group.description
    else:
        battle_group_description = ''

    if request.method == 'POST':
        players = map(int, request.form.getlist('players'))
        map_name = request.form.get('map_name', '')
        province = request.form.get('province', '')
        enemy_clan = request.form.get('enemy_clan', '')
        battle_result = request.form.get('battle_result', '')
        battle_commander = Player.query.get(int(request.form['battle_commander']))
        description = request.form.get('description', '')
        battle_group = int(request.form['battle_group'])
        battle_group_title = request.form.get('battle_group_title', '')
        battle_group_description = request.form.get('battle_group_description', '')
        battle_group_final = request.form.get('battle_group_final', '') == 'on'
        duration = request.form.get('duration', 15 * 60)

        errors = False
        date = None
        try:
            date = datetime.datetime.strptime(request.form.get('date', ''), '%d.%m.%Y %H:%M:%S')
        except ValueError:
            flash(u'Invalid date format', 'error')
            errors = True
        if not map_name:
            flash(u'Please enter the name of the map', 'error')
            errors = True
        if not battle_commander:
            flash(u'No battle commander selected', 'error')
            errors = True
        if not players:
            flash(u'No players selected', 'error')
            errors = True
        if not enemy_clan:
            flash(u'Please enter the enemy clan\'s tag', 'errors')
            errors = True
        if not battle_result:
            flash(u'Please select the correct outcome of the battle', 'errors')
            errors = True

        bg = None
        if battle_group == -1:
            # new group
            bg = BattleGroup(battle_group_title, battle_group_description, g.player.clan, date)
        elif battle_group >= 0:
            # existing group
            bg = BattleGroup.query.get(battle_group) or abort(500)
            if bg.get_final_battle() is not None and bg.get_final_battle() is not battle and battle_group_final:
                flash(u'Selected battle group already contains a battle marked as final')
                errors = True

        if not errors:
            battle.date = date
            battle.clan = g.player.clan
            battle.enemy_clan = enemy_clan
            battle.victory = battle_result == 'victory'
            battle.draw = battle_result == 'draw'
            battle.map_name = map_name
            battle.map_province = province
            battle.battle_commander_id = battle_commander.id
            battle.description = description
            battle.duration = duration

            if bg:
                battle.battle_group_final = battle_group_final
                battle.battle_group = bg
                db_session.add(bg)
            else:
                battle.battle_group = None

            for ba in battle.attendances:
                if not ba.reserve:
                    db_session.delete(ba)

            for player_id in players:
                player = Player.query.get(player_id)
                if not player:
                    abort(404)
                ba = BattleAttendance(player, battle, reserve=False)
                db_session.add(ba)

            db_session.add(battle)
            db_session.commit()
            logger.info(g.player.name + " updated the battle " + str(battle.id))
            return redirect(url_for('battles_list', clan=g.player.clan))

    return render_template('battles/edit.html', date=date, map_name=map_name, province=province, battle=battle,
                           battle_groups=battle_groups, duration=duration, battle_group_description=battle_group_description,
                           battle_commander=battle_commander, enemy_clan=enemy_clan, battle_result=battle_result,
                           battle_group_final=battle_group_final, players=players, description=description,
                           replay=replay, replays=replays, all_players=all_players, sorted_players=sorted_players)


@app.route('/battles/create', methods=['GET', 'POST'])
@require_login
@require_role(roles=config.CREATE_BATTLE_ROLES)
def create_battle():
    """
        Create battle form.
    :return:
    """
    all_players = Player.query.filter_by(clan=g.player.clan, locked=False).order_by('lower(name)').all()
    sorted_players = sorted(all_players, reverse=True, key=lambda p: p.player_role_value())

    # Prefill form with data from replay
    enemy_clan = ''
    players = []
    replay = None
    description = ''
    battle_result = ''
    map_name = ''
    province = ''
    duration = 15 * 60
    battle_commander = None
    date = datetime.datetime.now()
    battle_groups = BattleGroup.query.filter_by(clan=g.player.clan).order_by('date').all()
    battle_group = ''
    battle_group_id = int(request.args.get('battle_group_id', -2))
    battle_group_title = ''
    battle_group_description = ''
    battle_group_final = False
    filename = request.args.get('filename', '')
    folder = request.args.get('folder', '')
    if request.method == 'POST':
        filename = request.form.get('filename', '')
        folder = request.form.get('folder', '')

    if filename:
        file_blob = open(os.path.join(app.config['UPLOAD_FOLDER'], folder, secure_filename(filename)), 'rb').read()
        replay = replays.parse_replay(file_blob)
        if not replay:
            flash(u'Error: Parsing replay file failed :-(.', 'error')
        else:
            clan = replays.guess_clan(replay)
            if clan not in config.CLAN_NAMES or clan != g.player.clan:
                flash(
                    u'Error: "Friendly" clan was not in the list of clans '
                    u'supported by this website or you are not a member',
                    'error')
            map_name = constants.MAP_EN_NAME_BY_ID.get(replay['first']['mapName'], 'Unknown')
            all_players = Player.query.filter_by(clan=clan, locked=False).order_by('lower(name)')
            players = Player.query.filter(Player.name.in_(replays.player_team(replay))).order_by('lower(name)').all()
            if g.player in players:
                battle_commander = g.player.id
            date = datetime.datetime.strptime(replay['first']['dateTime'], '%d.%m.%Y %H:%M:%S')

            if not replay['second']:
                flash(u'Error: Uploaded replay file is incomplete (Battle was left before it ended). ' +
                      u'Can not determine all information automatically.', 'error')
            elif not replays.is_cw(replay):
                flash(
                    u'Error: Uploaded replay file is probably not from a clan war '
                    u'(Detected different clan tags in one of the team' +
                    u' or players from the same clan on both sides)', 'error')
            else:
                enemy_clan = replays.guess_enemy_clan(replay)
                if replays.player_won(replay):
                    battle_result = 'victory'

            if replay['second']:
                duration = int(replay['second'][0]['common']['duration'])
            else:
                flash('Warning. Replay seems to be incomplete (detailed battle information is missing). '
                      'Cannot determine battle duration automatically and replay cannot be used in player performance'
                      ' calculation!', 'error')

    if request.method == 'POST':
        players = map(int, request.form.getlist('players'))
        filename = request.form.get('filename', '')
        folder = request.form.get('folder', '')
        map_name = request.form.get('map_name', '')
        province = request.form.get('province', '')
        enemy_clan = request.form.get('enemy_clan', '')
        battle_result = request.form.get('battle_result', '')
        battle_commander = Player.query.get(int(request.form['battle_commander']))
        description = request.form.get('description', '')
        duration = request.form.get('duration', 15 * 60)
        battle_group = int(request.form['battle_group'])
        battle_group_title = request.form.get('battle_group_title', '')
        battle_group_description = request.form.get('battle_group_description', '')
        battle_group_final = request.form.get('battle_group_final', '') == 'on'
        file_blob = None

        errors = False
        date = None
        try:
            date = datetime.datetime.strptime(request.form.get('date', ''), '%d.%m.%Y %H:%M:%S')
        except ValueError:
            flash(u'Invalid date format', 'error')
            errors = True

        # Validation
        if filename:
            file_blob = open(os.path.join(app.config['UPLOAD_FOLDER'], folder, secure_filename(filename)), 'rb').read()
        else:
            if not 'replay' in request.files or not request.files['replay']:
                flash(u'No replay selected', 'error')
                errors = True
            else:
                file_blob = request.files['replay'].read()
        if not map_name:
            flash(u'Please enter the name of the map', 'error')
            errors = True
        if not battle_commander:
            flash(u'No battle commander selected', 'error')
            errors = True
        if not players:
            flash(u'No players selected', 'error')
            errors = True
        if not enemy_clan:
            flash(u'Please enter the enemy clan\'s tag', 'errors')
            errors = True
        if not battle_result:
            flash(u'Please select the correct outcome of the battle', 'errors')
            errors = True
        if not duration:
            flash(u'Please provide the duration of the battle', 'errors')
            errors = True

        battle = Battle.query.filter_by(date=date, clan=g.player.clan, enemy_clan=enemy_clan).first()
        if battle:
            # The battle is already in the system.
            flash(u'Battle already exists (same date, clan and enemy clan).', 'error')
            errors = True

        bg = None
        if battle_group == -1:
            # new group
            bg = BattleGroup(battle_group_title, battle_group_description, g.player.clan, date)
        elif battle_group >= 0:
            # existing group
            bg = BattleGroup.query.get(battle_group) or abort(500)
            if bg.get_final_battle() and battle_group_final:
                flash(u'Selected battle group already contains a battle marked as final')
                errors = True

        if not errors:
            battle = Battle(date, g.player.clan, enemy_clan, victory=(battle_result == 'victory'),
                            map_name=map_name, map_province=province,
                            draw=(battle_result == 'draw'), creator=g.player,
                            battle_commander=battle_commander, description=description,
                            duration=duration)

            if bg:
                battle.battle_group_final = battle_group_final
                battle.battle_group = bg
                db_session.add(bg)

            if config.STORE_REPLAYS_IN_DB:
                battle.replay = Replay(file_blob, pickle.dumps(replay))
            else:
                battle.replay = Replay(None, pickle.dumps(replay))

            battle.replay.player_name = replay['first']['playerName']

            for player_id in players:
                player = Player.query.get(player_id)
                if not player:
                    abort(404)
                ba = BattleAttendance(player, battle, reserve=False)
                db_session.add(ba)

            db_session.add(battle)
            db_session.commit()
            logger.info(g.player.name + " added the battle " + str(battle.id))
            return redirect(url_for('battles_list', clan=g.player.clan))

    return render_template('battles/create.html', CLAN_NAMES=config.CLAN_NAMES, all_players=all_players,
                           players=players,
                           enemy_clan=enemy_clan, filename=filename, folder=folder, replay=replay,
                           battle_commander=battle_commander,
                           map_name=map_name, province=province, description=description, replays=replays,
                           battle_result=battle_result, date=date, battle_groups=battle_groups,
                           battle_group=battle_group, battle_group_title=battle_group_title, duration=duration,
                           battle_group_description=battle_group_description, battle_group_final=battle_group_final,
                           sorted_players=sorted_players, battle_group_id=battle_group_id)


@app.route('/battles/list/<clan>')
@require_login
def battles_list(clan):
    """
        Table of all battles of a clan.
    :param clan:
    :return:
    """
    if not clan in config.CLAN_NAMES:
        abort(404)
    battles = Battle.query.options(joinedload_all('battle_group.battles')).options(
        joinedload_all('attendances.player')).filter_by(clan=clan)
    if 'enemy' in request.args:
        battles = battles.filter_by(enemy_clan=request.args.get('enemy', None))
    battles = battles.all()
    return render_template('battles/battles.html', clan=clan, battles=battles)


@app.route('/battles/group/<int:group_id>')
@require_login
def battle_group_details(group_id):
    """
        Battle group details page with table of the individual battles.
    :param group_id:
    :return:
    """
    bg = BattleGroup.query.options(joinedload_all('battles.attendances.player')).get(group_id) or abort(404)

    return render_template('battles/battle_group.html', battle_group=bg, battles=bg.battles,
                           clan=bg.clan)


@app.route('/battles/<int:battle_id>')
@require_login
def battle_details(battle_id):
    """
        Battle details page.
    :param battle_id:
    :return:
    """
    battle = Battle.query.get(battle_id) or abort(404)
    return render_template('battles/battle.html', battle=battle, replays=replays)


@app.route('/battles/<int:battle_id>/delete')
@require_login
@require_role(config.DELETE_BATTLE_ROLES)
def delete_battle(battle_id):
    """
        Delete battle from the database.
    :param battle_id:
    :return:
    """
    battle = Battle.query.get(battle_id) or abort(404)
    if battle.clan != g.player.clan and g.player.name not in config.ADMINS:
        abort(403)
    for ba in battle.attendances:
        db_session.delete(ba)
    if battle.battle_group and len(battle.battle_group.battles) == 1:
        # last battle in battle group, delete the group as well
        db_session.delete(battle.battle_group)
    db_session.delete(battle)
    logger.info(g.player.name + " deleted the battle " + str(battle.id) + " " + str(battle))
    db_session.commit()

    return redirect(url_for('battles_list', clan=g.player.clan))


@app.route('/players/<clan>')
@require_login
def clan_players(clan):
    """
        List of players with participation of a clan.
    :param clan:
    :return:
    """
    if not clan in config.CLAN_NAMES:
        abort(404)
    players = Player.query.options(joinedload_all('battles.battle')).filter_by(clan=clan, locked=False).all()
    possible = defaultdict(int)
    reserve = defaultdict(int)
    played = defaultdict(int)
    present = defaultdict(int)
    clan_battles = Battle.query.options(joinedload_all('attendances.player')).filter_by(clan=clan).order_by(
        'date asc').all()
    battle_groups = BattleGroup.query.options(joinedload_all('battles.attendances.player')).filter_by(clan=clan).all()
    players_by_battle_group_id = dict()
    reserves_by_battle_group_id = dict()
    for bg in battle_groups:
        players_by_battle_group_id[bg.id] = bg.get_players()
        reserves_by_battle_group_id[bg.id] = bg.get_reserves()

    last_battle_by_player = dict()
    for p in players:
        last_battle = None
        for ba in p.battles:
            if ba.battle.clan == p.clan and (last_battle is None or ba.battle.date > last_battle.date):
                last_battle = ba.battle
        last_battle_by_player[p] = last_battle

    for player in players:
        for battle in clan_battles:
            if battle.date < player.member_since:
                continue
            if battle.battle_group_id and not battle.battle_group_final:
                continue  # only finals will count
            possible[player] += 1

            if battle.battle_group_id:
                if player in players_by_battle_group_id[battle.battle_group_id]:
                    played[player] += 1
                    present[player] += 1
                elif player in reserves_by_battle_group_id[battle.battle_group_id]:
                    reserve[player] += 1
                    present[player] += 1
            else:
                if battle.has_player(player):
                    played[player] += 1
                    present[player] += 1
                elif battle.has_reserve(player):
                    reserve[player] += 1
                    present[player] += 1

    # 30 days stats
    oldest_date = datetime.datetime.now() - datetime.timedelta(days=30)
    possible30 = defaultdict(int)
    reserve30 = defaultdict(int)
    played30 = defaultdict(int)
    present30 = defaultdict(int)
    clan_battles = Battle.query.options(joinedload_all('attendances.player')) \
        .filter_by(clan=clan).filter(Battle.date > oldest_date).order_by('date asc').all()
    for player in players:
        for battle in clan_battles:
            if battle.date < player.member_since:
                continue
            if battle.battle_group_id and not battle.battle_group_final:
                continue  # only finals will count
            possible30[player] += 1

            if battle.battle_group:
                if player in players_by_battle_group_id[battle.battle_group_id]:
                    played30[player] += 1
                    present30[player] += 1
                elif player in reserves_by_battle_group_id[battle.battle_group_id]:
                    reserve30[player] += 1
                    present30[player] += 1
            else:
                if battle.has_player(player):
                    played30[player] += 1
                    present30[player] += 1
                elif battle.has_reserve(player):
                    reserve30[player] += 1
                    present30[player] += 1

    return render_template('players/players.html', clan=clan, players=players,
                           played=played, present=present, possible=possible, reserve=reserve,
                           played30=played30, present30=present30, possible30=possible30,
                           last_battle_by_player=last_battle_by_player)


@app.route('/players/<int:player_id>')
def player_details(player_id):
    """
        Player details page.
    :param player_id:
    :return:
    """
    player = Player.query.get(player_id) or abort(404)

    # current month stats
    today = datetime.datetime.now()
    oldest_date = datetime.datetime(today.year, today.month, 1)
    possible = 0
    reserve = 0
    played = 0
    present = 0
    wins = 0
    clan_battles = Battle.query.options(joinedload_all('attendances.player')) \
        .filter_by(clan=player.clan).filter(Battle.date > oldest_date).order_by('date asc').all()
    for battle in clan_battles:
        if battle.date < player.member_since:
            continue
        if battle.battle_group_id and not battle.battle_group_final:
            continue  # only finals will count
        possible += 1

        if battle.battle_group:
            if player in battle.battle_group.get_players():
                if battle.victory:
                    wins += 1
                played += 1
                present += 1
            elif player in battle.battle_group.get_reserves():
                reserve += 1
                present += 1
        else:
            if battle.has_player(player):
                if battle.victory:
                    wins += 1
                played += 1
                present += 1
            elif battle.has_reserve(player):
                reserve += 1
                present += 1
    return render_template('players/player.html', player=player, possible=possible, present=present, played=played,
                           reserve=reserve, oldest_date=oldest_date, wins=wins)


@app.route('/battles/<int:battle_id>/sign-reserve')
@require_login
def sign_as_reserve(battle_id):
    """
        Sign currently logged in player as reserve of a battle.
    :param battle_id:
    :return:
    """
    battle = Battle.query.get(battle_id) or abort(404)
    if battle.clan != g.player.clan and g.player.name not in config.ADMINS:
        abort(403)
    if not config.RESERVE_SIGNUP_ALLOWED:
        abort(403)
    back_to_battle = 'back_to_battle' in request.args
    # disallow signing as reserve for old battles
    if battle.date < datetime.datetime.now() - config.RESERVE_SIGNUP_DURATION:
        flash(u"Can't sign up as reserve for battles older than 24 hours. Contact an admin if needed.")
        if back_to_battle:
            return redirect(url_for('battle_details', battle_id=battle.id))
        return redirect(url_for('battles_list', clan=g.player.clan))

    if not battle.has_player(g.player) and not battle.has_reserve(g.player):
        ba = BattleAttendance(g.player, battle, reserve=True)
        db_session.add(ba)
        logger.info(g.player.name + " signed himself as reserve for " + str(battle))
        db_session.commit()

    if back_to_battle:
        return redirect(url_for('battle_details', battle_id=battle.id))

    return redirect(url_for('battles_list', clan=g.player.clan))


@app.route('/battles/<int:battle_id>/unsign-reserve')
@require_login
def unsign_as_reserve(battle_id):
    """
        Remove currently logged in player as reserve from a battle.
    :param battle_id:
    :return:
    """
    battle = Battle.query.get(battle_id) or abort(404)
    if battle.clan != g.player.clan and g.player.name not in config.ADMINS:
        abort(403)
    if not config.RESERVE_SIGNUP_ALLOWED:
        abort(403)
    back_to_battle = 'back_to_battle' in request.args
    if battle.date < datetime.datetime.now() - config.RESERVE_SIGNUP_DURATION:
        flash(u"Can't sign up as reserve for battles older than 24 hours. Contact an admin if needed.")
        if back_to_battle:
            return redirect(url_for('battle_details', battle_id=battle.id))
        return redirect(url_for('battles_list', clan=g.player.clan))

    ba = BattleAttendance.query.filter_by(player=g.player, battle=battle, reserve=True).first() or abort(500)
    db_session.delete(ba)
    logger.info(g.player.name + " removed himself as reserve for " + str(battle))
    db_session.commit()

    if back_to_battle:
        return redirect(url_for('battle_details', battle_id=battle.id))

    return redirect(url_for('battles_list', clan=g.player.clan))


@app.route('/battles/<int:battle_id>/download-replay/')
@require_login
def download_replay(battle_id):
    """
        Replay download handler. Returns the requested replay blob as binary download.
    :param battle_id:
    :return:
    """
    battle = Battle.query.get(battle_id) or abort(404)
    if not battle.replay_id:
        abort(404)
    if not battle.replay.replay_blob:
        abort(404)
    response = make_response(battle.replay.replay_blob)
    response.headers['Content-Type'] = 'application/octet-stream'
    response.headers['Content-Disposition'] = 'attachment; filename=' + \
                                              secure_filename(battle.date.strftime(
                                                  '%d.%m.%Y_%H_%M_%S') + '_' + battle.clan + '_' +
                                              battle.enemy_clan + '.wotreplay')
    return response


@app.route('/replays/download/<int:replay_id>')
@require_login
def download_additional_replay(replay_id):
    """
        Replay download handler. Returns the requested replay blob as binary download.
    :param replay_id:
    :return:
    """
    replay = Replay.query.get(replay_id) or abort(404)
    battle = replay.associated_battle
    if not replay.replay_blob:
        abort(404)
    response = make_response(replay.replay_blob)
    response.headers['Content-Type'] = 'application/octet-stream'
    response.headers['Content-Disposition'] = 'attachment; filename=' + \
                                              secure_filename(battle.date.strftime(
                                                  '%d.%m.%Y_%H_%M_%S') + '_' + battle.clan + '_' +
                                              battle.enemy_clan + '.wotreplay')
    return response


@app.route('/replays/delete/<int:replay_id>')
@require_login
@require_role(config.DELETE_BATTLE_ROLES)
def delete_replay(replay_id):
    replay = Replay.query.get(replay_id) or abort(404)
    battle_id = replay.associated_battle_id

    db_session.delete(replay)
    db_session.commit()

    return redirect(url_for('battle_details', battle_id=battle_id))


@app.route('/battles/download-replays')
@require_login
def download_replays():
    battle_ids = map(int, request.args.getlist('ids[]'))
    if not battle_ids:
        abort(404)

    buf = StringIO()
    tar = tarfile.open(mode='w', fileobj=buf)
    for battle in Battle.query.filter(Battle.id.in_(battle_ids)):
        if not battle.replay or not battle.replay.replay_blob:
            continue
        filename = secure_filename(battle.date.strftime(
            '%d.%m.%Y_%H_%M_%S') + '_' + battle.clan + '_' + battle.enemy_clan + '.wotreplay')
        info = tarfile.TarInfo(filename)
        info.size = len(battle.replay.replay_blob)
        info.mtime = calendar.timegm(battle.date.utctimetuple())
        info.type = tarfile.REGTYPE
        tar.addfile(info, StringIO(battle.replay.replay_blob))
    tar.close()

    response = make_response(buf.getvalue())
    response.headers['Content-Type'] = 'application/tar'
    response.headers['Content-Disposition'] = 'attachment; filename=' + secure_filename("replays.tar")
    return response


@app.route('/payout/<clan>')
@require_login
@require_role(config.PAYOUT_ROLES)
@require_clan_membership
def payout(clan):
    """
        Payout date range and battle selection page.
    :param clan:
    :return:
    """
    return render_template('payout/payout.html', clan=clan)


@app.route('/payout/reserve-conflicts/<clan>')
@require_login
@require_role(config.PAYOUT_ROLES)
@require_clan_membership
def reserve_conflicts(clan):
    # noinspection PyShadowingNames
    def overlapping_battles(battle, ordered_battles, before_dt=timedelta(minutes=0), after_dt=timedelta(minutes=0)):
        """ Return a list of battles b whose start time lies within the interval
            [battle.date - before_dt, battle.date + battle.duration + after_dt].
            Such battles overlap with the given battle. """
        return [b for b in ordered_battles if battle.date - before_dt <= b.date <=
                battle.date + timedelta(seconds=battle.duration or (15*60)) + after_dt]

    # noinspection PyShadowingNames
    def get_reserve_conflicts(battles):
        """ Returns the players that are reserve in at least two of the given battles """
        reserve_count = defaultdict(int)
        for battle in battles:
            for player in battle.get_reserve_players():
                reserve_count[player] += 1
        return sorted([p for p in reserve_count if reserve_count[p] > 1], key=lambda p: p.name)

    battles = Battle.query.options(joinedload('attendances')).filter_by(clan=clan).order_by('date asc').all()
    all_reserve_conflicts = OrderedDict()
    for battle in battles:
        overlaps = overlapping_battles(battle, battles)
        conflicts = get_reserve_conflicts(overlaps)
        if conflicts:
            all_reserve_conflicts[tuple(overlaps)] = conflicts

    return render_template('payout/reserve_conflicts.html', reserve_conflicts=all_reserve_conflicts)


@app.route('/payout/<clan>/battles', methods=['GET', 'POST'])
@require_login
@require_role(config.PAYOUT_ROLES)
@require_clan_membership
def payout_battles(clan):
    """
        Main payout calculation page.
    :param clan:
    :return:
    """
    if request.method == 'POST':
        from_date = request.form['fromDate']
        to_date = request.form['toDate']
        gold = int(request.form['gold'])
        victories_only = request.form.get('victories_only', False)
    else:
        from_date = request.args.get('fromDate')
        to_date = request.args.get('toDate')
        gold = int(request.args.get('gold'))
        victories_only = request.args.get('victories_only', False) == 'on'

    from_date = datetime.datetime.strptime(from_date, '%d.%m.%Y')
    to_date = datetime.datetime.strptime(to_date, '%d.%m.%Y') + datetime.timedelta(days=1)
    battles = Battle.query.options(joinedload('attendances')).filter_by(clan=clan).filter(
        Battle.date >= from_date, Battle.date <= to_date,
        or_(Battle.battle_group_id == None, Battle.battle_group_final == True))
    if victories_only:
        battles = battles.filter_by(victory=True)
    battles = battles.all()

    clan_members = Player.query.filter_by(clan=clan, locked=False).all()
    player_fced_win = defaultdict(int)
    player_fced_defeat = defaultdict(int)
    player_fced_draws = defaultdict(int)
    player_played = defaultdict(int)
    player_reserve = defaultdict(int)
    player_victories = defaultdict(int)
    player_defeats = defaultdict(int)
    player_draws = defaultdict(int)
    for battle in battles:
        if battle.battle_group and not battle.battle_group_final:
            continue  # only finals count

        if battle.battle_group and battle.battle_group_final:
            battle_players = battle.battle_group.get_players()
            battle_reserves = battle.battle_group.get_reserves()
        else:
            battle_players = battle.get_players()
            battle_reserves = battle.get_reserve_players()

        battle_commander = battle.battle_commander
        if not battle_commander.locked:
            if battle.victory:
                player_fced_win[battle_commander] += 1
            elif battle.draw:
                player_fced_draws[battle_commander] += 1
            else:
                player_fced_defeat[battle_commander] += 1

        for p in battle_players:
            if p.locked or p == battle_commander:
                continue
            player_played[p] += 1
            if battle.victory:
                player_victories[p] += 1
            elif battle.draw:
                player_draws[p] += 1
            else:
                player_defeats[p] += 1

        for p in battle_reserves:
            if p.locked:
                continue
            player_reserve[p] += 1

    players = set()
    for p in clan_members:
        if player_played[p] or player_reserve[p] or player_fced_win[p] or player_fced_defeat[p]:
            players.add(p)

    player_points = dict()
    for p in players:
        player_points[p] = player_fced_win[p] * 6 + player_fced_defeat[p] * 4 + player_fced_draws[p] * 2 + \
                           player_victories[p] * 3 + player_defeats[p] * 2 + player_draws[p] * 2 + player_reserve[p]
    total_points = sum(player_points[p] for p in players)
    player_gold = dict()
    for p in players:
        player_gold[p] = int(round(player_points[p] / float(total_points) * gold))

    return render_template('payout/payout_battles.html', battles=battles, clan=clan, fromDate=from_date, toDate=to_date,
                           player_played=player_played, player_reserve=player_reserve, players=players,
                           player_gold=player_gold, gold=gold, player_defeats=player_defeats,
                           player_fced_win=player_fced_win, victories_only=victories_only,
                           player_fced_defeat=player_fced_defeat, player_victories=player_victories,
                           player_fced_draws=player_fced_draws, player_draws=player_draws, player_points=player_points)


@app.route('/players/json')
@require_login
def players_json():
    clan = request.args.get('clan')
    players = Player.query.filter_by(clan=clan, locked=False).all()

    return jsonify(
        {"players": [player.to_dict() for player in players]}
    )


@app.route('/reserve-players/json/<clan>/<int:battle_id>')
@require_login
def reserve_players_json(clan, battle_id):
    battle = Battle.query.get(battle_id) or abort(404)
    battle_player_ids = [p.id for p in (battle.get_players() + battle.get_reserve_players())]
    players = Player.query.filter_by(clan=clan, locked=False).filter(Player.id.notin_(battle_player_ids)).order_by(
        'name asc')
    q = request.args.get('q', None)
    if q:
        players = players.filter(Player.name.ilike('%' + q + '%'))
    players = players.all()

    return jsonify(
        {"players": [player.to_dict() for player in players]}
    )


@app.route('/battle-players-update/<int:battle_id>', methods=['PUT'])
@require_login
@require_role(config.CREATE_BATTLE_ROLES)
def battle_reserves_update(battle_id):
    battle = Battle.query.get(battle_id) or abort(404)
    reserves = request.json
    reserve_before = set()
    for ba in battle.attendances:
        if ba.reserve:
            reserve_before.add(ba.player)
            db_session.delete(ba)
    reserve_now = set()
    for reserve in reserves:
        player = Player.query.get(reserve['id'])
        reserve_now.add(player)
        ba = BattleAttendance(player, battle, reserve=True)
        db_session.add(ba)
    db_session.commit()
    logger.info(g.player.name + " updated the reserves for " + str(battle) + " - added: " +
                ", ".join([p.name for p in (reserve_now - reserve_before)]) + " - deleted: " +
                ", ".join([p.name for p in (reserve_before - reserve_now)]))
    return jsonify({"status": "ok"})


@app.route('/payout/battles')
@require_login
@require_role(config.PAYOUT_ROLES)
def payout_battles_json():
    """
        Ajax request handler for battles on the payout page.
        Returns selected battles serialized as JSON.
    :return:
    """
    clan = request.args.get('clan', None)
    if g.player.clan != clan and not g.player.name in config.ADMINS:
        abort(403)
    from_date = request.args.get('fromDate', None)
    to_date = request.args.get('toDate', None)

    if not clan or not from_date or not to_date:
        return jsonify({
            "sEcho": 1,
            "iTotalRecords": 0,
            "iTotalDisplayRecords": 0,
            "aaData": []
        })

    from_date = datetime.datetime.strptime(from_date, '%d.%m.%Y')
    to_date = datetime.datetime.strptime(to_date, '%d.%m.%Y') + datetime.timedelta(days=1)
    victories_only = request.args.get('victories_only', False) == 'on'
    battles = Battle.query.filter_by(clan=clan).filter(Battle.date >= from_date, Battle.date <= to_date,
                                                       or_(Battle.battle_group_id == None,
                                                           Battle.battle_group_final == True))
    if victories_only:
        battles = battles.filter_by(victory=True)
    battles = battles.all()
    return jsonify({
        "sEcho": 1,
        "iTotalRecords": len(battles),
        "iTotalDisplayRecords": len(battles),
        "aaData": [
            [battle.id,
             battle.date.strftime('%d.%m.%Y %H:%M:%S'),
             battle.enemy_clan,
             battle.creator.name,
             battle.outcome_str()] for battle in battles
        ]
    })


@app.route('/players/commanded/<clan>')
@require_login
@require_role(config.COMMANDED_ROLES)
def players_commanded(clan):
    commanders = Player.query.filter_by(locked=False, clan=clan).filter(Player.id.in_(db_session.query(Battle.battle_commander_id) \
                                .distinct())).order_by(Player.name).all()

    return render_template('players/commanding.html', commanders=commanders, clan=clan)


@app.route('/players/commanded-json')
@require_login
@require_role(config.COMMANDED_ROLES)
def players_commanded_json():
    from_date = request.args.get('fromDate', None) or abort(404)
    to_date = request.args.get('toDate', None) or abort(404)

    from_date = datetime.datetime.strptime(from_date, '%d.%m.%Y')
    to_date = datetime.datetime.strptime(to_date, '%d.%m.%Y') + datetime.timedelta(days=1)
    commander = Player.query.get(int(request.args.get('commander_id'))) or abort(404)
    use_battle_groups = request.args.get('use_battle_groups', False) == 'on'

    battles = Battle.query.options(joinedload_all('battle_group.battles')).options(
        joinedload_all('attendances.player')).filter(Battle.date >= from_date).filter(Battle.date <= to_date) \
                            .filter_by(battle_commander=commander)
    player_count = defaultdict(int)
    for battle in battles:
        if use_battle_groups:
            if battle.battle_group_id and battle.battle_group_final:
                players = battle.battle_group.get_players()
            elif not battle.battle_group_id:
                players = battle.get_players()
            else:
                continue
        else:
            players = battle.get_players()

        for player in players:
            player_count[player] += 1

    return jsonify({
        "sEcho": 1,
        "iTotalRecords": len(player_count),
        "iTotalDisplayRecords": len(player_count),
        "aaData": [
            (k.name,
             v) for k, v in player_count.iteritems()
        ]
    })


@app.route('/statistics/<clan>')
@require_login
@require_clan_membership
def clan_statistics(clan):
    """
        Display clan statistics such as number of battles played recently.
    :param clan:
    :return:
    """
    battles_query = Battle.query.filter_by(clan=clan)

    battles = battles_query.all()
    battles_won = battles_query.filter_by(victory=True).count()

    battles_one_week_query = battles_query.filter(Battle.date >= datetime.datetime.now() - datetime.timedelta(days=7))
    battles_one_week = battles_one_week_query.all()
    battles_one_week_won = battles_one_week_query.filter_by(victory=True).count()

    battles_thirty_days_query = battles_query.filter(
        Battle.date >= datetime.datetime.now() - datetime.timedelta(days=30))
    battles_thirty_days = battles_thirty_days_query.all()
    battles_thirty_days_won = battles_thirty_days_query.filter_by(victory=True).count()

    # Battles played by map
    wins_by_commander = defaultdict(int)
    battles_by_commander = defaultdict(int)
    battles_by_map = defaultdict(int)
    victories_by_map = defaultdict(int)
    battles_by_enemy = defaultdict(int)
    wins_by_enemy = defaultdict(int)
    for battle in battles:
        battles_by_commander[battle.battle_commander] += 1
        battles_by_map[battle.map_name] += 1
        battles_by_enemy[battle.enemy_clan] += 1
        if battle.victory:
            wins_by_enemy[battle.enemy_clan] += 1
            victories_by_map[battle.map_name] += 1
            wins_by_commander[battle.battle_commander] += 1
    map_battles = list(battles_by_map.iteritems())

    win_ratio_by_commander = dict(
        (c, wins_by_commander[c] / float(battles_by_commander[c])) for c in battles_by_commander
        if battles_by_commander[c] > 10)

    # Win ratio by map
    win_ratio_by_map = dict()
    for map_name in battles_by_map:
        win_ratio_by_map[map_name] = float(victories_by_map[map_name]) / battles_by_map[map_name]

    enemies_by_battle_count = defaultdict(int)
    for enemy_clan in battles_by_enemy:
        enemies_by_battle_count[battles_by_enemy[enemy_clan]] += 1

    battle_count_cutoff = 0
    for battle_count in range(1, max(battles_by_enemy.values())):
        if enemies_by_battle_count[battle_count] <= 20:
            battle_count_cutoff = battle_count
            break

    # Win ratio by enemy clan
    win_ratio_by_enemy_clan = dict()
    for enemy_clan in battles_by_enemy:
        if battles_by_enemy[enemy_clan] < battle_count_cutoff:
            continue
        win_ratio_by_enemy_clan[enemy_clan] = float(wins_by_enemy[enemy_clan]) / battles_by_enemy[enemy_clan]

    from datetime import timedelta
    import calendar

    def weekrange(start, end):
        for n in range(int((end - start).days)):
            yield start + timedelta(days=n)

    battles_per_day = []
    for start_date in weekrange(datetime.datetime.now() - datetime.timedelta(days=30), datetime.datetime.now()):
        end_date = start_date + datetime.timedelta(days=1)
        day_battles = battles_query.filter(Battle.date >= start_date, Battle.date < end_date)
        battles_per_day.append((calendar.timegm(start_date.timetuple()) * 1000, day_battles.count()))

    players_joined = Player.query.filter_by(clan=clan).order_by('member_since desc').all()
    players_left = Player.query.filter_by(clan=clan, locked=True) \
        .filter(Player.lock_date.isnot(None)).order_by('lock_date desc').all()

    return render_template('clan_stats.html', battles=battles, total_battles=len(battles),
                           battles_one_week=battles_one_week, battles_one_week_won=battles_one_week_won,
                           map_battles=map_battles, battles_won=battles_won, players_joined=players_joined,
                           players_left=players_left, clan=clan,
                           battles_thirty_days=battles_thirty_days, battles_thirty_days_won=battles_thirty_days_won,
                           win_ratio_by_map=win_ratio_by_map, win_ratio_by_commander=win_ratio_by_commander,
                           wins_by_commander=wins_by_commander, battles_by_commander=battles_by_commander,
                           win_ratio_by_enemy_clan=win_ratio_by_enemy_clan, battles_by_enemy=battles_by_enemy,
                           wins_by_enemy=wins_by_enemy, battle_count_cutoff=battle_count_cutoff,
                           battles_per_day=battles_per_day)


@app.route('/statistics/<clan>/players', methods=['GET', 'POST'])
@require_login
@require_clan_membership
@require_role(config.PLAYER_PERFORMANCE_ROLES)
def player_performance(clan):
    """ Player statistics from replay files: damage done, spots, wn7, ... """
    from_date = request.form.get('fromDate', None)
    to_date = request.form.get('toDate', None)

    if from_date is None:
        from_date = datetime.datetime.now() - datetime.timedelta(days=4*7)
    else:
        from_date = datetime.datetime.strptime(from_date, '%d.%m.%Y')

    if to_date is None:
        to_date = datetime.datetime.now()
    else:
        to_date = datetime.datetime.strptime(to_date, '%d.%m.%Y') + datetime.timedelta(days=1)

    battles = Battle.query.options(joinedload('replay')).filter_by(clan=clan).filter(Battle.date>=from_date, Battle.date<=to_date).all()
    players = Player.query.filter_by(clan=clan, locked=False).all()

    result = analysis.player_performance(battles, players)

    return render_template('players/performance.html', clan_players=players, result=result, clan=clan,
                           from_date=from_date, to_date=to_date)


@app.route('/profile', methods=['GET', 'POST'])
@require_login
def profile():
    """ Player profile page """
    clan_battles_query = Battle.query.filter_by(clan=g.player.clan)
    played_battles = Battle.query.join(Battle.attendances).filter(Battle.attendances.any(player_id=g.player.id)) \
        .filter(BattleAttendance.reserve == False).distinct()

    performance = analysis.player_performance(played_battles, [g.player])

    def weekrange(start, end):
        for n in range(int((end - start).days)):
            yield start + timedelta(days=n)

    player_battles_per_day = []
    battles_per_day = []
    for start_date in weekrange(datetime.datetime.now() - datetime.timedelta(days=30), datetime.datetime.now()):
        end_date = start_date + datetime.timedelta(days=1)

        # All clan battles
        day_battles = clan_battles_query.filter(Battle.date >= start_date, Battle.date < end_date)
        battles_per_day.append((calendar.timegm(start_date.timetuple()) * 1000, day_battles.count()))

        # Player's battles
        day_battles_played = played_battles.filter(Battle.date >= start_date, Battle.date < end_date)
        player_battles_per_day.append((calendar.timegm(start_date.timetuple()) * 1000, day_battles_played.count()))

    if request.method == 'POST':
        g.player.email = request.form.get('email', '')
        db_session.add(g.player)
        db_session.commit()
    return render_template('players/profile.html', played_battles=played_battles, performance=performance,
                           battles_per_day=battles_per_day, player_battles_per_day=player_battles_per_day)


@app.route('/admin/export-emails/<clan>')
@require_login
@require_clan_membership
@require_role(config.ADMIN_ROLES)
def export_emails(clan):
    """ Return names and email addresses as CSV file """
    csv_response = StringIO()
    csv_writer = csv.writer(csv_response)
    csv_writer.writerow(["Name", "e-mail"])

    for player in Player.query.filter_by(locked=False, clan=clan).order_by('email'):
        csv_writer.writerow([player.name, player.email])

    headers = Headers()
    headers.add('Content-Type', 'text/csv')
    headers.add('Content-Disposition', 'attachment',
                filename=secure_filename(clan + "_emails.csv"))
    return Response(response=csv_response.getvalue(), headers=headers)


@app.route('/api/battle-checksums')
def battle_checksums():
    import hashlib

    hashes = list()
    for battle in Battle.query.all():
        replay = battle.replay.unpickle()
        if not replay:
            continue
        sha = hashlib.sha1()
        sha.update(''.join(sorted(replays.player_team(replay))))
        sha.update(replays.guess_enemy_clan(replay))
        sha.update(replay['first']['mapName'])
        hashes.append(sha.hexdigest())

    return jsonify({'hashes': hashes})
