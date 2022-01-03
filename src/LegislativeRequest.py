import json

# -=- BC Data Collector -=-
from Provinces.BC.MainRequest import BC

# -=- Get Credentials -=-
with open('./secrets.json', 'r') as secrets_file:
    secrets = json.load(secrets_file)['MongoCreds']

bc_request = BC(secrets)

# -=- If an election has happened get the member data -=-
if bc_request.check_for_bc_election():
    bc_request.get_member_data()

# -=- Fetch Data -=-
bc_request.get_daily_data()

# -=- Clean Up Chrome Driver -=-
bc_request.clean_up()