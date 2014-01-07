from pyquery import PyQuery as pq
from auth import authenticate
from datetime import datetime
from urllib import urlencode
import re
import json

def get_final_grades():
    ''' extracts your grades from CMU's academic audit
    returns a json of course -> letter grade (string)
    * means you're taking the class and grades haven't been put in yet
    AP means you got it through AP credit
    P is pass
    '''

    s = authenticate('https://enr-apps.as.cmu.edu/audit/audit')

    # find out the params for main major auditing
    mainFrame = s.get('https://enr-apps.as.cmu.edu/audit/audit?call=2').content
    d = pq(mainFrame)
    params = {'call': 7}
    for htmlInput in d('input[type=hidden]'):
        name = d(htmlInput).attr('name')
        value = d(htmlInput).attr('value')
        if name != 'call':
            params[name] = value

    # get page for given major
    classes = s.get('https://enr-apps.as.cmu.edu/audit/audit?' + urlencode(params)).content
    
    # take grades from <pre>s in the page
    d = pq(classes)
    courses = {}
    for pre in d('pre'):
        data = d(pre).text()
        for line in data.split('\n'):
            matches = re.search('(\d+-\d+) \w+\s*\'\d+ ((\w|\*)+)\s*(\d+\.\d)\s*$', line)
            if matches is not None:
                course = matches.group(1)
                grade = matches.group(2)
                courses[course] = grade
                    
    return courses

def get_autolab_grades():
    s = authenticate('https://autolab.cs.cmu.edu')
    
    main = s.get('https://autolab.cs.cmu.edu').content
    d = pq(main)
    current_courses = d('#content > ul > li > a')
    grades = {}

    for course in current_courses:
        course_page = s.get('https://autolab.cs.cmu.edu%s/gradebook/student' % d(course).attr('href')).content
        course_name = d(course).text()
        cd = pq(course_page)

        grades[course_name] = {}

        assignments = cd('.grades tr')
        for assgn in assignments:
            if d(assgn).attr('class') == 'header': continue
            grade = d(assgn).text()
            matches = re.search('^([\D\s]*) \d ([\d\.]+) / ([\d\.]+)$', grade)

            if matches is not None:
                name = matches.group(1)
                score = float(matches.group(2))
                total = float(matches.group(3))

                grades[course_name][name] = [score, total]
                

    return grades

def get_sio():
    ''' get information from SIO
    TODO: parse GWT response
    '''

    s = authenticate('https://s3.as.cmu.edu/sio/index.html')
    s.headers['Origin'] = 'https://s3.as.cmu.edu'
    s.headers['Referer'] = 'https://s3.as.cmu.edu/sio/index.html'
    s.headers['X-GWT-Module-Base'] = 'https://s3.as.cmu.edu/sio/sio/'
    s.headers['DNT'] = '1'
    s.headers['Content-Type'] = 'text/x-gwt-rpc; charset=UTF-8'

    siojs = s.get('https://s3.as.cmu.edu/sio/sio/sio.nocache.js').content
    permutation = re.search("Ub='([^']+)'", siojs).group(1)
    s.headers['X-GWT-Permutation'] = permutation

    page_name = 'https://s3.as.cmu.edu/sio/sio/%s.cache.html' % (permutation)
    cachehtml = s.get(page_name).content

    auth_key = re.search("vLi='([^']+)'", cachehtml).group(1)
    context_key = re.search("cHi='([^']+)'", cachehtml).group(1)
    content_key = re.search("BMi='([^']+)'", cachehtml).group(1)
    
    # info in user context: full name, major/school
    s.post('https://s3.as.cmu.edu/sio/sio/userContext.rpc', 
           data=('7|0|4|https://s3.as.cmu.edu/sio/sio/|%s|edu.cmu.s3.ui.common.client.serverproxy.user.UserContextService|initUserContext|1|2|3|4|0|' % context_key))

    s.post('https://s3.as.cmu.edu/sio/sio/authorization.rpc', 
                 data=('7|0|4|https://s3.as.cmu.edu/sio/sio/|%s|edu.cmu.s3.ui.sio.common.client.serverproxy.AuthorizationService|initLoggedInAsStudent|1|2|3|4|0|' % auth_key))

    s.post('https://s3.as.cmu.edu/sio/sio/bioinfo.rpc',
                 data=('7|0|4|https://s3.as.cmu.edu/sio/sio/|%s|edu.cmu.s3.ui.sio.student.client.serverproxy.bio.StudentBioService|fetchStudentSMCBoxInfo|1|2|3|4|0|' % content_key)).content


def get_blackboard_grades():
    ''' returns all your grades from the current semester
    returns a json of courses mapping to a json of homeworks mapping to an array of [score, total]
    raises an Exception if blackboard refuses to respond (which it does sometimes, query until it works)
    '''

    s = authenticate('https://blackboard.andrew.cmu.edu')

    ''' As of November 2013, Blackboard loads grades dynamically in these "streams"
    so we request a stream containing a list of courses and then request grades for each course
    except, because fuck blackboard, they'll give us a list of courses as a JSON but the grades
    themselves are placed right in an HTML page (so much for ajax). bbGrades is the JSON output
    of the stream we get for a student
    '''
    bbGrades = json.loads(s.post('https://blackboard.andrew.cmu.edu/webapps/streamViewer/streamViewer',
                               data={'cmd': 'loadStream', 'streamName': 'mygrades', 'forOverview': False, 'providers': {}}).content)

    # Sometimes blackboard fails for unknown reasons, raise exception in this case
    if len(bbGrades['sv_extras']['sx_filters']) == 0:
        raise Exception('blackboard connection failed')

    grades = {}
    now = datetime.now()

    currSemester = ('F' if now.month > 6 else 'S') + str(now.year % 100)

    for course_id, course in bbGrades['sv_extras']['sx_filters'][0]['choices'].iteritems():

        # we rely on blackboard's naming convention that all courses are of the pattern [SEASON][YEAR]-[COURSE NAME]
        # also, :3
        if course[:3] != currSemester: continue

        # get the HTML page for the specific set of grades we want
        grades[course] = {}
        html = s.get('https://blackboard.andrew.cmu.edu/webapps/bb-mygrades-BBLEARN/myGrades?course_id=%s&stream_name=mygrades' % course_id).content
        
        # use pyquery (like jQuery) to extract grades
        d = pq(html)
        for homework in d('.grade-item'):
            hw = d(homework).find('.name').text().strip()
            grade = d(homework).find('.gradeCellGrade').text()
            if grade is None: continue

            matches = re.search('([\d\.]+)\s*/([\d\.]+) Grade$', grade)
            if matches is None: continue

            grades[course][hw] = [float(matches.group(1)), float(matches.group(2))]

    return grades
