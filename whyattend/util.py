"""
    Utility classes
    ~~~~~~~~~~~~~~~
"""


class ReverseProxied(object):
    """Wrap the application in this middleware and configure the
    front-end server to add these headers, to let you quietly bind
    this to a URL other than / and to an HTTP scheme that is
    different than what is used locally.

    In nginx:
    location /myprefix {
        proxy_pass http://192.168.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Scheme $scheme;
        proxy_set_header X-Script-Name /myprefix;
        }

    :param app: the WSGI application
    """

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        script_name = environ.get('HTTP_X_SCRIPT_NAME', '')
        if script_name:
            environ['SCRIPT_NAME'] = script_name
            path_info = environ['PATH_INFO']
            if path_info.startswith(script_name):
                environ['PATH_INFO'] = path_info[len(script_name):]

        server = environ.get('HTTP_X_FORWARDED_SERVER', '')
        if server:
            environ['HTTP_HOST'] = server

        scheme = environ.get('HTTP_X_SCHEME', '')
        if scheme:
            environ['wsgi.url_scheme'] = scheme
        return self.app(environ, start_response)


def pretty_date(d):
    """
    Format the time delta between d and now human-friendly. E.g. 'in 2 hours', '20 seconds ago'
    :param d:
    :return:
    """
    from math import fabs
    from datetime import datetime

    now = datetime.now()
    diff = now - d
    total_seconds = diff.seconds + diff.days * 24 * 60 * 60
    sec = int(fabs(total_seconds))

    if sec < 60:
        v = sec
        unit = 'second' + ('s' if v != 1 else '')
    elif sec < 60 * 60:
        v = sec / 60
        unit = 'minute' + ('s' if v != 1 else '')
    elif sec < 60 * 60 * 24:
        v = sec / 60 / 60
        unit = 'hour' + ('s' if v != 1 else '')
    else:
        v = sec / 60 / 60 / 24
        unit = 'day' + ('s' if v != 1 else '')

    if total_seconds < 0:
        return 'in %i %s' % (v, unit)  # future
    else:
        return '%i %s ago' % (v, unit)  # past