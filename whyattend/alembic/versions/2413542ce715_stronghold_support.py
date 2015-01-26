"""Stronghold support

Revision ID: 2413542ce715
Revises: 398cf0b7b8c8
Create Date: 2014-11-08 18:03:01.861716

"""

# revision identifiers, used by Alembic.
revision = '2413542ce715'
down_revision = '398cf0b7b8c8'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('battle', sa.Column('stronghold', sa.Boolean(), nullable=True))
    op.add_column('player_battle', sa.Column('resources_earned', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('player_battle', 'resources_earned')
    op.drop_column('battle', 'stronghold')
