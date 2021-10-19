import json

# -=- BC Data Collector -=-
from Provinces.BC.MainRequest import MainRequest as BC

# -=- Get Credentials -=-
with open('./secrets.json', 'r') as secrets_file:
    secrets = json.load(secrets_file)['MongoCreds']

# -=- Fetch Data -=-
BC.get_daily_data(secrets)
