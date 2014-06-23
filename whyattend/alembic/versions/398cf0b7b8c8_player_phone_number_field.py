"""Player phone number field

Revision ID: 398cf0b7b8c8
Revises: 37000801b290
Create Date: 2014-06-23 21:07:23.417795

"""

# revision identifiers, used by Alembic.
revision = '398cf0b7b8c8'
down_revision = '37000801b290'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('player', sa.Column('phone', sa.String(length=100), nullable=True))


def downgrade():
    op.drop_column('player', 'phone')
