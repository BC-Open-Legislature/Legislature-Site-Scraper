# BC Open Legislature Website Scraper

### Description

The scraper for the BC open legislature site that scrapes data from the https://leg.bc.ca and saves it to a mongo database for future use

---
### Features
* Collect Member data
  * Collect riding, name, image and more
  * Collect their recent debate / vote data
  * Collect a bio for them
* Debates (hansard)
  * Collect the debates with the member speaking

---
### Planned Features
* Cleanup
  * Cleanup the script so that it's more efficent and can be reused and wont break the second the legislature changes their site
* Voting data
  * Gather the voting data of members
  * Gather the voting tallies of votes
* Bill data
  * Gather the bill data for bills in the legislature

---
### Contributing / Source Code Installation
This covers the installation for developing the application using the source code.

##### Step 1. Installation
###### First clone the github repo to your local machine
```bash
$ git clone https://github.com/BC-Open-Legislature/Legislature-Site-Scraper.git --branch main
```

###### Next enter the directory we just created
```bash
$ cd ./Legislature-Site-Scraper
```

###### Now install all the requirements
```bash
$ python3 -m pip install -r requirements.txt
```

##### Step 2. Data Base Installation / Setup
###### Setup a mongo database
* Setup a remote mongo database on https://cloud.mongodb.com 
* You can also run it on your local machine https://docs.mongodb.com/manual/installation/`
* 

###### Get the mongodb credentials
###### - Remote Database
* Go to the clusters page
* Then click the connect button
* Follow the instructions on the page from there
* Once you have your connection string copy src/example_secrets.json and rename it to secrets.json
* Finally paste your connection string into the MongoCreds portion of the secrets file

###### - Local Database
* Copy src/example_secrets.json
* Paste `mongodb://localhost:8000` into the MongoCreds portion of the secrets file

##### Step 3. Docker
###### Install Docker
* Get docker or the docker CLI from https://docs.docker.com/get-docker/

###### Build The Dockerfile
```bash
docker build -t legislature-site-scraper:1.0 .
```

###### Run The Dockerfile
###### - Docker CLI
```bash
docker run legislature-site-scraper:1.0
```

###### - Docker Desktop
* Go to https://docs.docker.com/desktop/dashboard/#start-a-sample-application and follow the instructions there

---
### Acknowledgements
This idea and scraper is 100% based on the incredible Canadian open parliament project by Michael Mulley 
https://github.com/michaelmulley/openparliament

The data is also collected from the legislature's site at 
https://leg.bc.ca