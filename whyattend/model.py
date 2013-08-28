"""
    Database mapping
"""

from flask.ext.sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Player(db.Model):
    __tablename__ = 'player'
    id = db.Column(db.Integer, primary_key=True)
    openid = db.Column(db.String(100), unique=True)
    wot_id = db.Column(db.String(100), unique=True)

    member_since = db.Column(db.DateTime)

    name = db.Column(db.String(100), unique=True)
    clan = db.Column(db.String(10))
    role = db.Column(db.String(50))  # one of {leader, vice_leader, commander, recruiter, private (=soldier), recruit}
    locked = db.Column(db.Boolean)

    gold_earned = db.Column(db.Integer)

    def __init__(self, wot_id, openid, member_since, name, clan, role, locked=False):
        self.wot_id = wot_id
        self.openid = openid
        self.member_since = member_since
        self.name = name
        self.clan = clan
        self.role = role
        self.gold_earned = 0
        self.locked = locked

    def battles_played(self):
        return BattleAttendance.query.filter_by(player=self, reserve=False)

    def battles_reserve(self):
        return BattleAttendance.query.filter_by(player=self, reserve=True)

    def battles_played_participation_ratio(self):
        played_battles = BattleAttendance.query.filter_by(player=self, reserve=False).count()
        possible_battles = Battle.query.filter(Battle.date >= self.member_since, Battle.clan == self.clan).count()
        return played_battles / float(possible_battles) if possible_battles > 0 else 0

    def participation_ratio(self):
        attended_battles = BattleAttendance.query.filter_by(player=self).count()
        possible_battles = Battle.query.filter(Battle.date >= self.member_since, Battle.clan == self.clan).count()
        return attended_battles / float(possible_battles) if possible_battles > 0 else 0

    def __repr__(self):
        return "<Player %r, %r, %r, %r>" % (self.wot_id, self.name, self.clan, self.role)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "clan": self.clan,
            "role": self.role,
            "gold_earned": self.gold_earned
        }


class BattleAttendance(db.Model):
    __tablename__ = 'player_battle'
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'), primary_key=True)
    battle_id = db.Column(db.Integer, db.ForeignKey('battle.id'), primary_key=True)
    player = db.relationship("Player", backref="battles")
    battle = db.relationship("Battle", backref="attendances")
    reserve = db.Column(db.Boolean)

    def __init__(self, player, battle, reserve=False):
        self.player = player
        self.battle = battle
        self.reserve = reserve


class Battle(db.Model):
    __tablename__ = 'battle'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime)
    clan = db.Column(db.String(10))
    enemy_clan = db.Column(db.String(10))
    victory = db.Column(db.Boolean)
    draw = db.Column(db.Boolean)
    paid = db.Column(db.Boolean)
    description = db.Column(db.Text)

    # WoT map name
    map_name = db.Column(db.String(80))
    # Which province the battle was for (or provinces, if encounter)
    map_province = db.Column(db.String(80))

    battle_commander_id = db.Column(db.Integer, db.ForeignKey('player.id'))
    battle_commander = db.relationship("Player", backref="battles_commanded", foreign_keys=[battle_commander_id])

    creator_id = db.Column(db.Integer, db.ForeignKey('player.id', ondelete='set null'), nullable=True)
    creator = db.relationship("Player", backref="battles_created", foreign_keys=[creator_id])

    replay_id = db.Column(db.Integer, db.ForeignKey('replay.id'))
    replay = db.relationship("Replay", backref="battle", uselist=False)

    battle_group_id = db.Column(db.Integer, db.ForeignKey('battlegroup.id'))
    battle_group = db.relationship("BattleGroup", backref="battles")
    # Is this the "final battle" of the group? Exactly one per group should be true
    battle_group_final = db.Column(db.Boolean)

    def __init__(self, date, clan, enemy_clan, victory, draw, creator, battle_commander, map_name, map_province,
                 description='', replay=None, paid=False):
        self.date = date
        self.clan = clan
        self.enemy_clan = enemy_clan
        self.victory = victory
        self.draw = draw
        self.creator = creator
        self.description = description
        self.battle_commander = battle_commander
        self.map_name = map_name
        self.map_province = map_province
        self.paid = paid
        if victory and draw:
            raise Exception('Battle can not be a victory and draw at the same time')

    def outcome_str(self):
        if self.victory:
            return 'Victory'
        elif self.draw:
            return 'Draw'
        else:
            return 'Defeat'

    def has_player(self, player):
        for ba in self.attendances:
            if ba.player == player and not ba.reserve:
                return True
        return False

    def has_reserve(self, player):
        for ba in self.attendances:
            if ba.player == player and ba.reserve:
                return True
        return False

    def get_players(self):
        return [ba.player for ba in BattleAttendance.query.filter_by(battle=self, reserve=False)]

    def get_reserve_players(self):
        return [ba.player for ba in BattleAttendance.query.filter_by(battle=self, reserve=True)]


class BattleGroup(db.Model):
    """
        Representation of grouped battles, e.g. landings which span across multiple battles.
    """
    __tablename__ = 'battlegroup'
    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(100))
    description = db.Column(db.Text)
    clan = db.Column(db.String(10))
    date = db.Column(db.DateTime)

    def __init__(self, title, description, clan, date):
        self.title = title
        self.description = description
        self.clan = clan
        self.date = date

    def get_final_battle(self):
        for battle in self.battles:
            if battle.battle_group_final:
                return battle
        return None


class Replay(db.Model):
    __tablename__ = 'replay'
    id = db.Column(db.Integer, primary_key=True)
    replay_pickle = db.Column(db.Binary)
    replay_blob = db.Column(db.Binary)

    def __init__(self, replay_blob, replay_pickle):
        self.replay_pickle = replay_pickle
        self.replay_blob = replay_blob

