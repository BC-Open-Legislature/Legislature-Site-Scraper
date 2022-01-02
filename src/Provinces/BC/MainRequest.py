import time
from pymongo import MongoClient
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException


class MainRequest():
    def get_daily_data(secrets):
        # -=- Intialization -=-
        options = webdriver.ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-dev-shm-usage')

        drive = webdriver.Chrome(options=options)

        cluster = MongoClient(secrets)

        # -=- Debates -=-

        # ~ Get the main legislative page
        drive.get('https://www.leg.bc.ca/')
        time.sleep(5)

        # ~ Click on the debates portion of the page
        for element in drive.find_element(By.CLASS_NAME, 'BCLASS-bulleted-list').find_element(By.XPATH, './*'):
            try:
                if 'Debates' in element.text:
                    element.find_element(By.TAG_NAME, 'a').click()
                    break
            except StaleElementReferenceException:
                pass
        time.sleep(5)

        outer_path_for_debates = drive.find_element(By.CLASS_NAME, 'BCLASS-Hansard-List')
        # = Used for making sure all the debates being read from are on the same day
        day = ''
        links_to_check = []      # = Used for looping over every debate that happend on that day
        # = Used to store a temporary array of the debate links in a day to be added to links_to_check
        temp_links_to_check = []
        offset = 0

        # ~ Loop over all the recent debates and find the most recent finalized transcript
        for i in range(len(outer_path_for_debates.find_elements(By.XPATH, './*'))):
            i = i-offset
            # ~ Get the title of the debate (ex. Tuesday, June 8, 2021, Morning — Committee C	Blues)
            # = Title of the debate used for finding out if it's still a draft
            current_debate_text = outer_path_for_debates.find_elements(By.XPATH, './*')[i].text.lower()
            if current_debate_text != '' and 'blues' not in current_debate_text and 'live' not in current_debate_text and 'page' not in current_debate_text:

                # ~ Check if it's the same day still
                if current_debate_text.split(',')[0] == day or day == '':
                    # ~ Set the day to check on the be this items day
                    day = current_debate_text.split(',')[0]
                    temp_links_to_check.append(outer_path_for_debates.find_elements(By.XPATH,'./*')[i].find_element(By.CLASS_NAME, 'BCLASS-Hansard-HTMLLink').find_element(By.XPATH, './*').get_attribute('href'))

                # ~ If it's not and we have 3 days worth of data leave the loop
                elif len(links_to_check) >= 3:
                    break
                else:
                    day = ''
                    temp_links_to_check.reverse()
                    links_to_check.append(temp_links_to_check)
                    temp_links_to_check = []
                    offset += 1

        links_to_check.reverse()

        for link_to_check in links_to_check:
            # ~ Get the date so that it can be properly archived
            day = link_to_check[0].split('/')[-1].split('am')[0].split('pm')[0]

            # = Stores a dictionary with an array of elements
            debates_for_today = []

            # ~ Loop over every link
            for link in link_to_check:
                drive.get(link)
                time.sleep(10)

                proceedingHeading, procedureHeading, subjectHeading = ['', '', ''];
                drive.switch_to.frame(drive.find_elements(By.TAG_NAME, 'iframe')[0])
                
                for entry in drive.find_element(By.XPATH, '/html/body/div/div[3]').find_elements(By.XPATH, './/*'):
                    # ~ If the speaker begins talking
                    if 'speaker-begins' in entry.get_attribute('class'):
                        debates_for_today.append({
                            'short_name': entry.find_element(By.CLASS_NAME, 'attribution').text.replace(':', ''),
                            'text': entry.text.replace(entry.find_element(By.CLASS_NAME, 'attribution').text, ''),
                            'type': 'member_speech',
                            'time': entry.get_attribute('data-timeofday')[8:],
                            'proceedingHeading': proceedingHeading,
                            'procedureHeading': procedureHeading,
                            'subjectHeading': subjectHeading,
                        })
                    
                    # ~ If the speaker continues talking
                    elif 'speaker-continues' in entry.get_attribute('class'):
                        debates_for_today[-1]['text'] += entry.text;
                    
                    # ~ If they change procedures / proceedings / subject
                    elif 'proceeding-heading' in entry.get_attribute('class'):
                        proceedingHeading = entry.text
                    elif 'procedure-heading' in entry.get_attribute('class'):
                        procedureHeading = entry.text
                    elif 'subject-heading' in entry.get_attribute('class'):
                        subjectHeading = entry.text

            # ~ Format all the data so that it can be easily accessed from a database query
            debates_for_today = {
                '_id': day,                # = yyyymmdd
                'date': day,               # = yyyymmdd
                'data': debates_for_today  # = Full transcripts as listed above
            }

            # ~ Insert the data into the Mongo database (overwrites the data if its already in there)
            cluster['BC_Legislative_Archive']['Debates'].replace_one(
                {'_id': day},       # = Filter
                debates_for_today,  # = New Data
                upsert=True         # = Upsert
            )

        drive.close()

    def get_member_data(secrets):
        # -=- Intialization -=-
        options = webdriver.ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-dev-shm-usage')

        drive = webdriver.Chrome(options=options)

        cluster = MongoClient(secrets)

        # -=- Member Data -=-

        # ~ Get the main legislative page
        drive.get('https://www.leg.bc.ca/learn-about-us/members')
        time.sleep(5)

        # ~ Get all the links for every mla
        mla_list = []  # = Stores a array of all links
        for mla in drive.find_element(By.XPATH, '/html/body/form/div[7]/div/div[2]/div/div[3]/span/div[3]/div/div/ul').find_elements(By.XPATH, './*'):
            mla_list.append(mla.find_elements(By.XPATH,'./*')[0].get_attribute('href'))

        formatted_mlas = []  # = Stores the formatted data for all the mlas
        for mla in mla_list:
            # ~ Go to the mla's page
            drive.get(mla)
            time.sleep(1)

            if 'Hon. ' in drive.find_element(By.XPATH, '/html/body/form/div[7]/div/div[2]/div/div[3]/span/div[1]/div[1]/h2').text:
                text = drive.find_element(By.XPATH, '/html/body/form/div[7]/div/div[2]/div/div[3]/span/div[1]/div[1]/h2').text.split('MLA: ')[1].split('Hon. ')[1].replace(', Q.C.', '').split(' ')
            else:
                text = drive.find_element(By.XPATH, '/html/body/form/div[7]/div/div[2]/div/div[3]/span/div[1]/div[1]/h2').text.split('MLA: ')[1].replace(', Q.C.', '').split(' ')

            abreviated_name = text[0][0] + '. '

            # ~ Abrevivate the name so that it can be found easier
            for tailing_name in text[1:]:
                abreviated_name += tailing_name.replace(', Q.C.', '') + ' '
            abreviated_name = abreviated_name.strip()

            member_data = drive.find_element(By.XPATH, '/html/body/form/div[7]/div/div[2]/div/div[3]/span/div[1]/div[1]/div[2]/div[2]/div[1]/div').text.split('\n')
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
                'name': drive.find_element(By.XPATH, '/html/body/form/div[7]/div/div[2]/div/div[3]/span/div[1]/div[1]/h2').text.replace('Hon. ', '').replace('MLA: ', '').replace(', Q.C.', ''),
                'image': drive.find_element(By.XPATH, '/html/body/form/div[7]/div/div[2]/div/div[3]/span/div[1]/div[1]/div[2]/div[1]/div/img').get_attribute('src'),
                'about': drive.find_element(By.XPATH, '/html/body/form/div[7]/div/div[2]/div/div[3]/span/div[1]/div[1]/div[3]/div').text,
                'member_data': member_data,
                'active': True
            })

        cluster['BC_Legislative_Archive']['Members'].update_many(
            {}, {'$set': {'active': False}}
        )

        # ~ Close the driver
        drive.close()
