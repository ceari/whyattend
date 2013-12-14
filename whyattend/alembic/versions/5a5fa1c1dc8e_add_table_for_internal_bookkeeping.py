"""add table for internal bookkeeping

Revision ID: 5a5fa1c1dc8e
Revises: 3a763038a0c9
Create Date: 2013-12-14 23:56:27.650187

"""

# revision identifiers, used by Alembic.
revision = '5a5fa1c1dc8e'
down_revision = '3a763038a0c9'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    op.create_table('webapp_data',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('last_successful_sync', sa.DateTime(), nullable=True),
    sa.Column('last_sync_attempt', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('webapp_data')
