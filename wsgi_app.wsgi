import sys
sys.path.insert(0, '/var/www/clanwars')
venv_path = '/var/www/clanwars/env/bin/activate_this.py'
execfile(venv_path, dict(__file__=venv_path))

from whyattend.webapp import app as application
