"""
    The Web Application
    ~~~~~~~~~~~~~~~~~~~

    Implementation of all request handlers and core functionality.
"""

import datetime
import os
import pickle
import logging
import hashlib

from collections import defaultdict
from functools import wraps
from flask import Flask, g, session, render_template, flash, redirect, request, url_for, abort, make_response, jsonify
from flask.ext.openid import OpenID
from flask.ext.cache import Cache
from sqlalchemy import or_
from sqlalchemy.orm import joinedload, joinedload_all
from werkzeug.utils import secure_filename

from . import config, replays, wotapi, util, tasks
from .model import Player, Battle, BattleAttendance, Replay, BattleGroup, db_session

# Set up Flask application
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = config.DATABASE_URI
app.config['SQLALCHEMY_ECHO'] = False
app.config['SECRET_KEY'] = config.SECRET_KEY
app.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16 MB at a time should be plenty for replays
cache = Cache(app, config={'CACHE_TYPE': 'simple'})
oid = OpenID(app, config.OID_STORE_PATH)

app.jinja_env.filters['pretty_date'] = util.pretty_date

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

# CSRF protection
@app.before_request
def csrf_protect():
    if request.method == "POST":
        token = session.pop('_csrf_token', None)
        if not token or token != request.form.get('_csrf_token'):
            flash('Invalid CSRF token. Please try again or contact an administrator for help.')
            return redirect(url_for('index'))


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
    g.CREATE_BATTLE_ROLES = config.CREATE_BATTLE_ROLES
    g.ADMINS = config.ADMINS
    g.ADMIN_ROLES = config.ADMIN_ROLES
    g.PLAYER_PERFORMANCE_ROLES = config.PLAYER_PERFORMANCE_ROLES
    g.RESERVE_SIGNUP_ALLOWED = config.RESERVE_SIGNUP_ALLOWED


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

@app.route('/sync-players/<int:clan_id>')
def sync_players(clan_id):
    """
        Synchronize players in the database with Wargaming servers.
    :param clan_id:
    :return:
    """
    if config.API_KEY == request.args['API_KEY']:
        logger.info("Clan member synchronization triggered for " + str(clan_id))

        clan_info = wotapi.get_clan(str(clan_id))
        processed = set()
        for player_id in clan_info['data'][str(clan_id)]['members']:
            import time
            time.sleep(0.3)
            player = clan_info['data'][str(clan_id)]['members'][player_id]
            player_data = wotapi.get_player(str(player['account_id']))
            p = Player.query.filter_by(wot_id=str(player['account_id'])).first()
            if not player_data:
                if p: processed.add(p.id) # skip this guy later when locking players
                logger.info("WOTAPI Error: Could not retrieve player information of " + str(player['account_id']))
                continue # API Error?

            since = datetime.datetime.fromtimestamp(
                float(player_data['data'][str(player['account_id'])]['clan']['since']))

            if p:
                # Player exists, update information
                processed.add(p.id)
                p.locked = False
                p.clan = clan_info['data'][str(clan_id)]['abbreviation']
                p.role = player['role'] # role might have changed
                p.member_since = since # might have rejoined
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

        # All players of the clan in the DB, which are no longer in the clan
        for player in Player.query.filter_by(clan=clan_info['data'][str(clan_id)]['abbreviation']):
            if player.id in processed or player.id is None or player.locked: continue
            logger.info("Locking player " + player.name)
            player.locked = True
            player.lock_date = datetime.datetime.now()
            db_session.add(player)

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

        # Cache battle status for 60 seconds to avoid spamming WG's server
        @cache.memoize(timeout=60)
        def cached_scheduled_battles(clan_id):
            logger.info("Querying Wargaming server for battle schedule of clan " + str(clan_id) + " " + g.player.clan)
            return wotapi.get_scheduled_battles(clan_id)

        # Cache provinces owned for 60 seconds to avoid spamming WG's server
        @cache.memoize(timeout=60)
        def cached_provinces_owned(clan_id):
            logger.info("Querying Wargaming server for provinces owned by clan " + str(clan_id) + " " + g.player.clan)
            return wotapi.get_provinces(clan_id)

        provinces_owned = cached_provinces_owned(config.CLAN_IDS[g.player.clan])
        total_revenue = 0
        for p in provinces_owned['request_data']['items']:
            total_revenue += p['revenue']
        scheduled_battles = cached_scheduled_battles(config.CLAN_IDS[g.player.clan])
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
    return render_template('admin.html', API_KEY=config.API_KEY)


