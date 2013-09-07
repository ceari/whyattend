"""
    Web application based on Flask.
"""

import datetime
import os
import json
import pickle

from functools import wraps
from flask import Flask, g, session, render_template, flash, redirect, request, url_for, abort, make_response, jsonify
from flask.ext.openid import OpenID
from sqlalchemy import or_
from sqlalchemy.orm import joinedload, joinedload_all
from werkzeug.utils import secure_filename

import config
import replays
import wotapi
import filters
from .util import ReverseProxied
from .model import db, Player, Battle, BattleAttendance, Replay, BattleGroup

# Set up Flask application
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = config.DATABASE_URI
app.config['SQLALCHEMY_ECHO'] = False
app.config['SECRET_KEY'] = config.SECRET_KEY
app.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16 MB at a time should be plenty for replays
db.init_app(app)
oid = OpenID(app, config.OID_STORE_PATH)

app.jinja_env.filters['age'] = filters.age

# Set up middleware in case we are behind a reverse proxy server
app.wsgi_app = ReverseProxied(app.wsgi_app)

# decorates a decorator function to be able to specify parameters :-)
decorator_with_args = lambda decorator: lambda *args, **kwargs: \
    lambda func: decorator(func, *args, **kwargs)

@app.before_request
def lookup_current_user():
    g.player = None
    if app.config['DEBUG'] and request.url.endswith('createdb'): return
    if 'openid' in session:
        # Checking if player exists for every request might be overkill
        g.player = Player.query.filter_by(openid=session.get('openid')).first()
        if g.player and g.player.locked:
            g.player = None
            session.pop('openid', None)


@app.before_request
def inject_constants():
    g.clans = config.CLAN_NAMES
    g.roles = config.ROLE_LABELS
    g.PAYOUT_ROLES = config.PAYOUT_ROLES
    g.WOT_SERVER_REGION_CODE = config.WOT_SERVER_REGION_CODE
    g.DELETE_BATTLE_ROLES = config.DELETE_BATTLE_ROLES
    g.CREATE_BATTLE_ROLES = config.CREATE_BATTLE_ROLES


