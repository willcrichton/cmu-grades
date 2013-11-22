from urlparse import urlparse
from HTMLParser import HTMLParser
from config import *
import requests

def authenticate(url):
    ''' queries an asset behind CMU's WebISO wall
    it uses Shibboleth authentication (see: http://dev.e-taxonomy.eu/trac/wiki/ShibbolethProtocol)
    note that you can use this to authenticate stuff beyond just grades! (any CMU service)
    sample usage:
        s = authenticate('https://enr-apps.as.cmu.edu/audit/audit')
        print s.get('https://enr-apps.as.cmu.edu/audit/audit').content
    '''

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
    # magic, but we don't have that luxury, so we manually parse the form.
    class ShibbolethParser(HTMLParser):
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

    parser = ShibbolethParser()
    parser.feed(form)

    # Update headers for where we're coming from
    s.headers = {'Host':  urlparse(url).netloc,
                 'Origin': 'https://login.cmu.edu',
                 'Referer': 'https://login.cmu.edu/idp/profile/SAML2/Redirect/SSO',
                 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/32.0.1700.14 Safari/537.36'}

    # 4. Finish authentication by sending POST request
    s.post(parser.url, data=parser.to_post).content

    return s


