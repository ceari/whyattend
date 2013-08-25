""" Configuration settings.
    This file should be used as a template and overview
    of all available options. Put your local deployment
    settings into local_config.py, which overrides these
    defaults. (see bottom of file)
"""

# Database URI (see http://docs.sqlalchemy.org/en/latest/core/engines.html#supported-databases)
DATABASE_URI = 'sqlite:///test.db'

# Path to temporary folder for OpenID authentication files
OID_STORE_PATH = 'tmp/oid'

# generate one via e.g. "import os; os.urandom(24)"
SECRET_KEY = ''

CLAN_NAMES = ('CLAN', 'STRONK')

# Temporary folder for uploaded replays
UPLOAD_FOLDER = 'tmp/uploads'

# Wargaming.net API token and base URL
API_TOKEN = ''
API_URL = ''

# Key for attendance tracker API functions
API_KEY = 'testkey'

# Map WoT API clan roles to displayed name
ROLE_LABELS = {
    'leader': 'Commander',
    'vice_leader': 'Deputy Commander',
    'commander': 'Company Commander',
    'recruiter': 'Recruiter',
    'private': 'Soldier',
    'recruit': 'Recruit',
    'treasurer': 'Treasurer'
}

CREATE_BATTLE_ROLES = ('leader', 'vice_leader', 'commander', 'treasurer')
DELETE_BATTLE_ROLES = ('leader', 'vice_leader', 'commander', 'treasurer')
PAYOUT_ROLES = ('leader', 'vice_leader', 'commander', 'treasurer')

# Should replays be stored in the database?
STORE_REPLAYS_IN_DB = True

# Override settings with local config, if present
try:
    from whyattend.local_config import *
except ImportError:
    pass
