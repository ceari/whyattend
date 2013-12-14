"""
    Database mapping
    ~~~~~~~~~~~~~~~~
"""

import pickle

from . import config

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Binary
from sqlalchemy.orm import scoped_session, sessionmaker, deferred, relationship
from sqlalchemy.ext.declarative import declarative_base

engine = create_engine(config.DATABASE_URI, convert_unicode=True)
db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

Base = declarative_base()
Base.query = db_session.query_property()


def init_db():
    """ Creates the database tables from the model class declarations.
    Existing tables will not be overwritten. """
    Base.metadata.create_all(bind=engine)


class Player(Base):
    __tablename__ = 'player'
    id = Column(Integer, primary_key=True)
    openid = Column(String(100), unique=True)
    wot_id = Column(String(100), unique=True)

    member_since = Column(DateTime)

    name = Column(String(100), unique=True)
    clan = Column(String(10))
    role = Column(String(50))       # one of {leader, vice_leader, commander, recruiter, private (=soldier), recruit}
    locked = Column(Boolean)        # set to true if player left the clan. Login is no longer possible then.
    lock_date = Column(DateTime)    # When did the player leave
    email = Column(String(100), default='')

    gold_earned = Column(Integer)

    def __init__(self, wot_id, openid, member_since, name, clan, role, locked=False):
        self.wot_id = wot_id
        self.openid = openid
        self.member_since = member_since
        self.name = name
        self.clan = clan
        self.role = role
        self.gold_earned = 0
        self.locked = locked
        self.email = ''

    def battles_played(self):
        return BattleAttendance.query.filter_by(player=self, reserve=False)

    def battles_reserve(self):
        return BattleAttendance.query.filter_by(player=self, reserve=True)

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

    def player_role_value(self):
        """Return an integer for each player role that can be used as sorting key."""
        v = {
            'leader': 6,
            'vice_leader': 5,
            'commander': 4,
            'recruiter': 2,
            'private': 1,
            'recruit': 0,
            'treasurer': 3
        }
        if self.role not in v:
            return 0
        return v[self.role]


class BattleAttendance(Base):
    """ Association class between players and battles. """
    __tablename__ = 'player_battle'
    player_id = Column(Integer, ForeignKey('player.id'), primary_key=True)
    battle_id = Column(Integer, ForeignKey('battle.id'), primary_key=True)
    player = relationship("Player", backref="battles")
    battle = relationship("Battle", backref="attendances")
    reserve = Column(Boolean)

    def __init__(self, player, battle, reserve=False):
        self.player = player
        self.battle = battle
        self.reserve = reserve


class Battle(Base):
    __tablename__ = 'battle'
    id = Column(Integer, primary_key=True)
    date = Column(DateTime)
    clan = Column(String(10))
    enemy_clan = Column(String(10))
    victory = Column(Boolean)
    draw = Column(Boolean)
    paid = Column(Boolean)
    description = Column(Text)
    duration = Column(Integer) # duration of the battle in seconds

    # WoT map name
    map_name = Column(String(80))
    # Which province the battle was for (or provinces, if encounter)
    map_province = Column(String(80))

    battle_commander_id = Column(Integer, ForeignKey('player.id'))
    battle_commander = relationship("Player", backref="battles_commanded", foreign_keys=[battle_commander_id])

    creator_id = Column(Integer, ForeignKey('player.id', ondelete='set null'), nullable=True)
    creator = relationship("Player", backref="battles_created", foreign_keys=[creator_id])

    replay_id = Column(Integer, ForeignKey('replay.id'))
    replay = relationship("Replay", backref="battle", uselist=False)

    battle_group_id = Column(Integer, ForeignKey('battlegroup.id'))
    battle_group = relationship("BattleGroup", backref="battles")
    # Is this the "final battle" of the group? Exactly one per group should be true
    battle_group_final = Column(Boolean)

    def __init__(self, date, clan, enemy_clan, victory, draw, creator, battle_commander, map_name, map_province, duration,
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
        self.duration = duration
        if victory and draw:
            raise Exception("Battle can not be victory and draw at the same time")

    def outcome_str(self):
        if self.victory and not self.draw:
            return 'Victory'
        elif not self.victory and not self.draw:
            return 'Defeat'
        else:
            return 'Draw'

    def outcome_repr(self):
        if self.victory and not self.draw:
            return 'victory'
        elif not self.victory and not self.draw:
            return 'defeat'
        else:
            return 'draw'

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
        return [ba.player for ba in self.attendances if not ba.reserve]

    def get_reserve_players(self):
        return [ba.player for ba in self.attendances if ba.reserve]

    def __str__(self):
        return "%s vs. %s on %s" % (self.clan, self.enemy_clan, self.map_name)


class BattleGroup(Base):
    """
        Representation of grouped battles, e.g. landings which span across multiple battles.
    """
    __tablename__ = 'battlegroup'
    id = Column(Integer, primary_key=True)

    title = Column(String(100))
    description = Column(Text)
    clan = Column(String(10))
    date = Column(DateTime)

    def __init__(self, title, description, clan, date):
        self.title = title
        self.description = description
        self.clan = clan
        self.date = date

    def get_players(self):
        players = set()
        for battle in self.battles:
            for ba in battle.attendances:
                if not ba.reserve:
                    players.add(ba.player)
        return players

    def get_reserves(self):
        players = set()
        for battle in self.battles:
            for ba in battle.attendances:
                if ba.reserve:
                    players.add(ba.player)
        return players

    def get_final_battle(self):
        for battle in self.battles:
            if battle.battle_group_final:
                return battle
        return None

    def get_representative_battle(self):
        for battle in self.battles:
            if battle.battle_group_final:
                return battle
        if self.battles:
            return self.battles[0]
        return None


class Replay(Base):
    __tablename__ = 'replay'
    id = Column(Integer, primary_key=True)
    # The data returned by replays.parse_replay as Python pickle
    replay_pickle = Column(Binary)
    # The replay file
    replay_blob = deferred(Column(Binary))


    def __init__(self, replay_blob, replay_pickle):
        self.replay_pickle = replay_pickle
        self.replay_blob = replay_blob

    def unpickle(self):
        return pickle.loads(self.replay_pickle)


class WebappData(Base):
    __tablename__ = 'webapp_data'
    id = Column(Integer, primary_key=True)
    last_successful_sync = Column(DateTime)
    last_sync_attempt = Column(DateTime)

    @classmethod
    def get(cls):
        data = WebappData.query.get(1)
        if data is None:
            data = WebappData()
            db_session.add(data)
            db_session.commit()
        return data
