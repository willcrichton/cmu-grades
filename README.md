cmu-grades
==========

Provides an API for automated login to CMU services. Contains a few sample programs for extracting data from Academic Audit and Blackboard. Please email [willcrichton@cmu.edu](willcrichton@cmu.edu) with any issues.

To use the provided authorization functions, you need to change your `config.py` file to look like:
   
    USERNAME = 'ANDREWID'
    PASSWORD = 'YOURPASSWORD'
    
As you can see, using an automated login requires storing your password. Hence, I do not endorse the use of this API on
the grounds of security--storing your password somewhere is bad! But, you know, if you really need automated logins,
the option is there. I personally base64 encoded my password so it's not immediately obvious when you open the file.
