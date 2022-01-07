import time
import pymongo
from pymongo import MongoClient
from selenium import webdriver
from selenium.webdriver.common.by import By


class BC():
    def __init__(self, secrets: str) -> None:
        options = webdriver.ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')

        self.drive = webdriver.Chrome(options=options)
        self.drive.implicitly_wait(5)

        self.cluster = MongoClient(secrets)

    def clean_up(self) -> None:
        self.drive.close()

    def check_for_bc_election(self) -> bool:
        '''Check for whether or not a BC election has happend using wikipedia'''

        # -=- Get The Wikipedia Page For The BC Election -=-
        self.drive.get('https://en.wikipedia.org/wiki/2020_British_Columbia_general_election')

        while True:
            # ~ Check if it's the most recent election
            if 'Next' not in self.drive.find_element(By.XPATH, '/html/body/div[3]/div[3]/div[5]/div[1]/table[1]/tbody/tr[2]/td/table/tbody/tr/td[3]/a').text:
                self.drive.find_element(By.XPATH, '/html/body/div[3]/div[3]/div[5]/div[1]/table[1]/tbody/tr[2]/td/table/tbody/tr/td[3]/a').click()
            else:
                # ~ Check if it's a current election
                if 'On' not in self.drive.find_element(By.XPATH, '/html/body/div[3]/div[3]/div[5]/div[1]/table[1]/tbody/tr[2]/td/table/tbody/tr/td[2]').text:
                    election = self.drive.find_element(By.CLASS_NAME, 'infobox-title').text
                    current_election = self.cluster['BC_Legislative_Archive']['Legislative_Data'].find_one(
                        {
                            '_id': 'current_election'
                        }
                    )
                    current_election = '' if current_election == None else current_election['value']

                    if election == current_election:
                        return False
                    else:
                        self.cluster['BC_Legislative_Archive']['Legislative_Data'].replace_one(
                            {'_id': 'current_election'},
                            {'_id': 'current_election', 'value': election},
                            upsert=True
                        )
                        return True


    def get_daily_data(self):
        latest_date = self.cluster['BC_Legislative_Archive']['Debates'].find().limit(1).sort('_id', direction=pymongo.DESCENDING)[0]['date']

        self.drive.get('https://www.leg.bc.ca/')

        # ~ Click on the debates portion of the page
        for element in self.drive.find_element(By.CLASS_NAME, 'BCLASS-bulleted-list').find_elements(By.XPATH, './*'):
            if 'Debates' in element.text:
                element.find_element(By.TAG_NAME, 'a').click()
                break

        outer_path_for_debates = self.drive.find_element(By.CLASS_NAME, 'BCLASS-Hansard-List')
        day = ''
        links_to_check = []
        temp_links_to_check = []

        for i in range(len(outer_path_for_debates.find_elements(By.XPATH, './*'))):
            # ~ Get the title of the debate (ex. Tuesday, June 8, 2021, Morning — Committee C	Blues)
            current_debate_text = outer_path_for_debates.find_elements(By.XPATH, './*')[i].text.lower()
            if current_debate_text != '' and 'blues' not in current_debate_text and 'live' not in current_debate_text and 'page' not in current_debate_text:
                if current_debate_text.split(',')[0] != day:
                    day = ''
                    temp_links_to_check.reverse()
                    links_to_check.append(temp_links_to_check)
                    temp_links_to_check = []
                day = current_debate_text.split(',')[0]
                temp_links_to_check.append(outer_path_for_debates.find_elements(By.XPATH,'./*')[i].find_element(By.CLASS_NAME, 'BCLASS-Hansard-HTMLLink').find_element(By.XPATH, './*').get_attribute('href'))
                if temp_links_to_check[0].split('/')[-1].split('am')[0].split('pm')[0] == latest_date:
                    break

        links_to_check.reverse()

        for link_to_check in links_to_check[:-1]:
            # ~ Get the date so that it can be properly archived
            day = link_to_check[0].split('/')[-1].split('am')[0].split('pm')[0]

            # = Stores a dictionary with an array of elements
            debates_for_today = []

            # ~ Loop over every link
            for link in link_to_check:
                self.drive.get(link)
                time.sleep(5)

                proceedingHeading = '' 
                procedureHeading = '' 
                subjectHeading = ''
                self.drive.switch_to.frame(self.drive.find_element(By.ID, 'BCLASS-Hansard-ContentFrame-v2'))
                
                for entry in self.drive.find_element(By.CLASS_NAME, 'transcript').find_elements(By.XPATH, './/*'):
                    # ~ If the speaker begins talking
                    if 'speaker-begins' in entry.get_attribute('class'):
                        name = entry.find_element(By.CLASS_NAME, 'attribution').text.replace(':', '').replace('Hon. ', '').replace(', Q.C. ', '').replace('’', '\'')
                        speaker = self.cluster['BC_Legislative_Archive']['Members'].find_one({'_id': name})
                        if speaker == None:
                            speaker = {}
                        
                        debates_for_today.append({
                            'short_name': name,
                            'name': speaker.get('name', name),
                            'image': speaker.get('image', ''),
                            'party': speaker.get('member_data', {}).get('party', 'None'),
                            'location': speaker.get('member_data', {}).get('location', 'Unknown'),

                            'text': entry.text.replace(entry.find_element(By.CLASS_NAME, 'attribution').text, ''),
                            'proceedingHeading': proceedingHeading,
                            'procedureHeading': procedureHeading,
                            'subjectHeading': subjectHeading,

                            'time': entry.get_attribute('data-timeofday')[8:],
                        })
                    
                    # ~ If the speaker continues talking
                    elif 'speaker-continues' in entry.get_attribute('class'):
                        debates_for_today[-1]['text'] += f' {entry.text}';
                    
                    # ~ If they change procedures / proceedings / subject
                    elif 'proceeding-heading' in entry.get_attribute('class'):
                        proceedingHeading = entry.text.replace('\n', ' ')
                    elif 'procedure-heading' in entry.get_attribute('class'):
                        procedureHeading = entry.text.replace('\n', ' ')
                    elif 'subject-heading' in entry.get_attribute('class'):
                        subjectHeading = entry.text.replace('\n', ' ')

            # ~ Format all the data so that it can be easily accessed from a database query
            debates_for_today = {
                '_id': day,                # = yyyymmdd
                'date': day,               # = yyyymmdd
                'data': debates_for_today  # = Full transcripts as listed above
            }

            # ~ Insert the data into the Mongo database (overwrites the data if its already in there)
            self.cluster['BC_Legislative_Archive']['Debates'].replace_one(
                {'_id': day},       # = Filter
                debates_for_today,  # = New Data
                upsert=True         # = Upsert
            )

    def get_member_data(self):
        # -=- Member Data -=-

        # ~ Get the main legislative page
        self.drive.get('https://www.leg.bc.ca/learn-about-us/members')

        # ~ Get all the links for every mla
        mla_list = []  # = Stores a array of all links
        for mla in self.drive.find_element(By.XPATH, '/html/body/form/div[7]/div/div[2]/div/div[3]/span/div[3]/div/div/ul').find_elements(By.XPATH, './*'):
            mla_list.append(mla.find_elements(By.XPATH,'./*')[0].get_attribute('href'))

        formatted_mlas = []  # = Stores the formatted data for all the mlas
        for mla in mla_list:
            # ~ Go to the mla's page
            self.drive.get(mla)

            if 'Hon. ' in self.drive.find_element(By.XPATH, '/html/body/form/div[7]/div/div[2]/div/div[3]/span/div[1]/div[1]/h2').text:
                text = self.drive.find_element(By.XPATH, '/html/body/form/div[7]/div/div[2]/div/div[3]/span/div[1]/div[1]/h2').text.split('MLA: ')[1].split('Hon. ')[1].replace(', Q.C.', '').split(' ')
            else:
                text = self.drive.find_element(By.XPATH, '/html/body/form/div[7]/div/div[2]/div/div[3]/span/div[1]/div[1]/h2').text.split('MLA: ')[1].replace(', Q.C.', '').split(' ')

            abreviated_name = text[0][0] + '. '

            # ~ Abrevivate the name so that it can be found easier
            for tailing_name in text[1:]:
                abreviated_name += tailing_name.replace(', Q.C.', '') + ' '
            abreviated_name = abreviated_name.strip()

            member_data = self.drive.find_element(By.XPATH, '/html/body/form/div[7]/div/div[2]/div/div[3]/span/div[1]/div[1]/div[2]/div[2]/div[1]/div').text.split('\n')
            # ~ If the member has titles format it so
            if len(member_data) > 3:
                member_data = {
                    'titles': member_data[0],
                    'location': member_data[1],
                    'elected': member_data[2],
                    'party': member_data[3],
                }
            else:
                member_data = {
                    'titles': '',
                    'location': member_data[0],
                    'elected': member_data[1],
                    'party': member_data[2],
                }
            # ~ Add the data to the array of formatted data
            formatted_mlas.append({
                '_id': str(abreviated_name),
                'abreviated_name': str(abreviated_name),
                'name': self.drive.find_element(By.XPATH, '/html/body/form/div[7]/div/div[2]/div/div[3]/span/div[1]/div[1]/h2').text.replace('Hon. ', '').replace('MLA: ', '').replace(', Q.C.', ''),
                'image': self.drive.find_element(By.XPATH, '/html/body/form/div[7]/div/div[2]/div/div[3]/span/div[1]/div[1]/div[2]/div[1]/div/img').get_attribute('src'),
                'about': self.drive.find_element(By.XPATH, '/html/body/form/div[7]/div/div[2]/div/div[3]/span/div[1]/div[1]/div[3]/div').text,
                'member_data': member_data,
                'active': True
            })

        self.cluster['BC_Legislative_Archive']['Members'].update_many(
            {}, {'$set': {'active': False}}
        )

        for mla in formatted_mlas:
            self.cluster["BC_Legislative_Archive"]["Members"].replace_one(
                {"_id": mla["_id"]},
                mla,
                True
            )