@app.route('/help')
def help():
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
        if not player_data or not player_data['data'] or not player_data['data']['clan']:
            flash(u'Error: Could not retrieve player information from Wargaming. Contact an admin for help :-)',
                  'error')
            return render_template('create_profile.html', next_url=oid.get_next_url())

        clan_ids_to_name = dict((v,k) for k, v in map.iteritems())
        clan_id = player_data['data'][str(wot_id)]['clan']['clan_id']
        clan = clan_ids_to_name[str(clan_id)]
        if clan_id not in config.CLAN_IDS.values():
            flash(u'You have to be in one of the clans to login', 'error')
            return render_template('create_profile.html', next_url=oid.get_next_url())

        role = player_data['data'][str(wot_id)]['clan']['role']
        member_since = datetime.datetime.fromtimestamp(
                float(player_data['data'][str(player['account_id'])]['clan']['since']))
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
    flash(u'You were signed out', 'info')
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
        file = request.files['replay']
        if file and file.filename.endswith('.wotreplay'):
            filename = secure_filename(g.player.name + '_' + file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            return redirect(url_for('create_battle', filename=filename))
    return render_template('battles/create_from_replay.html')


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
    if battle.clan != g.player.clan and g.player.name not in config.ADMINS: abort(403)

    all_players = Player.query.filter_by(clan=g.player.clan, locked=False).order_by('lower(name)').all()
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

        errors = False
        date = None
        try:
            date = datetime.datetime.strptime(request.form.get('date', ''), '%d.%m.%Y %H:%M:%S')
        except ValueError as e:
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

            if bg:
                battle.battle_group_final = battle_group_final
                battle.battle_group = bg
                db_session.add(bg)

            for ba in battle.attendances:
                if not ba.reserve:
                    db_session.delete(ba)

            for player_id in players:
                player = Player.query.get(player_id)
                if not player: abort(404)
                ba = BattleAttendance(player, battle, reserve=False)
                db_session.add(ba)

            db_session.add(battle)
            db_session.commit()
            logger.info(g.player.name + " updated the battle " + str(battle.id))
            return redirect(url_for('battles', clan=g.player.clan))

    return render_template('battles/edit.html', date=date, map_name=map_name, province=province, battle=battle,
                           battle_groups=battle_groups,
                           battle_commander=battle_commander, enemy_clan=enemy_clan, battle_result=battle_result,
                           battle_group_final=battle_group_final, players=players, description=description,
                           replay=replay, replays=replays, all_players=all_players)


@app.route('/battles/create', methods=['GET', 'POST'])
@require_login
@require_role(roles=config.CREATE_BATTLE_ROLES)
def create_battle():
    """
        Create battle form.
    :return:
    """
    all_players = Player.query.filter_by(clan=g.player.clan, locked=False).order_by('lower(name)').all()

    # Prefill form with data from replay
    enemy_clan = ''
    players = []
    replay = None
    description = ''
    battle_result = ''
    map_name = ''
    province = ''
    battle_commander = None
    date = datetime.datetime.now()
    battle_groups = BattleGroup.query.filter_by(clan=g.player.clan).order_by('date').all()
    battle_group = '-1'
    battle_group_title = ''
    battle_group_description = ''
    battle_group_final = False
    filename = request.args.get('filename', '')
    if request.method == 'POST':
        filename = request.form.get('filename', '')

    if filename:
        file_blob = open(os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename)), 'rb').read()
        replay = replays.parse_replay(file_blob)
        if not replay:
            flash(u'Error: Parsing replay file failed :-(.', 'error')
        else:
            clan = replays.guess_clan(replay)
            if clan not in config.CLAN_NAMES or clan != g.player.clan:
                flash(
                    u'Error: "Friendly" clan was not in the list of clans supported by this website or you are not a member',
                    'error')
            map_name = replay['first']['mapDisplayName']
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
                    u'Error: Uploaded replay file is probably not from a clan war (Detected different clan tags in one of the team' + \
                    u' or players from the same clan on both sides)', 'error')
            else:
                enemy_clan = replays.guess_enemy_clan(replay)
                if replays.player_won(replay):
                    battle_result = 'victory'

    if request.method == 'POST':
        players = map(int, request.form.getlist('players'))
        filename = request.form.get('filename', '')
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

        errors = False
        date = None
        try:
            date = datetime.datetime.strptime(request.form.get('date', ''), '%d.%m.%Y %H:%M:%S')
        except ValueError as e:
            flash(u'Invalid date format', 'error')
            errors = True

        # Validation
        if filename:
            file_blob = open(os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename)), 'rb').read()
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
                            battle_commander=battle_commander, description=description)

            if bg:
                battle.battle_group_final = battle_group_final
                battle.battle_group = bg
                db_session.add(bg)

            if config.STORE_REPLAYS_IN_DB:
                battle.replay = Replay(file_blob, pickle.dumps(replay))
            else:
                battle.replay = Replay(None, pickle.dumps(replay))

            for player_id in players:
                player = Player.query.get(player_id)
                if not player: abort(404)
                ba = BattleAttendance(player, battle, reserve=False)
                db_session.add(ba)

            db_session.add(battle)
            db_session.commit()
            logger.info(g.player.name + " added the battle " + str(battle.id))
            return redirect(url_for('battles', clan=g.player.clan))

    return render_template('battles/create.html', CLAN_NAMES=config.CLAN_NAMES, all_players=all_players,
                           players=players,
                           enemy_clan=enemy_clan, filename=filename, replay=replay, battle_commander=battle_commander,
                           map_name=map_name, province=province, description=description, replays=replays,
                           battle_result=battle_result, date=date, battle_groups=battle_groups,
                           battle_group=battle_group, battle_group_title=battle_group_title,
                           battle_group_description=battle_group_description, battle_group_final=battle_group_final)


