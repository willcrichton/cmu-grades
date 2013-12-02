from crontab import CronTab
from grades import *
from twilio.rest import TwilioRestClient
from config import *
import smtplib
import sys
import os
import json
import site

# writes job to the cron
def install():
    cron = CronTab()
    command = 'export PYTHONPATH=%s; python %s run' % (site.getsitepackages()[0], os.path.realpath(__file__))
    job = cron.new(command=command, comment='cmu-grades')
    job.minute.every(5)
    cron.write()
    print 'Installed cmu-grades!'

# removes job from the cron
def uninstall():
    cron = CronTab()
    job = cron.find_comment('cmu-grades')
    cron.remove(job[0])
    cron.write()
    print 'Uninstalled cmu-grades!'

def send_text(message):
    client = TwilioRestClient(ACCOUNT_SID, AUTH_TOKEN)    
    client.sms.messages.create(to=PHONE_NUMBER, from_=TWILIO_NUMBER, body=message.strip())

def diff(old, new):
    new_scores = {}
    for course, grades in new.iteritems():
        if not course in old: break
        old_grades = old[course]
        if isinstance(grades, basestring) and grades != old_grades:
            new_scores[course] = grades
        else:
            new_grades = [(hw, grades[hw]) for hw in grades if hw not in old_grades]
            if len(new_grades) > 0:
                new_scores[course] = new_grades

    return new_scores

# sends text if grades have changed
def run():
    
    # fetches grades from blackboard
    try:
        courses = get_blackboard_grades()    
        finals = get_final_grades()
    except Exception:
        return
    
    finals['21-241'] = 'Q'

    # gets saved grades
    data = {}
    exists = os.path.exists('grades.json')
    if exists:
        path = os.path.dirname(os.path.realpath(__file__)) + '/grades.json'
        f = open(path, 'r+')
        try:
            old_data = json.loads(f.read())
        except:
            # delete malformed json
            f.close()
            os.remove(path)
            return

        f.seek(0)
        f.truncate()

        old_courses = old_data['courses']
        old_finals = old_data['finals']

        bb_diff = diff(old_courses, courses)

        # send a text if blackboard scores have changed
        if len(bb_diff) > 0:
            message = 'New Blackboard grades!\n'
            for course, grades in bb_diff.iteritems():
                mapper = lambda hw: hw[0] + ' [' + str(round(100.0 * hw[1][0] / hw[1][1])) + ']'
                message += '%s: %s\n' % (course, ', '.join(map(mapper, grades)))
            send_text(message)

        # same for finals from academic audit
        final_diff = diff(old_finals, finals)
        if len(final_diff) > 0:
            message = 'New final grades!\n'
            for course, grade in final_diff.iteritems():
                message += '%s: %s\n' % (course, grade)
            send_text(message)

    else:
        f = open('grades.json', 'w')

    # write out the new scores
    f.write(json.dumps({'courses': courses, 'finals': finals}))
    f.close()


COMMANDS = {
    'install': install,
    'uninstall': uninstall,
    'run': run
}

def main():
    if len(sys.argv) <= 1 or sys.argv[1] not in COMMANDS:
        print 'USAGE: %s <%s>' % (sys.argv[0], "|".join(COMMANDS))
        exit()

    COMMANDS[sys.argv[1]]()

if __name__ == '__main__':
    main()
    
