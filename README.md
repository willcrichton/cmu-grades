cmu-grades
==========

Provides a service for querying grades and an API for automated login to CMU services. The `app.py` will text you using 
Twilio whenever you get a new grade on Blackboard.

If you're just curious about using the Shibboleth/WebISO authentication, take a look at `auth.py`. If you're looking 
to use the texting app, then you'll need a full install.

To setup, first you need to install [pip](https://pypi.python.org/pypi/pip) and run `pip install -r requirements.txt`.

Then, to use the provided authorization functions, you need to change your `config.py` file to look like:
   
    USERNAME = 'ANDREWID'
    PASSWORD = 'YOURPASSWORD'
    ACCOUNT_SID = 'TWILIO_ACCOUNT_ID'
    AUTH_TOKEN = 'TWILIO_AUTH_TOKEN'
    PHONE_NUMBER = '+YOUR_PHONE_NUMBER'
    TWILIO_NUMBER = '+TWILIO_PHONE_NUMBER'
    
As you can see, using an automated login requires storing your password. Hence, I do not endorse the use of this API on
the grounds of security--storing your password somewhere is bad! But, you know, if you really need automated logins,
the option is there. I personally base64 encoded my password so it's not immediately obvious when you open the file.
