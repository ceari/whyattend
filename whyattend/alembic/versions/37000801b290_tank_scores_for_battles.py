"""Tank scores for battles

Revision ID: 37000801b290
Revises: 533b503ed449
Create Date: 2014-05-06 21:03:28.609214

"""

# revision identifiers, used by Alembic.
revision = '37000801b290'
down_revision = '533b503ed449'

from alembic import op
import sqlalchemy as sa

from whyattend.model import Base, Battle, db_session
from whyattend import replays
Base.metadata.bind = op.get_bind()


def upgrade():
    op.add_column('battle', sa.Column('score_enemy_team', sa.Integer(), nullable=True))
    op.add_column('battle', sa.Column('score_own_team', sa.Integer(), nullable=True))
    for battle in Battle.query.all():
        replay = battle.replay
        if replay and replay.replay_pickle:
            try:
                battle.score_own_team, battle.score_enemy_team = replays.score(replay.unpickle())
            except Exception as e:
                print "Error parsing pickle of battle " + str(battle.id), e
                pass
    db_session.commit()
    ### end Alembic commands ###


def downgrade():
    op.drop_column('battle', 'score_own_team')
    op.drop_column('battle', 'score_enemy_team')
    ### end Alembic commands ###
