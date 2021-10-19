import time
from pymongo import MongoClient
from selenium import webdriver


def check_for_bc_election(secrets: str) -> bool:
    '''Check for whether or not a BC election has happend using wikipedia'''

    options = webdriver.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-dev-shm-usage')

    drive = webdriver.Chrome(options=options)
    drive.implicitly_wait(5)

    # -=- Get The Wikipedia Page For The BC Election -=-
    drive.get('https://en.wikipedia.org/wiki/2020_British_Columbia_general_election')

    while True:
        # ~ Check if it's the most recent election
        if 'Next' not in drive.find_element_by_xpath('/html/body/div[3]/div[3]/div[5]/div[1]/table[1]/tbody/tr[2]/td/table/tbody/tr/td[3]/a').text:
            drive.find_element_by_xpath(
                '/html/body/div[3]/div[3]/div[5]/div[1]/table[1]/tbody/tr[2]/td/table/tbody/tr/td[3]/a'
            ).click()
        else:
            # ~ Check if it's a current election
            if 'On' not in drive.find_element_by_xpath('/html/body/div[3]/div[3]/div[5]/div[1]/table[1]/tbody/tr[2]/td/table/tbody/tr/td[2]').text:
                cluster = MongoClient(secrets)
                election = drive.find_element_by_class_name(
                    "infobox-title"
                ).text
                current_election = cluster["BC_Legislative_Archive"]["Legislative_Data"].find_one(
                    {
                        "_id": "current_election"
                    }
                )
                current_election = '' if current_election == None else current_election["value"]

                if election == current_election:
                    return False
                else:
                    cluster["BC_Legislative_Archive"]["Legislative_Data"].update_one(
                        {"_id": 'current_election'},
                        {"$push": {"value": election}}
                    )
                    return True