def require_login(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.player is None or g.player.locked:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def require_clan_membership(f):
    @wraps(f)
    def decorated_f(*args, **kwargs):
        if g.player is None:
            return redirect(url_for('login', next=request.url))
        # Has to be a request handler with 'clan' argument
        if not 'clan' in kwargs:
            abort(500)
        if g.player.clan != kwargs['clan'] and not g.player.name == 'fantastico':
            abort(403)
        return f(*args, **kwargs)
    return decorated_f


@decorator_with_args
def require_role(f, roles):
    @wraps(f)
    def decorated_f(*args, **kwargs):
        if g.player is None:
            return redirect(url_for('login', next=request.url))
        if g.player.role not in roles and g.player.name != 'fantastico':
            abort(403)

        return f(*args, **kwargs)
    return decorated_f

############## API request handlers

@app.route('/createdb')
def create_db():
    if app.config['DEBUG']:
        db.create_all()
    return redirect(url_for('index'))


@app.route('/sync-players/<int:clan_id>')
def sync_players(clan_id):
    """
    Synchronize players in database with Wargaming clan data
    :param clan_id:
    :return:
    """
    if config.API_KEY == request.args['API_KEY']:
        import time
        time.sleep(0.1) # Rate limiting
        clan_info = wotapi.get_clan(str(clan_id))
        processed = set()
        for player in clan_info['data']['members']:
            print "Checking player ", player['account_name']
            player_data = wotapi.get_player(str(player['account_id']))
            if not player_data: continue # API Error?
            p = Player.query.filter_by(wot_id=str(player['account_id'])).first()
            if p:
                # Player exists, update information
                print "Player " + p.name + " exists. Updating information"
                processed.add(p.id)
                p.locked = False
                p.clan = clan_info['data']['abbreviation']
                p.role = player['role'] # role might have changed
                p.member_since = wotapi.get_member_since_date(player_data) # might have rejoined
            else:
                # New player
                p = Player(str(player['account_id']),
                           'https://eu.wargaming.net/id/' + str(player['account_id']) + '-' + player['account_name'] + '/',
                           wotapi.get_member_since_date(player_data), player['account_name'], clan_info['data']['abbreviation'],
                           player['role'])
                print "Adding new player " + p.name
            db.session.add(p)

        # All players of the clan in the DB, which are no longer in the clan
        for player in Player.query.filter_by(clan=clan_info['data']['abbreviation']):
            if player.id in processed: continue
            player.locked = True
            print "Locking " + player.name + " because he is no longer in the clan."
            db.session.add(player)

        db.session.commit()

    else:
        abort(403)

    return redirect(url_for('index'))

############## Request handlers Public request handlers

@app.route("/")
def index():
    if g.player:
        latest_battles = Battle.query.filter_by(clan=g.player.clan).order_by('date desc').limit(3)
    else:
        latest_battles = None

    return render_template('index.html', clans=config.CLAN_NAMES, latest_battles=latest_battles)


@app.route('/help')
def help():
    return render_template('help.html')


@app.route('/attributions')
def attributions():
    return render_template('attributions.html')


@app.route('/login', methods=['GET', 'POST'])
@oid.loginhandler
def login():
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
    """This is called when login with OpenID succeeded and it's not
        necessary to figure out if this is the users's first login or not.
        This function has to redirect otherwise the user will be presented
        with a terrible URL which we certainly don't want.
    """
    session['openid'] = resp.identity_url
    session['nickname'] = resp.nickname
    player = Player.query.filter_by(openid=resp.identity_url, locked=False).first()
    if player is not None:
        flash(u'Successfully signed in', 'success')
        g.player = player
        return redirect(oid.get_next_url())
    return redirect(url_for('create_profile', next=oid.get_next_url(),
                            name=resp.nickname))


@app.route('/create-profile', methods=['GET', 'POST'])
def create_profile():
    """If this is the user's first login, the create_or_login function
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

        clan = wotapi.get_clantag(player_data)
        role = wotapi.get_player_clan_role(player_data)
        member_since = wotapi.get_member_since_date(player_data)
        if not role:
            flash(u'Error: Could not retrieve player role from wargaming server', 'error')
            return render_template('create_profile.html', next_url=oid.get_next_url())

        db.session.add(Player(wot_id, session['openid'], member_since, session['nickname'], clan, role))
        db.session.commit()
        flash(u'Welcome!', 'success')
        return redirect(oid.get_next_url())
    return render_template('create_profile.html', next_url=oid.get_next_url())


@app.route('/logout')
@require_login
def logout():
    session.pop('openid', None)
    session.pop('nickname', None)
    g.player = None
    flash(u'You were signed out', 'info')
    return redirect(oid.get_next_url())


@app.route('/battles/create/from-replay', methods=['GET', 'POST'])
@require_login
@require_role(roles=config.CREATE_BATTLE_ROLES)
def create_battle_from_replay():
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
    battle = Battle.query.get(battle_id) or abort(404)
    if battle.clan != g.player.clan and g.player.name != 'fantastico': abort(403)

    all_players = Player.query.filter_by(clan=g.player.clan, locked=False).order_by('lower(name)').all()
    date = battle.date
    map_name = battle.map_name
    province = battle.map_province
    battle_commander = battle.battle_commander
    enemy_clan = battle.enemy_clan
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
            if bg.get_final_battle() is not battle and battle_group_final :
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
                db.session.add(bg)

            for ba in battle.attendances:
                if not ba.reserve:
                    db.session.delete(ba)

            for player_id in players:
                player = Player.query.get(player_id)
                if not player: abort(404)
                ba = BattleAttendance(player, battle, reserve=False)
                db.session.add(ba)

            db.session.add(battle)
            db.session.commit()
            return redirect(url_for('battles', clan=g.player.clan))

    return render_template('battles/edit.html', date=date, map_name=map_name, province=province, battle=battle,
                           battle_commander=battle_commander, enemy_clan=enemy_clan, battle_result=battle_result,
                           battle_group_final=battle_group_final, players=players, description=description,
                           replay=replay, replays=replays, all_players=all_players)


@app.route('/battles/create', methods=['GET', 'POST'])
@require_login
@require_role(roles=config.CREATE_BATTLE_ROLES)
def create_battle():
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
                flash(u'Error: "Friendly" clan was not in the list of clans supported by this website or you are not a member', 'error')
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
                flash(u'Error: Uploaded replay file is probably not from a clan war (Detected different clan tags in one of the team' + \
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
                db.session.add(bg)

            if config.STORE_REPLAYS_IN_DB:
                battle.replay = Replay(file_blob, pickle.dumps(replay))
            else:
                battle.replay = Replay(None, pickle.dumps(replay))

            for player_id in players:
                player = Player.query.get(player_id)
                if not player: abort(404)
                ba = BattleAttendance(player, battle, reserve=False)
                db.session.add(ba)

            db.session.add(battle)
            db.session.commit()
            return redirect(url_for('battles', clan=g.player.clan))

    return render_template('battles/create.html', CLAN_NAMES=config.CLAN_NAMES, all_players=all_players, players=players,
                           enemy_clan=enemy_clan, filename=filename, replay=replay, battle_commander=battle_commander,
                           map_name=map_name, province=province, description=description, replays=replays,
                           battle_result=battle_result, date=date, battle_groups=battle_groups,
                           battle_group=battle_group, battle_group_title=battle_group_title,
                           battle_group_description=battle_group_description, battle_group_final=battle_group_final)


@app.route('/battles/list/<clan>')
@require_login
def battles(clan):
    if not clan in config.CLAN_NAMES:
        abort(404)
    battles = Battle.query.options(joinedload_all('battle_group.battles')).options(joinedload_all('attendances.player')).filter_by(clan=clan).all()
    return render_template('battles/battles.html', clan=clan, battles=battles)


@app.route('/battles/group/<int:group_id>')
@require_login
def battle_group(group_id):
    battle_group = BattleGroup.query.options(joinedload_all('battles.attendances.player')).get(group_id) or abort(404)

    return render_template('battles/battle_group.html', battle_group=battle_group, battles=battle_group.battles,
                           clan=battle_group.clan)


@app.route('/battles/<int:battle_id>')
@require_login
def battle_details(battle_id):
    battle = Battle.query.get(battle_id) or abort(404)
    return render_template('battles/battle.html', battle=battle, replays=replays)


@app.route('/battles/<int:battle_id>/delete')
@require_login
@require_role(config.DELETE_BATTLE_ROLES)
def delete_battle(battle_id):
    battle = Battle.query.get(battle_id) or abort(404)
    if battle.clan != g.player.clan and g.player.name != 'fantastico': abort(403)
    for ba in battle.attendances:
        db.session.delete(ba)
    if battle.battle_group and len(battle.battle_group.battles) == 1:
        # last battle in battle group, delete the group as well
        db.session.delete(battle.battle_group)
    db.session.delete(battle)
    db.session.commit()
    return redirect(url_for('battles', clan=g.player.clan))


@app.route('/players/<clan>')
@require_login
def players(clan):
    if not clan in config.CLAN_NAMES:
        abort(404)
    players = Player.query.options(joinedload_all('battles.battle')).filter_by(clan=clan, locked=False).all()
    possible = dict((p, 0) for p in players)
    reserve = dict((p, 0) for p in players)
    played = dict((p, 0) for p in players)
    present = dict((p, 0) for p in players)
    clan_battles = Battle.query.options(joinedload_all('attendances.player')).filter_by(clan=clan).order_by('date asc').all()
    for player in players:
        for battle in clan_battles:
            if battle.date < player.member_since: continue
            if battle.battle_group and not battle.battle_group_final: continue # only finals will count
            possible[player] += 1

            if battle.battle_group:
                if player in battle.battle_group.get_players():
                    played[player] += 1
                    present[player] += 1
                elif player in battle.battle_group.get_reserves():
                    reserve[player] += 1
                    present[player] += 1
            else:
                if battle.has_player(player):
                    played[player] += 1
                    present[player] += 1
                elif battle.has_reserve(player):
                    reserve[player] += 1
                    present[player] += 1

    return render_template('players/players.html', clan=clan, players=players,
                           played=played, present=present, possible=possible, reserve=reserve)


@app.route('/players/<int:player_id>')
def player(player_id):
    player = Player.query.get(player_id) or abort(404)

    return render_template('players/player.html', player=player)


@app.route('/battles/<int:battle_id>/sign-reserve')
@require_login
def sign_as_reserve(battle_id):
    battle = Battle.query.get(battle_id) or abort(404)
    if battle.clan != g.player.clan and g.player.name != 'fantastico': abort(403)
    # disallow signing as reserve for old battles
    if battle.date < datetime.datetime.now() - config.RESERVE_SIGNUP_DURATION:
        flash(u"Can't sign up as reserve for battles older than 24 hours. Contact an admin if needed.")
        return redirect(url_for('battles', clan=g.player.clan))

    if not battle.has_player(g.player) and not battle.has_reserve(g.player):
        ba = BattleAttendance(g.player, battle, reserve=True)
        db.session.add(ba)
        db.session.commit()
    return redirect(url_for('battles', clan=g.player.clan))


@app.route('/battles/<int:battle_id>/unsign-reserve')
@require_login
def unsign_as_reserve(battle_id):
    battle = Battle.query.get(battle_id) or abort(404)
    if battle.clan != g.player.clan and g.player.name != 'fantastico': abort(403)
    if battle.date < datetime.datetime.now() - config.RESERVE_SIGNUP_DURATION:
        flash(u"Can't sign up as reserve for battles older than 24 hours. Contact an admin if needed.")
        return redirect(url_for('battles', clan=g.player.clan))

    ba = BattleAttendance.query.filter_by(player=g.player, battle=battle, reserve=True).first() or abort(500)
    db.session.delete(ba)
    db.session.commit()
    return redirect(url_for('battles', clan=g.player.clan))


@app.route('/battles/<int:battle_id>/download-replay/')
@require_login
def download_replay(battle_id):
    battle = Battle.query.get(battle_id) or abort(404)
    if not battle.replay_id: abort(404)
    response = make_response(battle.replay.replay_blob)
    response.headers['Content-Type'] = 'application/octet-stream'
    response.headers['Content-Disposition'] = 'attachment; filename=' + \
            secure_filename(battle.date.strftime('%d.%m.%Y_%H_%M_%S') + '_' + battle.clan + '_' + battle.enemy_clan + '.wotreplay')
    return response


@app.route('/payout/<clan>')
@require_login
@require_role(config.PAYOUT_ROLES)
@require_clan_membership
def payout(clan):
    return render_template('payout.html', clan=clan)


@app.route('/payout/<clan>/battles', methods=['GET', 'POST'])
@require_login
@require_role(config.PAYOUT_ROLES)
@require_clan_membership
def payout_battles(clan):
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
        Battle.date >= fromDate, Battle.date <= toDate, or_(Battle.battle_group_id==None, Battle.battle_group_final==True))
    if victories_only:
        battles = battles.filter_by(victory=True)
    battles = battles.all()

    clan_players = Player.query.filter_by(clan=clan, locked=False).all()
    player_fced_win = dict((p, 0) for p in clan_players)
    player_fced_defeat = dict((p, 0) for p in clan_players)
    player_fced_draws = dict((p, 0) for p in clan_players)
    player_played = dict((p, 0) for p in clan_players)
    player_reserve = dict((p, 0) for p in clan_players)
    player_gold = dict((p, 0) for p in clan_players)
    player_victories = dict((p, 0) for p in clan_players)
    player_defeats = dict((p, 0) for p in clan_players)
    player_draws = dict((p, 0) for p in clan_players)
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

    return render_template('payout_battles.html', battles=battles, clan=clan, fromDate=fromDate, toDate=toDate,
                           player_played=player_played, player_reserve=player_reserve, players=players,
                           player_gold=player_gold, gold=gold, player_defeats=player_defeats, player_fced_win=player_fced_win,
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


@app.route('/payout/battles')
@require_login
@require_role(config.PAYOUT_ROLES)
def payout_battles_json():
    clan = request.args.get('clan', None)
    if g.player.clan != clan and not g.player.name == 'fantastico': abort(403)
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
                                                       or_(Battle.battle_group_id==None, Battle.battle_group_final==True))
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

