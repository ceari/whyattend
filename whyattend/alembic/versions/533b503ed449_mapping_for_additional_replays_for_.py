"""Mapping for additional replays for battles

Revision ID: 533b503ed449
Revises: 5a5fa1c1dc8e
Create Date: 2014-03-27 20:41:56.503403

"""

# revision identifiers, used by Alembic.
revision = '533b503ed449'
down_revision = '5a5fa1c1dc8e'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('replay', sa.Column('associated_battle_id', sa.Integer(), nullable=True))
    op.add_column('replay', sa.Column('player_name', sa.String(length=100), nullable=True))


def downgrade():
    op.drop_column('replay', 'player_name')
    op.drop_column('replay', 'associated_battle_id')
