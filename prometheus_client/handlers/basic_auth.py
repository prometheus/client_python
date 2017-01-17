#!/usr/bin/python

import base64

from prometheus_client.handlers.base import handler as default_handler

def handler(url, method, timeout, headers, data, **kwargs):
    '''Handler that implements HTTP Basic Auth by setting auth headers if
    'username' passed as keyword argument.'''
    if 'username' in kwargs:
        username = kwargs['username']
        password = kwargs['password']
        auth_value = "{0}:{1}".format(username, password)
        auth_header = "Basic {0}".format(base64.b64encode(bytes(auth_value)))
        headers.append(['Authorization', auth_header])
    default_handler(url, method, timeout, headers, data)
