import os

DB_HOST = os.environ['DB_PORT_5432_TCP_ADDR']

DATABASE_URI = 'postgresql+psycopg2://docker:docker@%s:5432/docker' % (DB_HOST, )

SECRET_KEY = "abcdefgh"
CLAN_NAMES = ('WHY', )
CLAN_IDS = {
    'WHY': '500014725',
}
UPLOAD_FOLDER = '/tmp/whyattend/uploads'

OID_STORE_PATH = '/tmp/whyattend/oid'

ERROR_LOG_FILE = '/tmp/error.log'
LOG_FILE = '/tmp/whyattend.log'

API_URL = 'http://api.worldoftanks.eu/'
API_TOKEN = 'apitoken'

API_KEY = 'apikey'

import datetime
RESERVE_SIGNUP_ALLOWED = True
RESERVE_SIGNUP_DURATION = datetime.timedelta(days=70)

MENU_LINKS = [
    ('Global Map', 'http://worldoftanks.eu/clanwars/maps/globalmap/'),
    ('Campaign Map', 'http://worldoftanks.eu/clanwars/eventmap/'),
]

STATISTICS_VISIBLE = {
    'win_rate_by_commander': True,
}
