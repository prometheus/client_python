#!/usr/bin/env python


from ..utils import floatToGoString
from ..validation import (
    _is_valid_legacy_labelname, _is_valid_legacy_metric_name,
)

CONTENT_TYPE_LATEST = 'application/openmetrics-text; version=1.0.0; charset=utf-8'
"""Content type of the latest OpenMetrics text format"""


def _is_valid_exemplar_metric(metric, sample):
    if metric.type == 'counter' and sample.name.endswith('_total'):
        return True
    if metric.type in ('gaugehistogram') and sample.name.endswith('_bucket'):
        return True
    if metric.type in ('histogram') and sample.name.endswith('_bucket') or sample.name == metric.name:
        return True
    return False


def generate_latest(registry):
    '''Returns the metrics from the registry in latest text format as a string.'''
    output = []
    for metric in registry.collect():
        try:
            mname = metric.name
            # (Vesari): TODO: this is wrong. TYPE should come before HELP!!!!
            output.append('# HELP {} {}\n'.format(
                escape_metric_name(mname), _escape(metric.documentation)))
            output.append(f'# TYPE {escape_metric_name(mname)} {metric.type}\n')
            if metric.unit:
                output.append(f'# UNIT {escape_metric_name(mname)} {metric.unit}\n')
            for s in metric.samples:
                if not _is_valid_legacy_metric_name(s.name):
                    labelstr = escape_metric_name(s.name)
                    if s.labels:
                        labelstr += ', '
                else:
                    labelstr = ''
                
                if s.labels:
                    items = sorted(s.labels.items())
                    labelstr += ','.join(
                        ['{}="{}"'.format(
                            escape_label_name(k), _escape(v))
                            for k, v in items])
                if labelstr:
                    labelstr = "{" + labelstr + "}"
                    
                if s.exemplar:
                    if not _is_valid_exemplar_metric(metric, s):
                        raise ValueError(f"Metric {metric.name} has exemplars, but is not a histogram bucket or counter")
                    labels = '{{{0}}}'.format(','.join(
                        ['{}="{}"'.format(
                            k, v.replace('\\', r'\\').replace('\n', r'\n').replace('"', r'\"'))
                            for k, v in sorted(s.exemplar.labels.items())]))
                    if s.exemplar.timestamp is not None:
                        exemplarstr = ' # {} {} {}'.format(
                            labels,
                            floatToGoString(s.exemplar.value),
                            s.exemplar.timestamp,
                        )
                    else:
                        exemplarstr = ' # {} {}'.format(
                            labels,
                            floatToGoString(s.exemplar.value),
                        )
                else:
                    exemplarstr = ''   
                
                timestamp = ''
                if s.timestamp is not None:
                    timestamp = f' {s.timestamp}'

                native_histogram = ''
                positive_spans = ''
                positive_deltas = ''
                negative_spans = ''
                negative_deltas = ''
                pos = False
                neg = False      
                if s.native_histogram:
                    if s.name is not metric.name:
                        raise ValueError(f"Metric {metric.name} is native histogram, but sample name is not valid")                 
                    # Initialize basic nh template
                    nh_sample_template = '{{count:{},sum:{},schema:{},zero_threshold:{},zero_count:{}'

                    args = [
                        s.native_histogram.count_value,
                        s.native_histogram.sum_value,
                        s.native_histogram.schema,
                        s.native_histogram.zero_threshold,
                        s.native_histogram.zero_count,
                    ]

                    # Signal presence for pos/neg spans/deltas
                    pos = False
                    neg = False

                    # If there are pos spans, append them to the template and args
                    if s.native_histogram.pos_spans:
                        positive_spans = ','.join([f'{ps[0]}:{ps[1]}' for ps in s.native_histogram.pos_spans])
                        positive_deltas = ','.join(f'{pd}' for pd in s.native_histogram.pos_deltas)
                        nh_sample_template += ',positive_spans:[{}]'
                        args.append(positive_spans)
                        pos = True

                    # If there are neg spans exist, append them to the template and args
                    if s.native_histogram.neg_spans:
                        negative_spans = ','.join([f'{ns[0]}:{ns[1]}' for ns in s.native_histogram.neg_spans])
                        negative_deltas = ','.join(str(nd) for nd in s.native_histogram.neg_deltas)
                        nh_sample_template += ',negative_spans:[{}]'
                        args.append(negative_spans)
                        neg = True

                    # Append pos deltas if pos spans were added
                    if pos:
                        nh_sample_template += ',positive_deltas:[{}]'
                        args.append(positive_deltas)

                    # Append neg deltas if neg spans were added
                    if neg:
                        nh_sample_template += ',negative_deltas:[{}]'
                        args.append(negative_deltas)

                    # Add closing brace
                    nh_sample_template += '}}'

                    # Format the template with the args
                    native_histogram = nh_sample_template.format(*args)

                print("These are the pos deltas", positive_deltas) #DEBUGGING LINE       
                print("The is the nh", native_histogram) #DEBUGGING LINE
                value = ''    
                if s.value is not None or not s.native_histogram:
                    value = floatToGoString(s.value)       
                if _is_valid_legacy_metric_name(s.name):
                    output.append('{}{} {}{}{}{}\n'.format(
                        s.name,
                        labelstr,
                        value,
                        timestamp,
                        exemplarstr,
                        native_histogram
                    ))

                else:
                    output.append('{} {}{}{}{}\n'.format(
                        labelstr,
                        value,
                        timestamp,
                        exemplarstr,
                        native_histogram
                    ))
        except Exception as exception:
            exception.args = (exception.args or ('',)) + (metric,)
            raise

    output.append('# EOF\n')
    return ''.join(output).encode('utf-8')


def escape_metric_name(s: str) -> str:
    """Escapes the metric name and puts it in quotes iff the name does not
    conform to the legacy Prometheus character set.
    """
    if _is_valid_legacy_metric_name(s):
        return s
    return '"{}"'.format(_escape(s))


def escape_label_name(s: str) -> str:
    """Escapes the label name and puts it in quotes iff the name does not
    conform to the legacy Prometheus character set.
    """
    if _is_valid_legacy_labelname(s):
        return s
    return '"{}"'.format(_escape(s))


def _escape(s: str) -> str:
    """Performs backslash escaping on backslash, newline, and double-quote characters."""
    return s.replace('\\', r'\\').replace('\n', r'\n').replace('"', r'\"')
