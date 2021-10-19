import json

# -=- BC Data Collector -=-
from Provinces.BC.MainRequest import MainRequest as BC
from Provinces.BC.CheckForElection import check_for_bc_election

# -=- Get Credentials -=-
with open('./secrets.json', 'r') as secrets_file:
    secrets = json.load(secrets_file)['MongoCreds']

# -=- Fetch Data -=-
# BC.get_daily_data(secrets)

# -=- If an election has happened get the member data -=-
if check_for_bc_election(secrets):
    BC.get_member_data(secrets)
