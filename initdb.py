from whyattend import model
from whyattend import config

model.init_db()

from alembic.config import Config
from alembic import command
alembic_cfg = Config("alembic.ini")
alembic_cfg.set_main_option("sqlalchemy.url", config.DATABASE_URI)
command.stamp(alembic_cfg, "head")