@app.route('/battles/list/<clan>')
@require_login
def battles(clan):
    """
        Table of all battles of a clan.
    :param clan:
    :return:
    """
    if not clan in config.CLAN_NAMES:
        abort(404)
    battles = Battle.query.options(joinedload_all('battle_group.battles')).options(
        joinedload_all('attendances.player')).filter_by(clan=clan).all()
    return render_template('battles/battles.html', clan=clan, battles=battles)


@app.route('/battles/group/<int:group_id>')
@require_login
def battle_group(group_id):
    """
        Battle group details page with table of the individual battles.
    :param group_id:
    :return:
    """
    battle_group = BattleGroup.query.options(joinedload_all('battles.attendances.player')).get(group_id) or abort(404)

    return render_template('battles/battle_group.html', battle_group=battle_group, battles=battle_group.battles,
                           clan=battle_group.clan)


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
    if battle.clan != g.player.clan and g.player.name not in config.ADMINS: abort(403)
    for ba in battle.attendances:
        db_session.delete(ba)
    if battle.battle_group and len(battle.battle_group.battles) == 1:
        # last battle in battle group, delete the group as well
        db_session.delete(battle.battle_group)
    db_session.delete(battle)
    logger.info(g.player.name + " deleted the battle " + str(battle.id) + " " + str(battle))
    db_session.commit()

    return redirect(url_for('battles', clan=g.player.clan))


