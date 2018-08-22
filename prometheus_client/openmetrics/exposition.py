#!/usr/bin/python

from __future__ import unicode_literals

from .. import core

CONTENT_TYPE_LATEST = str('text/openmetrics; version=0.0.1; charset=utf-8')
'''Content type of the latest OpenMetrics text format'''

def generate_latest(registry):
    '''Returns the metrics from the registry in latest text format as a string.'''
    output = []
    for metric in registry.collect():
        mname = metric.name
        output.append('# HELP {0} {1}\n'.format(
            mname, metric.documentation.replace('\\', r'\\').replace('\n', r'\n').replace('"', r'\"')))
        output.append('# TYPE {0} {1}\n'.format(mname, metric.type))
        if metric.unit:
            output.append('# UNIT {0} {1}\n'.format(mname, metric.unit))
        for s in metric.samples:
            if s.labels:
                labelstr = '{{{0}}}'.format(','.join(
                    ['{0}="{1}"'.format(
                     k, v.replace('\\', r'\\').replace('\n', r'\n').replace('"', r'\"'))
                     for k, v in sorted(s.labels.items())]))
            else:
                labelstr = ''
            timestamp = ''
            if s.timestamp is not None:
                # Convert to milliseconds.
                timestamp = ' {0}'.format(s.timestamp)
            output.append('{0}{1} {2}{3}\n'.format(s.name, labelstr, core._floatToGoString(s.value), timestamp))
    output.append('# EOF\n')
    return ''.join(output).encode('utf-8')

