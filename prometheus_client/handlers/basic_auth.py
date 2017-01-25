#!/usr/bin/python

import base64

from prometheus_client.exposition import default_handler

def handler(url, method, timeout, headers, data, username = None, password = None):
    def handle():
        '''Handler that implements HTTP Basic Auth.
        Sets auth headers using supplied 'username' and 'password', if set.
        '''
        if username is not None and password is not None:
            auth_value = "{0}:{1}".format(username, password)
            auth_header = "Basic {0}".format(base64.b64encode(bytes(auth_value)))
            headers.append(['Authorization', auth_header])
        default_handler(url, method, timeout, headers, data)()

    return handle
