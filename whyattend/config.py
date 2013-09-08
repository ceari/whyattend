""" Configuration settings.
    This file should be used as a template and overview
    of all available options. Put your local deployment
    settings into local_config.py, which overrides these
    defaults. (see bottom of file)
"""

import datetime

# Database URI (see http://docs.sqlalchemy.org/en/latest/core/engines.html#supported-databases)
DATABASE_URI = 'sqlite:///../tmp/test.db'

# Path to temporary folder for OpenID authentication files
OID_STORE_PATH = 'tmp/oid'

# generate one via e.g. "import os; os.urandom(24)"
SECRET_KEY = ''

CLAN_NAMES = ('CLAN', 'STRONK')
CLAN_IDS = {
    'CLAN': '23456789',
    'STRONK': '34567890'
}

# Temporary folder for uploaded replays
UPLOAD_FOLDER = 'tmp/uploads'

# Wargaming.net API token and base URL
API_TOKEN = ''
API_URL = ''

# WoT Server region code
WOT_SERVER_REGION_CODE = 'eu'

# Key for attendance tracker API functions
API_KEY = 'testkey'

# Map WoT API clan roles to displayed name
ROLE_LABELS = {
    'leader': 'Commander',
    'vice_leader': 'Deputy Commander',
    'commander': 'Field Commander',
    'recruiter': 'Recruiter',
    'private': 'Soldier',
    'recruit': 'Recruit',
    'treasurer': 'Treasurer'
}

CREATE_BATTLE_ROLES = ('leader', 'vice_leader', 'treasurer')
DELETE_BATTLE_ROLES = ('leader', 'vice_leader', 'treasurer')
PAYOUT_ROLES = ('leader', 'vice_leader', 'treasurer')

# How long after the battle date should reserves be able to sign in themselves
RESERVE_SIGNUP_DURATION = datetime.timedelta(days=7)

# Should replays be stored in the database?
STORE_REPLAYS_IN_DB = True

# Logfile
ERROR_LOG_FILE = '/tmp/error.log'
LOG_FILE = '/tmp/whyattend.log'

# Override settings with local config, if present
try:
    from local_config import *
except ImportError:
    pass
