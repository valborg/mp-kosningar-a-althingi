import xml.etree.ElementTree as ET
import numpy as np
import requests
import os
from multiprocessing.pool import ThreadPool

# this is just how I parse the xml, I took out what I thought was essential, there might be something more useful 
# but I doubt it
def parse_issue(lobendespogelse):
    filepath = str(os.getcwd()) + '/data/atvk_%d.xml' %lobendespogelse
    with open(filepath) as f:
        content = f.read()
    tree = ET.fromstring(content)
    if(len(tree.attrib)<2):
        return
    thing = tree.attrib['þingnúmer']
    issue_nr = tree.attrib['málsnúmer']
    votes = {}
    for child in tree:
        if(child.tag == 'mál'):
            for case in child:
                if(case.tag == 'málsheiti'):
                    issue_name = case.text
        if(child.tag == 'atkvæðaskrá'):
            for vote in child:
                votes[vote.attrib['id']] = (vote[0].text, vote[1].text)
    if not votes:
        return
    issue = Issue(lobendespogelse,thing, issue_name, issue_nr, votes)
    return issue

def parse_mp(lobendespogelse):
    lobendespogelse = int(lobendespogelse)
    filepath = str(os.getcwd()) + '/data/mp_%d.xml' %lobendespogelse
    with open(filepath) as f:
        content = f.read()
    tree = ET.fromstring(content)
    mp_id = tree.attrib['id']
    things = {}
    for child in tree:
        if(child.tag == 'nafn'):
            mp_name = child.text
        if(child.tag == 'þingsetur'):
            for sitting in child:
                for thing in sitting:
                    if(thing.tag == 'þing'):
                        thing_nr = thing.text
                    if(thing.tag == 'þingflokkur'):
                        things[thing_nr] = (thing.attrib['id'], thing.text)
    mp = MP(mp_id, mp_name, things)
    return mp

class Issue:
    def __init__(self, id, thing, issue_name, case_number, votes):
        #issue id
        self.id = id
        # thing id
        self.thing = thing
        # name of the issue
        self.issue_name = issue_name
        # case number (many votes are on the same issue)
        self.case_number = case_number
        # a dictionary of the votes, id's are mps id the values are the name of the mp and the vote they cast in text
        self.votes = votes
        
class MP:
    def __init__(self, id, name, things):
        # id's for the mp
        self.id = id
        # name of mp
        self.name = name
        # things are dictionaries where the keys are thing_numbers and the values are the party_id and name of the party 
        # that mp belonged to
        self.things = things

#these are the data points for each of the issues, each issue is now its own issue object
# that has has been documented above
# Magic number from the past
ISSUES = map(parse_issue, range(55344))
ISSUES = [issue for issue in ISSUES if issue]

# this is to make sure that the parsing of mps is done smart, only using the numbers that are used

mp_ids = set()
for issue in ISSUES:
    for mp_id in issue.votes:
        mp_ids.add(mp_id)

# here I'm parsing the data into objects, that are documented above

MPS = map(parse_mp, mp_ids)
MPS = {mp.id: mp for mp in MPS}   

# seeing all the votes that where cast, to be able to code them later

v = set()
for issue in ISSUES: 
    v |= {vote[1] for vote in issue.votes.values()}

# this is the data I mostly work with here for testing purposes

from collections import defaultdict
vote_thing = defaultdict(list)
for issue in ISSUES:
    vote_thing[issue.thing].append(issue)



# here I'm creating the master data
# you access each vote by thing_data[id_nr_of_thing_as_string]['votes'] it has a header that is the issue number 
# and the first column is the mp_id
# the other dicinoaries ['issues'] and ['mps'] are the ISSUES and MPS objects
vote_type = {'f: óþekktur kóði': 0, 'greiðir ekki atkvæði': 0, 'boðaði fjarvist': 0, 'já': 1, 'fjarverandi': 0, 'nei': 2}
# vote types come from v, see above
thing_data = {}
for thing_id, issues in vote_thing.items():
    mp_ids = set()
    for issue in issues:
        mp_ids |= set(issue.votes.keys())
    mps = [MPS[mp_id] for mp_id in mp_ids]
    width = len(issues)
    height = len(mps)
    thing_array = np.zeros((height+1, width+1))
    
    for i, mp in enumerate(mps):
        for j, issue in enumerate(issues):
            if mp.id in issue.votes:
                vote = issue.votes[mp.id][1]
                thing_array[i+1][0] = int(mp.id)
                thing_array[0][j+1] = int(issue.id)
                thing_array[i+1][j+1] = int(vote_type.get(vote, 0))
    # Magic number from the past
    thing_array[0][0] = 8008
    thing_data[thing_id] = {
        'issues': issues,
        'mps'   : mps,
        'votes' : thing_array
    }

def mp_fetcher(lobendespogelse):
    lobendespogelse = int(lobendespogelse)
    if(lobendespogelse%100 == 0):
        print("fetching: ", lobendespogelse)
    filepath = str(os.getcwd()) + '/data/mp_%d.xml' %lobendespogelse
    if(os.path.exists(filepath)):
        return(lobendespogelse, "komið")
    baseUrl = 'http://www.althingi.is/altext/xml/thingmenn/thingmadur/thingseta/?nr='+str(lobendespogelse)
    resp = requests.get(baseUrl)
    if resp.status_code == 200:
        with open(filepath, 'w') as f:
            f.write(resp.content.decode('UTF-8'))
        return (lobendespogelse, True, resp.status_code)
    return(lobendespogelse, False, resp.status_code)

#never run, ever. This is getting the data from the website, takes time.
def fetch_data_for_mps(mp_ids):
    with ThreadPool(100) as p:
        results = p.map(mp_fetcher, mp_ids)