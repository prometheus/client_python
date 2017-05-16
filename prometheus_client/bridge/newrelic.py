from __future__ import absolute_import

import newrelic.agent

from .. import core


@newrelic.agent.data_source_factory(name='Prometheus')
class PrometheusDataSource(object):
    def __init__(self, settings, environ):
        self.registry = settings.get('registry', core.REGISTRY)
        self.prefix = settings.get('prefix', '')

    def __call__(self):
        prefixstr = ''
        if self.prefix:
            prefixstr = self.prefix + '.'

        for metric in self.registry.collect():
            for name, labels, value in metric.samples:
                if labels:
                    labelstr = '.' + '.'.join(['{0}.{1}'.format(k, v) for k, v in sorted(labels.items())])
                else:
                    labelstr = ''

                metric_name = 'Custom/{0}{1}{2}'.format(prefixstr, name, labelstr)
                yield (metric_name, value)
