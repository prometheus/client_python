#!/usr/bin/python

try:
    from urllib2 import build_opener, Request, HTTPHandler
except ImportError:
    # Python 3
    from urllib.request import build_opener, Request, HTTPHandler

def handler(url, method, timeout, headers, data):
    '''Default handler that implements HTTP/HTTPS connections.'''
    request = Request(url, data=data)
    request.get_method = lambda: method
    for k, v in headers:
        request.add_header(k, v)
    resp = build_opener(HTTPHandler).open(request, timeout=timeout)
    if resp.code >= 400:
        raise IOError("error talking to pushgateway: {0} {1}".format(
            resp.code, resp.msg))
