from pprint import pprint

from sqlalchemy import create_engine, Table, MetaData
from sqlalchemy.sql import select

engine = create_engine("mysql://root@localhost/clanwars?use_unicode=0")
conn = engine.connect()
metadata = MetaData()
tanks = Table('wot_tanks_all_api2', metadata, autoload=True, autoload_with=engine)
tank_dict = {}
for row in list(conn.execute(select([tanks]))):
    tank_dict[row.tank_text_id] = {
        'tier': row.level
    }

pprint(tank_dict)
