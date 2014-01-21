from pyquery import PyQuery as pq
from auth import authenticate
from datetime import datetime
from urllib import urlencode
from icalendar import Calendar, Event, UTC
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
    TODO: figure out how to parse shit like the finances response
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

    # to successfully do RPC with SIO, you have to find the correct keys 
    # for each different kind of RPC you're doing and send them with the request
    def get_key(key):
        var_name = re.search("'%s',(\w+)," % key, cachehtml).group(1)
        return re.search("%s='([^']+)'" % var_name, cachehtml).group(1)

    context_key = get_key('userContext.rpc')
    content_key = get_key('bioinfo.rpc')

    # GWT returns something that's _almost_ JSON but not quite
    def parse_gwt(gwt_response):
        return json.loads(gwt_response.replace("'", '"').replace("\\", "\\\\")[4:])
    
    return_data = {}

    # info in user context: full name, major/school
    s.post('https://s3.as.cmu.edu/sio/sio/userContext.rpc', 
           data=('7|0|4|https://s3.as.cmu.edu/sio/sio/|%s|edu.cmu.s3.ui.common.client.serverproxy.user.UserContextService|initUserContext|1|2|3|4|0|' % context_key))

    # get mailbox/smc
    gwt_response =  s.post('https://s3.as.cmu.edu/sio/sio/bioinfo.rpc',
                           data=('7|0|4|https://s3.as.cmu.edu/sio/sio/|%s|edu.cmu.s3.ui.sio.student.client.serverproxy.bio.StudentBioService|fetchStudentSMCBoxInfo|1|2|3|4|0|' % content_key)).content
    sio_json = parse_gwt(gwt_response) 

    return_data['smc'] = sio_json[5][2]
    return_data['mailbox_combo'] = sio_json[5][1]

    # get schedule
    cal = Calendar.from_string(s.get('https://s3.as.cmu.edu/sio/export/schedule/S14_semester.ics?semester=S14').content)
    day_map = {'MO': 1, 'TU': 2, 'WE': 3, 'TH': 4, 'FR': 5}
    return_data['schedule'] = []
    for event in cal.walk():
        if event.name != 'VEVENT': continue

        return_data['schedule'].append({
            'days': map(lambda day: day_map[day], event.get('rrule').get('byday')),
            'location': event.get('location').strip(),
            'summary': event.get('summary').strip(),
            'start_time': event.get('dtstart').dt,
            'end_time': event.get('dtend').dt
        })

    return return_data


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
