"""Add email address to player

Revision ID: 18b90187fbae
Revises: None
Create Date: 2013-11-30 17:44:21.901888

"""

# revision identifiers, used by Alembic.
revision = '18b90187fbae'
down_revision = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    op.add_column('player', sa.Column('email', sa.String(length=100), default='', nullable=True))

def downgrade():
    op.drop_column('player', 'email')