@app.route('/players/<clan>')
@require_login
def players(clan):
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
            if battle.date < player.member_since: continue
            if battle.battle_group_id and not battle.battle_group_final: continue # only finals will count
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
            if battle.date < player.member_since: continue
            if battle.battle_group_id and not battle.battle_group_final: continue # only finals will count
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
def player(player_id):
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
        if battle.date < player.member_since: continue
        if battle.battle_group_id and not battle.battle_group_final: continue # only finals will count
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
    if battle.clan != g.player.clan and g.player.name not in config.ADMINS: abort(403)
    if not config.RESERVE_SIGNUP_ALLOWED: abort(403)
    back_to_battle = request.args.has_key('back_to_battle')
    # disallow signing as reserve for old battles
    if battle.date < datetime.datetime.now() - config.RESERVE_SIGNUP_DURATION:
        flash(u"Can't sign up as reserve for battles older than 24 hours. Contact an admin if needed.")
        if back_to_battle:
            return redirect(url_for('battle_details', battle_id=battle.id))
        return redirect(url_for('battles', clan=g.player.clan))

    if not battle.has_player(g.player) and not battle.has_reserve(g.player):
        ba = BattleAttendance(g.player, battle, reserve=True)
        db_session.add(ba)
        logger.info(g.player.name + " signed himself as reserve for " + str(battle))
        db_session.commit()

    if back_to_battle:
        return redirect(url_for('battle_details', battle_id=battle.id))

    return redirect(url_for('battles', clan=g.player.clan))


@app.route('/battles/<int:battle_id>/unsign-reserve')
@require_login
def unsign_as_reserve(battle_id):
    """
        Remove currently logged in player as reserve from a battle.
    :param battle_id:
    :return:
    """
    battle = Battle.query.get(battle_id) or abort(404)
    if battle.clan != g.player.clan and g.player.name not in config.ADMINS: abort(403)
    if not config.RESERVE_SIGNUP_ALLOWED: abort(403)
    back_to_battle = request.args.has_key('back_to_battle')
    if battle.date < datetime.datetime.now() - config.RESERVE_SIGNUP_DURATION:
        flash(u"Can't sign up as reserve for battles older than 24 hours. Contact an admin if needed.")
        if back_to_battle:
            return redirect(url_for('battle_details', battle_id=battle.id))
        return redirect(url_for('battles', clan=g.player.clan))

    ba = BattleAttendance.query.filter_by(player=g.player, battle=battle, reserve=True).first() or abort(500)
    db_session.delete(ba)
    logger.info(g.player.name + " removed himself as reserve for " + str(battle))
    db_session.commit()

    if back_to_battle:
        return redirect(url_for('battle_details', battle_id=battle.id))

    return redirect(url_for('battles', clan=g.player.clan))


