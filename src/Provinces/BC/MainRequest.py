import time
from tqdm import tqdm
from pymongo import MongoClient
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


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
        drive.get("https://www.leg.bc.ca/")
        time.sleep(5)

        # ~ Click on the debates portion of the page (might change over time so edit this)
        drive.find_element_by_xpath(
            "/html/body/form/div[7]/div/div[1]/div[1]/div/div[2]/div[2]/div/div/div[2]/div[1]/div[1]/div/div[2]/div[3]/div/div[1]/div/div/div/table/tbody/tr/td/ul/li[8]/a").click()
        time.sleep(5)

        outer_path_for_debates = drive.find_element_by_xpath(
            "/html/body/form/div[7]/div/div[2]/div/div[3]/span/div[3]/div[1]/div/div/div/div/div[2]/ul")
        # = Used for making sure all the debates being read from are on the same day
        day = ""
        links_to_check = []      # = Used for looping over every debate that happend on that day
        # = Used to store a temporary array of the debate links in a day to be added to links_to_check
        temp_links_to_check = []
        offset = 0

        # ~ Loop over all the recent debates and find the most recent finalized transcript
        for i in range(len(outer_path_for_debates.find_elements_by_xpath("./*"))):
            i = i-offset
            # ~ Get the title of the debate (ex. Tuesday, June 8, 2021, Morning — Committee C	Blues)
            # = Title of the debate used for finding out if it's still a draft
            current_debate_text = outer_path_for_debates.find_elements_by_xpath(
                "./*")[i].text.lower()
            if current_debate_text != "" and current_debate_text.__contains__("blues") == False and current_debate_text.__contains__("live") == False and current_debate_text.__contains__("page") == False:

                # ~ Check if it's the same day still
                if current_debate_text.split(',')[0] == day or day == "":
                    # ~ Set the day to check on the be this items day
                    day = current_debate_text.split(',')[0]
                    temp_links_to_check.append(outer_path_for_debates.find_elements_by_xpath(
                        "./*")[i].find_element_by_class_name("BCLASS-Hansard-HTMLLink").find_element_by_xpath("./*").get_attribute('href'))

                # ~ If it's not and we have 3 days worth of data leave the loop
                elif len(links_to_check) >= 3:
                    break
                else:
                    day = ""
                    temp_links_to_check.reverse()
                    links_to_check.append(temp_links_to_check)
                    temp_links_to_check = []
                    offset += 1

        links_to_check.reverse()

        # ~ Loop over all the links
        status_bar = tqdm(
            links_to_check,
            total=len(links_to_check),
            desc='Gathering Data'
        )

        for link_to_check in status_bar:
            # ~ Get the date so that it can be properly archived
            day = link_to_check[0].split('/')[-1].split('am')[0].split('pm')[0]

            debates_for_today = [{"type": "current_speaker", "short_name": cluster["BC_Legislative_Archive"]["Legislative_Data"].find_one(
                {"_id": "current_speaker"})["value"]}]  # = Stores an array of all the debate data
            # = Stores a dictionary with an array of elements for the recent debates of any member
            recent_data = {}
            index = 1        # = Used to allow the client to find an index

            # ~ Loop over every link
            for link in link_to_check:
                # ~ Read through all the text
                drive.get(link)
                time.sleep(10)
                drive.switch_to.frame(
                    drive.find_elements_by_tag_name('iframe')[0])
                for entry in drive.find_element_by_xpath('/html/body/div/div[3]').find_elements_by_xpath(".//*"):
                    # ~ If the speaker begins talking
                    if "speaker-begins" in entry.get_attribute('class'):
                        debates_for_today.append({
                            "short_name": entry.find_element_by_class_name('attribution').text.replace(":", ""),
                            "text": entry.text.replace(entry.find_element_by_class_name('attribution').text, "").replace('\n', ' '),
                            "type": "member_speech",
                            "time": entry.get_attribute('data-timeofday')[8:]
                        })

                        # ~ Check if the name is special or a normal member
                        if entry.find_element_by_class_name('attribution').text.replace(":", "") == "Mr. Speaker":
                            name = debates_for_today[0]["short_name"]
                        else:
                            name = entry.find_element_by_class_name(
                                'attribution').text.replace(":", "")

                        if name not in recent_data:
                            recent_data[name] = []
                        recent_data[name].append(f"{day}:{index}")
                        index += 1
                    # ~ If the speaker continues talking
                    elif "speaker-continues" in entry.get_attribute('class'):
                        debates_for_today.append({
                            "text": entry.text.replace('\n', ' '),
                            "type": "speaker_continues"
                        })
                    # If they change procedures / proceedings / subject
                    elif "proceeding-heading" in entry.get_attribute('class') or "procedure-heading" in entry.get_attribute('class') or "subject-heading" in entry.get_attribute('class'):
                        debates_for_today.append({
                            "text": entry.text.replace('\n', ' '),
                            "type": entry.get_attribute('class').replace("-", "_")
                        })
                        index += 1

            # ~ Format all the data so that it can be easily accessed from a database query
            debates_for_today = {
                "_id": day,                # = yyyymmdd
                "date": day,               # = yyyymmdd
                "data": debates_for_today  # = Full transcripts as listed above
            }

            # ~ Insert the data into the Mongo database (overwrites the data if its already in there)
            cluster["BC_Legislative_Archive"]["Debates"].replace_one(
                {"_id": day},       # = Filter
                debates_for_today,  # = New Data
                upsert=True         # = Upsert
            )

            # -=- Update Recent Member Data (Debates) -=-
            for key in recent_data:
                try:
                    data = cluster["BC_Legislative_Archive"]["Recent_Member_Data"].find_one(
                        {"_id": key})["recent_debates"][-len(recent_data[key]):]
                    for element in recent_data[key]:
                        if element not in data:
                            cluster["BC_Legislative_Archive"]["Recent_Member_Data"].update_one(
                                {"_id": key},
                                {"$push": {"recent_debates": element}}
                            )
                except Exception:
                    pass
        drive.close()
        print("Finished Gathering Daily Data \n")

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
        drive.get("https://www.leg.bc.ca/learn-about-us/members")
        time.sleep(5)

        # ~ Get all the links for every mla
        mla_list = []  # = Stores a array of all links
        for mla in drive.find_element_by_xpath("/html/body/form/div[7]/div/div[2]/div/div[3]/span/div[3]/div/div/ul").find_elements_by_xpath("./*"):
            mla_list.append(mla.find_elements_by_xpath(
                "./*")[0].get_attribute('href'))

        formatted_mlas = []  # = Stores the formatted data for all the mlas
        for mla in mla_list:
            # ~ Go to the mla's page
            drive.get(mla)
            time.sleep(1)

            if drive.find_element_by_xpath("/html/body/form/div[7]/div/div[2]/div/div[3]/span/div[1]/div[1]/h2").text.__contains__("Hon. "):
                text = drive.find_element_by_xpath("/html/body/form/div[7]/div/div[2]/div/div[3]/span/div[1]/div[1]/h2").text.split(
                    "MLA: ")[1].split("Hon. ")[1].replace(", Q.C.", "").split(' ')
                # = Stores if the member is part of a comittee (has the hon. title)
                hon = True
            else:
                text = drive.find_element_by_xpath(
                    "/html/body/form/div[7]/div/div[2]/div/div[3]/span/div[1]/div[1]/h2").text.split("MLA: ")[1].replace(", Q.C.", "").split(' ')
                # = Stores if the member is part of a comittee (has the hon. title)
                hon = False

            if hon == True:
                abreviated_name = "Hon. " + text[0][0] + '. '
            else:
                abreviated_name = text[0][0] + '. '

            # ~ Abrevivate the name so that it can be found easier
            for tailing_name in text[1:]:
                abreviated_name += tailing_name.replace(", Q.C.", "") + " "
            abreviated_name = abreviated_name.strip()

            member_data = drive.find_element_by_xpath(
                "/html/body/form/div[7]/div/div[2]/div/div[3]/span/div[1]/div[1]/div[2]/div[2]/div[1]/div").text.split('\n')
            # ~ If the member has titles format it so
            if len(member_data) > 3:
                member_data = {
                    "titles": member_data[0],
                    "location": member_data[1],
                    "elected": member_data[2],
                    "party": member_data[3],
                    "speaker": False
                }
                if member_data["titles"] == "Speaker of the Legislative Assembly":
                    member_data["speaker"] = True
                    cluster["BC_Legislative_Archive"]["Legislative_Data"].update_one(
                        {"_id": "current_speaker"},
                        {"$set": {"value": str(abreviated_name)}},
                        upsert=True
                    )
                    # ~ If they dont format it so
            else:
                member_data = {
                    "titles": "",
                    "location": member_data[0],
                    "elected": member_data[1],
                    "party": member_data[2],
                    "speaker": False
                }
            # ~ Add the data to the array of formatted data
            formatted_mlas.append({
                "_id": str(abreviated_name),
                "abreviated_name": str(abreviated_name),
                "name": drive.find_element_by_xpath("/html/body/form/div[7]/div/div[2]/div/div[3]/span/div[1]/div[1]/h2").text.replace("Hon. ", "").replace("MLA: ", "").replace(", Q.C.", "") + (" (Mr. Speaker)" * int(member_data["speaker"])),
                "image": drive.find_element_by_xpath("/html/body/form/div[7]/div/div[2]/div/div[3]/span/div[1]/div[1]/div[2]/div[1]/div/img").get_attribute('src'),
                "about": drive.find_element_by_xpath("/html/body/form/div[7]/div/div[2]/div/div[3]/span/div[1]/div[1]/div[3]/div").text,
                "member_data": member_data,
                "active": True
            })

        cluster["BC_Legislative_Archive"]["Members"].update_many(
            {}, {"$set": {"active": False}})
        # ~ Loop over every mla and add it to the database
        for mla in formatted_mlas:
            cluster["BC_Legislative_Archive"]["Members"].replace_one(
                {"_id": mla["_id"]},
                mla,
                True
            )
            try:
                cluster["BC_Legislative_Archive"]["Recent_Member_Data"].insert_one(
                    {
                        "_id": mla["_id"],
                        "recent_votes": [],
                        "recent_debates": []
                    }
                )
            except Exception:
                pass

        # ~ Close the driver to avoid wasted memory
        drive.close()
