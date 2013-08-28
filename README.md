World of Tanks CW Attendance Tracker
====================================

This web application helps a clan keep track of the clan war
attendance of its players and with gold payouts.

Dependencies
------------

* Python 2.7+
* Various Python libraries (See requirements.txt)
  These can be installed via "pip install -r requirements.txt"

Deployment
----------

As a Python WSGI application, this web application
can be deployed in various ways.
See the Flask documentation (http://flask.pocoo.org/docs/deploying/)
for further information.

Deployment Example
------------------

On Debian 7 you'd have to do the following:

Adjust the settings in `whyattend/config.py` Then:

    > apt-get install python python-pip python-virtualenv
    > virtualenv ./myenv
    > source ./myenv/bin/activate
    > pip install -r requirements.txt
    > pip install tornado

To start the server (here: Tornado):

    > source ./myenv/bin/activate
    > python runtornado.py

This will start a Tornado server listening on port 5001. It
is recommended to let Tornado listen only on localhost and put
it behind a web server such as nginx or apache.