@app.route('/battles/<int:battle_id>/download-replay/')
@require_login
def download_replay(battle_id):
    """
        Replay download handler. Returns the requested replay blob as binary download.
    :param battle_id:
    :return:
    """
    battle = Battle.query.get(battle_id) or abort(404)
    if not battle.replay_id: abort(404)
    response = make_response(battle.replay.replay_blob)
    response.headers['Content-Type'] = 'application/octet-stream'
    response.headers['Content-Disposition'] = 'attachment; filename=' + \
                                              secure_filename(battle.date.strftime(
                                                  '%d.%m.%Y_%H_%M_%S') + '_' + battle.clan + '_' + battle.enemy_clan + '.wotreplay')
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
        fromDate = request.form['fromDate']
        toDate = request.form['toDate']
        gold = int(request.form['gold'])
        victories_only = request.form.get('victories_only', False)
    else:
        fromDate = request.args.get('fromDate')
        toDate = request.args.get('toDate')
        gold = int(request.args.get('gold'))
        victories_only = request.args.get('victories_only', False) == 'on'

    fromDate = datetime.datetime.strptime(fromDate, '%d.%m.%Y')
    toDate = datetime.datetime.strptime(toDate, '%d.%m.%Y') + datetime.timedelta(days=1)
    battles = Battle.query.options(joinedload('attendances')).filter_by(clan=clan).filter(
        Battle.date >= fromDate, Battle.date <= toDate,
        or_(Battle.battle_group_id == None, Battle.battle_group_final == True))
    if victories_only:
        battles = battles.filter_by(victory=True)
    battles = battles.all()

    clan_players = Player.query.filter_by(clan=clan, locked=False).all()
    player_fced_win = defaultdict(int)
    player_fced_defeat = defaultdict(int)
    player_fced_draws = defaultdict(int)
    player_played = defaultdict(int)
    player_reserve = defaultdict(int)
    player_gold = defaultdict(int)
    player_victories = defaultdict(int)
    player_defeats = defaultdict(int)
    player_draws = defaultdict(int)
    for battle in battles:
        if battle.battle_group and not battle.battle_group_final: continue # only finals count

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
            if p.locked or p == battle_commander: continue
            player_played[p] += 1
            if battle.victory:
                player_victories[p] += 1
            elif battle.draw:
                player_draws[p] += 1
            else:
                player_defeats[p] += 1

        for p in battle_reserves:
            if p.locked: continue
            player_reserve[p] += 1

    players = set()
    for p in clan_players:
        if player_played[p] or player_reserve[p] or player_fced_win[p] or player_fced_defeat[p]:
            players.add(p)

    player_points = dict()
    for p in players:
        player_points[p] = player_fced_win[p] * 6 + player_fced_defeat[p] * 4 + player_fced_draws[p] * 2 + \
                           player_victories[p] * 3 + player_defeats[p] * 2 + player_draws[p] * 2 + player_reserve[p] * 1
    total_points = sum(player_points[p] for p in players)
    player_gold = dict()
    for p in players:
        player_gold[p] = int(round(player_points[p] / float(total_points) * gold))

    return render_template('payout/payout_battles.html', battles=battles, clan=clan, fromDate=fromDate, toDate=toDate,
                           player_played=player_played, player_reserve=player_reserve, players=players,
                           player_gold=player_gold, gold=gold, player_defeats=player_defeats,
                           player_fced_win=player_fced_win,
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
    players = Player.query.filter_by(clan=clan, locked=False).filter(Player.id.notin_(battle_player_ids)).order_by('name asc')
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
    logger.info(g.player.name + " updated the reserves for " + str(battle) + " - added: " + \
                ", ".join([p.name for p in (reserve_now - reserve_before)]) + " - deleted: " + \
                ", ".join([p.name for p in (reserve_before - reserve_now)])
    )
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
    if g.player.clan != clan and not g.player.name in config.ADMINS: abort(403)
    fromDate = request.args.get('fromDate', None)
    toDate = request.args.get('toDate', None)

    if not clan or not fromDate or not toDate:
        return jsonify({
            "sEcho": 1,
            "iTotalRecords": 0,
            "iTotalDisplayRecords": 0,
            "aaData": []
        })

    fromDate = datetime.datetime.strptime(fromDate, '%d.%m.%Y')
    toDate = datetime.datetime.strptime(toDate, '%d.%m.%Y') + datetime.timedelta(days=1)
    victories_only = request.args.get('victories_only', False) == 'on'
    battles = Battle.query.filter_by(clan=clan).filter(Battle.date >= fromDate, Battle.date <= toDate,
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
             battle.outcome_str(),
            ] for battle in battles
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

    battles_one_week_query = battles_query.filter(Battle.date>=datetime.datetime.now()-datetime.timedelta(days=7))
    battles_one_week = battles_one_week_query.all()
    battles_one_week_won = battles_one_week_query.filter_by(victory=True).count()

    battles_thirty_days_query = battles_query.filter(Battle.date>=datetime.datetime.now()-datetime.timedelta(days=30))
    battles_thirty_days = battles_thirty_days_query.all()
    battles_thirty_days_won = battles_thirty_days_query.filter_by(victory=True).count()

    # Battles played by map
    battles_by_map = dict()
    for battle in battles:
        if battle.map_name not in battles_by_map:
            battles_by_map[battle.map_name] = 0
        battles_by_map[battle.map_name] += 1
    map_battles = list(battles_by_map.iteritems())

    players_joined = Player.query.filter_by(clan=clan, locked=False).order_by('member_since desc').all()
    players_left = Player.query.filter_by(clan=clan, locked=True)\
        .filter(Player.lock_date.isnot(None)).order_by('lock_date desc').all()

    return render_template('clan_stats.html', battles=battles, total_battles=len(battles),
                           battles_one_week=battles_one_week, battles_one_week_won=battles_one_week_won,
                           map_battles=map_battles, battles_won=battles_won, players_joined=players_joined, players_left=players_left,
                           battles_thirty_days=battles_thirty_days, battles_thirty_days_won=battles_thirty_days_won)


@app.route('/statistics/<clan>/players')
@require_login
@require_clan_membership
@require_role(config.PLAYER_PERFORMANCE_ROLES)
def player_performance(clan):
    battles = Battle.query.options(joinedload('replay')).filter_by(clan=clan).all()
    clan_players = Player.query.filter_by(clan=clan, locked=False).all()

    battle_count = defaultdict(int)
    dmg = defaultdict(float)
    kills = defaultdict(int)
    survived = defaultdict(int)
    spotted = defaultdict(int)
    spot_damage = defaultdict(float)
    potential_damage = defaultdict(float)
    wins = defaultdict(int)
    decap = defaultdict(int)
    for battle in battles:
        replay_data = battle.replay.unpickle()
        if not replay_data or not 'pickle' in replay_data: continue
        players_perf = replays.player_performance(replay_data['pickle'])
        for player in battle.get_players():
            if not str(player.wot_id) in players_perf: continue # Replay/Players mismatch (account sharing?)
            perf = players_perf[str(player.wot_id)]
            battle_count[player] += 1
            dmg[player] += perf['damageDealt']
            spot_damage[player] += perf['damageAssistedRadio']
            kills[player] += perf['kills']
            survived[player] += 1 if perf['survived'] else 0
            potential_damage[player] += perf['potentialDamageReceived']
            wins[player] += 1 if battle.victory else 0
            spotted[player] += perf['spotted']
            decap[player] += perf['droppedCapturePoints']

    avg_dmg = defaultdict(float)
    avg_kills = defaultdict(float)
    survival_rate = defaultdict(float)
    avg_spotted = defaultdict(float)
    avg_spot_damage = defaultdict(float)
    avg_pot_damage = defaultdict(float)
    win_rate = defaultdict(float)
    avg_decap = defaultdict(float)
    for p in clan_players:
        if battle_count[p] > 0:
            bc = float(battle_count[p])
            avg_dmg[p] = dmg[p] / bc
            avg_kills[p] = kills[p] / bc
            survival_rate[p] = survived[p] / bc
            avg_spotted[p] = spotted[p] / bc
            avg_spot_damage[p] = spot_damage[p] / bc
            avg_pot_damage[p] = potential_damage[p] / bc
            win_rate[p] = wins[p] / bc
            avg_decap[p] = decap[p] / bc

    import math
    min = lambda a, b: a if a <= b else b

    wn7 = defaultdict(float)
    for p in clan_players:
        if battle_count[p] == 0: continue
        tier = 10.0
        wn7[p] = (1240.0 - 1040.0 / ((min(6, tier)) ** 0.164)) * avg_kills[p] \
                 + avg_dmg[p] * 530.0 / (184.0 * math.exp(0.24 * tier) + 130.0) \
                 + avg_spotted[p] * 125.0 * min(tier, 3) / 3.0 \
                 + min(avg_decap[p], 2.2) * 100.0 \
                 + ((185 / (0.17 + math.exp((win_rate[p] * 100.0 - 35.0) * -0.134))) - 500.0) * 0.45 \
                 - ((5.0 - min(tier, 5)) * 125.0) / (
                        1.0 + math.exp(( tier - (battle_count[p] / 220.0) ** (3.0 / tier) ) * 1.5))


    return render_template('players/performance.html', clan_players=clan_players, battle_count=battle_count,
                           avg_dmg=avg_dmg, avg_kills=avg_kills, avg_spotted=avg_spotted, survival_rate=survival_rate,
                           avg_spot_damage=avg_spot_damage, clan=clan, avg_pot_damage=avg_pot_damage, win_rate=win_rate,
                           wn7=wn7, avg_decap=avg_decap)
