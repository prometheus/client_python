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
        output.append('# HELP {0} {1}'.format(
            mname, metric.documentation.replace('\\', r'\\').replace('\n', r'\n').replace('"', r'\"')))
        output.append('\n# TYPE {0} {1}\n'.format(mname, metric.type))
        for name, labels, value in metric.samples:
            if labels:
                labelstr = '{{{0}}}'.format(','.join(
                    ['{0}="{1}"'.format(
                     k, v.replace('\\', r'\\').replace('\n', r'\n').replace('"', r'\"'))
                     for k, v in sorted(labels.items())]))
            else:
                labelstr = ''
            output.append('{0}{1} {2}\n'.format(name, labelstr, core._floatToGoString(value)))
    output.append('# EOF\n')
    return ''.join(output).encode('utf-8')

