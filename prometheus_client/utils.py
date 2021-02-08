import math
import sys

try:
    from urllib2 import HTTPError, HTTPRedirectHandler, Request
except ImportError:
    # Python 3
    from urllib.error import HTTPError
    from urllib.request import HTTPRedirectHandler, Request

PYTHON27_OR_OLDER = sys.version_info <= (2, 7)
INF = float("inf")
MINUS_INF = float("-inf")
NaN = float("NaN")


def floatToGoString(d):
    d = float(d)
    if d == INF:
        return '+Inf'
    elif d == MINUS_INF:
        return '-Inf'
    elif math.isnan(d):
        return 'NaN'
    else:
        s = repr(d)
        dot = s.find('.')
        # Go switches to exponents sooner than Python.
        # We only need to care about positive values for le/quantile.
        if d > 0 and dot > 6:
            mantissa = '{0}.{1}{2}'.format(s[0], s[1:dot], s[dot + 1:]).rstrip('0.')
            return '{0}e+0{1}'.format(mantissa, dot - 1)
        return s


class PrometheusRedirectHandler(HTTPRedirectHandler):
    """
    Allow additional methods (e.g. PUT) and data forwarding in redirects.

    Use of this class constitute a user's explicit agreement to the
    redirect responses the Prometheus client will receive when using it.
    You should only use this class if you control or otherwise trust the
    redirect behavior involved and are certain it is safe to full transfer
    the original request (method and data) to the redirected URL. For
    example, if you know there is a cosmetic URL redirect in front of a
    local deployment of a Prometheus server, and all redirects are safe,
    this is the class to use to handle redirects in that case.

    The standard HTTPRedirectHandler does not forward request data nor
    does it allow redirected PUT requests (which Prometheus uses for some
    operations, for example `push_to_gateway`) because these cannot
    generically guarantee no violations of HTTP RFC 2616 requirements for
    the user to explicitly confirm redirects that could have unexpected
    side effects (such as rendering a PUT request non-idempotent or
    creating multiple resources not named in the original request).
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        """
        Apply redirect logic to a request.

        See parent HTTPRedirectHandler.redirect_request for parameter info.

        If the redirect is disallowed, this raises the corresponding HTTP error.
        If the redirect can't be determined, return None to allow other handlers
        to try. If the redirect is allowed, return the new request.

        This method specialized for the case when (a) the user knows that the
        redirect will not cause unacceptable side effects for any request method,
        and (b) the user knows that any request data should be passed through to
        the redirect. If either condition is not met, this should not be used.
        """
        # note that requests being provided by a handler will use get_method to
        # indicate the method, by monkeypatching this, instead of setting the
        # Request object's method attribute.
        m = getattr(req, "method", req.get_method())
        if not (code in (301, 302, 303, 307) and m in ("GET", "HEAD")
                or code in (301, 302, 303) and m in ("POST", "PUT")):
            raise HTTPError(req.full_url, code, msg, headers, fp)
        new_request = Request(
            newurl.replace(' ', '%20'),  # space escaping in new url if needed.
            headers=req.headers,
            origin_req_host=req.origin_req_host,
            unverifiable=True,
            data=req.data,
        )
        if PYTHON27_OR_OLDER:
            # the `method` attribute did not exist for Request in Python 2.7.
            new_request.get_method = lambda: m
        else:
            new_request.method = m
        return new_request
