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

# sends text if grades have changed
def run():
    
    # fetches grades from blackboard
    courses = get_blackboard_grades()
    
    # gets saved grades
    data = {}
    exists = os.path.exists('grades.json')
    if exists:
        f = open('grades.json', 'r+')
        old_courses = json.loads(f.read())
        f.seek(0)

        # essentially diff the new scores and old scores
        new_scores = {}
        for course, grades in courses.iteritems():
            if not course in old_courses: break
            old_grades = old_courses[course]
            new_hw = [(hw, grades[hw]) for hw in grades if hw not in old_grades]
            if len(new_hw) > 0:
                new_scores[course] = new_hw

        # send a text if scores have changed
        if len(new_scores) > 0:
            client = TwilioRestClient(ACCOUNT_SID, AUTH_TOKEN)
            message = 'New grades!\n'
            for course in new_scores:
                message += course + ': ' + ', '.join(map(lambda hw: hw[0] + ' [' + str(round(100.0 * hw[1][0] / hw[1][1])) + ']', new_scores[course])) + '\n'
            client.sms.messages.create(to=PHONE_NUMBER, from_=TWILIO_NUMBER, body=message)
    
    else:
        f = open('grades.json', 'w')

    # write out the new scores
    f.write(json.dumps(courses))
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
    
