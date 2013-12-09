"""add battle duration

Revision ID: 3a763038a0c9
Revises: 18b90187fbae
Create Date: 2013-12-09 19:29:49.336000

"""

# revision identifiers, used by Alembic.
revision = '3a763038a0c9'
down_revision = '18b90187fbae'

from alembic import op
import sqlalchemy as sa

from whyattend.model import Base, Battle, db_session
Base.metadata.bind = op.get_bind()


def upgrade():
    op.add_column('battle', sa.Column('duration', sa.Integer, default=0, nullable=True))
    # Parse battle duration from existing replay pickles
    for battle in Battle.query.all():
        replay = battle.replay
        if replay and replay.replay_pickle:
            try:
                replay_data = replay.unpickle()
                pickle = replay_data['pickle']
                battle.duration = int(pickle['common']['duration'])
            except Exception as e:
                print "Error parsing pickle of battle " + str(battle.id), e
                pass
    db_session.commit()


def downgrade():
    op.drop_column('battle', 'duration')
