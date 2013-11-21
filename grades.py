from pyquery import PyQuery as pq
from auth import authenticate
from datetime import datetime
import re
import json

''' get_final_grades() : extracts your grades from CMU's academic audit
returns a json of course -> letter grade (string)
* means you're taking the class and grades haven't been put in yet
AP means you got it through AP credit
'''
def get_final_grades():
    s = authenticate('https://enr-apps.as.cmu.edu/audit/audit')

    # todo: make this dynamic
    classes = s.get('https://enr-apps.as.cmu.edu/audit/audit?call=7&MajorFile=2010:SCS:BS:CS.MAJ&college=college&year=catalog_year&major=degree+in+major').content
    
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


''' get_sio() : get information from SIO
CURRENTLY BROKEN: HOW DOES RPC WORK??? 
TODO: FIX THIS
'''
def get_sio():
    s = authenticate('https://s3.as.cmu.edu/sio/index.html')
    s.headers['Origin'] = 'https://s3.as.cmu.edu'
    s.headers['Referer'] = 'https://s3.as.cmu.edu/sio/index.html'
    s.headers['X-GWT-Module-Base'] = 'https://s3.as.cmu.edu/sio/sio/'
    s.headers['X-GWT-Permutation'] = 'BF8DF859F201A217774ED328C558EDE1'
    s.headers['Content-Type'] = 'text/x-gwt-rpc'

    print s.post('https://s3.as.cmu.edu/sio/sio/grades.rpc', data='7|0|4|https://s3.as.cmu.edu/sio/sio/|D954B1065FB984249A8E6FE7AC94FE73|edu.cmu.s3.ui.sio.student.client.serverproxy.grades.GradesService|fetchSemesterGrades|1|2|3|4|0|').content


''' get_blackboard_grades() : returns all your grades from the current semester
returns a json of courses mapping to a json of homeworks mapping to an array of [score, total]
raises an Exception if blackboard refuses to respond (which it does sometimes, query until it works)
'''
def get_blackboard_grades():
    s = authenticate('https://blackboard.andrew.cmu.edu')

    # make sure our headers are right for blackboard 
    # TODO: are all of these necessary?
    s.headers['Origin'] = 'https://blackboard.andrew.cmu.edu'
    s.headers['Referer'] = 'https://blackboard.andrew.cmu.edu/webapps/streamViewer/streamViewer?cmd=view&streamName=mygrades_d&&override_stream=mygrade'
    s.headers['X-Prototype-Version'] = '1.7'
    s.headers['X-Requested-With'] = 'XMLHttpRequest'

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

    # Dunno what happens with summer courses, not worrying about that case
    currSemester = ('F' if now.month > 6 else 'S') + str(now.year % 100)

    for course_id, course in bbGrades['sv_extras']['sx_filters'][0]['choices'].iteritems():

        # we rely on blackboard's naming convention that all courses are of the pattern [SEASON][YEAR]-[COURSE NAME]
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

print get_blackboard_grades()

