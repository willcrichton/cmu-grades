from HTMLParser import HTMLParser
from urlparse import urlparse
from pyquery import PyQuery as pq
from config import *
import base64
import requests
import re
import json

# authenticate(url) queries an asset behind CMU's WebISO wall
# it uses Shibboleth authentication (see: http://dev.e-taxonomy.eu/trac/wiki/ShibbolethProtocol)
def authenticate(url):
    # We're using a Requests (http://www.python-requests.org/en/latest/) session
    s = requests.Session()

    # 1. Initiate sequence by querying the protected asset
    s.get(url)

    # 2. Login to CMU's WebISO "Stateless" page
    s.headers = {'Host': 'login.cmu.edu', 'Referer': 'https://login.cmu.edu/idp/Authn/Stateless'}
    form = s.post('https://login.cmu.edu/idp/Authn/Stateless', 
                  data={'j_username': USERNAME, 'j_password': PASSWORD, 
                        'j_continue': '1', 'submit': 'Login'}).content

    # 3. Parse resultant HTML and send corresponding POST request
    # Here, if you were in a browser, you'd get fed an HTML form
    # that you don't actualy see--it submits instantly with some JS
    # magic, but we don't have that luxury.
    class ShibParser(HTMLParser):
        url = ''
        to_post = {}
        def handle_starttag(self, tag, alist):
            attrs = dict(alist)

            # Figure out where we need to submit to
            if tag == 'form':
                self.url = attrs['action']

            # Save input values
            elif tag == 'input' and attrs['type'] != 'submit':
                self.to_post[attrs['name']] = attrs['value']

    parser = ShibParser()
    parser.feed(form)

    # Update headers for where we're coming from
    s.headers = {'Host':  urlparse(url).netloc,
                 'Origin': 'https://login.cmu.edu',
                 'Referer': 'https://login.cmu.edu/idp/profile/SAML2/Redirect/SSO',
                 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/32.0.1700.14 Safari/537.36'}

    # 4. Finish authentication by sending POST request
    s.post(parser.url, data=parser.to_post).content

    return s


def get_grades():
    s = authenticate('https://enr-apps.as.cmu.edu/audit/audit')
    classes = s.get('https://enr-apps.as.cmu.edu/audit/audit?call=7&MajorFile=2010:SCS:BS:CS.MAJ&college=college&year=catalog_year&major=degree+in+major').content

    class ClassParser(HTMLParser):
        courses = {}
        def handle_data(self, data):
            if self.lasttag == 'pre':
                for line in data.split('\n'):
                    matches = re.search('(\d+-\d+) \w+\s*\'\d+ ((\w|\*)+)\s*(\d+\.\d)\s*$', line)
                    if matches is not None:
                        course = matches.group(1)
                        grade = matches.group(2)
                        self.courses[course] = grade
                    
    parser = ClassParser()
    parser.feed(classes)
    return parser.courses

#print get_grades()

def get_sio():
    s = authenticate('https://s3.as.cmu.edu/sio/index.html')
    s.headers['Origin'] = 'https://s3.as.cmu.edu'
    s.headers['Referer'] = 'https://s3.as.cmu.edu/sio/index.html'
    s.headers['X-GWT-Module-Base'] = 'https://s3.as.cmu.edu/sio/sio/'
    s.headers['X-GWT-Permutation'] = 'BF8DF859F201A217774ED328C558EDE1'
    s.headers['Content-Type'] = 'text/x-gwt-rpc'

    print s.post('https://s3.as.cmu.edu/sio/sio/grades.rpc', data='7|0|4|https://s3.as.cmu.edu/sio/sio/|D954B1065FB984249A8E6FE7AC94FE73|edu.cmu.s3.ui.sio.student.client.serverproxy.grades.GradesService|fetchSemesterGrades|1|2|3|4|0|').content

def get_blackboard():
    s = authenticate('https://blackboard.andrew.cmu.edu')
    s.headers['Origin'] = 'https://blackboard.andrew.cmu.edu'
    s.headers['Referer'] = 'https://blackboard.andrew.cmu.edu/webapps/streamViewer/streamViewer?cmd=view&streamName=mygrades_d&&override_stream=mygrade'
    s.headers['X-Prototype-Version'] = '1.7'
    s.headers['X-Requested-With'] = 'XMLHttpRequest'

    bbGrades = json.loads(s.post('https://blackboard.andrew.cmu.edu/webapps/streamViewer/streamViewer',
                               data={'cmd': 'loadStream', 'streamName': 'mygrades', 'forOverview': False, 'providers': {}}).content)

    grades = {}
    for course_id, course in bbGrades['sv_extras']['sx_filters'][0]['choices'].iteritems():
        if course[:3] != 'F13': continue
        grades[course] = {}
        html = s.get('https://blackboard.andrew.cmu.edu/webapps/bb-mygrades-BBLEARN/myGrades?course_id=%s&stream_name=mygrades' % course_id).content
        
        d = pq(html)
        for homework in d('.grade-item'):
            hw = d(homework).find('.name').text().strip()
            grade = d(homework).find('.gradeCellGrade').text()
            if grade is None: continue

            matches = re.search('([\d\.]+)\s*/([\d\.]+) Grade$', grade)
            if matches is None: continue

            grades[course][hw] = [float(matches.group(1)), float(matches.group(2))]

    print grades

get_blackboard()

