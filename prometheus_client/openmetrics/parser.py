#!/usr/bin/python

from __future__ import unicode_literals

try:
    import StringIO
except ImportError:
    # Python 3
    import io as StringIO

from .. import core


def text_string_to_metric_families(text):
    """Parse Openmetrics text format from a unicode string.

    See text_fd_to_metric_families.
    """
    for metric_family in text_fd_to_metric_families(StringIO.StringIO(text)):
        yield metric_family


def _unescape_help(text):
    result = []
    slash = False

    for char in text:
        if slash:
            if char == '\\':
                result.append('\\')
            elif char == '"':
                result.append('"')
            elif char == 'n':
                result.append('\n')
            else:
                result.append('\\' + char)
            slash = False
        else:
            if char == '\\':
                slash = True
            else:
                result.append(char)

    if slash:
        result.append('\\')

    return ''.join(result)


def _parse_value(value):
    value = ''.join(value)
    if value != value.strip():
        raise ValueError("Invalid value: {0!r}".format(value))
    try:
        return int(value)
    except ValueError:
        return float(value)


def _parse_timestamp(timestamp):
    timestamp = ''.join(timestamp)
    if not timestamp:
        return None
    if timestamp != timestamp.strip():
        raise ValueError("Invalid timestamp: {0!r}".format(timestamp))
    try:
        # Simple int.
        return core.Timestamp(int(timestamp), 0)
    except ValueError:
        try:
            # aaaa.bbbb. Nanosecond resolution supported.
            parts = timestamp.split('.', 1)
            return core.Timestamp(int(parts[0]), int(parts[1][:9].ljust(9, "0")))
        except ValueError:
            # Float.
            return float(timestamp)


def _parse_labels(it, text):
    # The { has already been parsed.
    state  = 'startoflabelname'
    labelname = []
    labelvalue = []
    labels = {}

    for char in it:
        if state == 'startoflabelname':
            if char == '}':
                state = 'endoflabels'
            else:
                state = 'labelname'
                labelname.append(char)
        elif state == 'labelname':
            if char == '=':
                state = 'labelvaluequote'
            else:
                labelname.append(char)
        elif state == 'labelvaluequote':
            if char == '"':
                state = 'labelvalue'
            else:
                raise ValueError("Invalid line: " + text)
        elif state == 'labelvalue':
            if char == '\\':
                state = 'labelvalueslash'
            elif char == '"':
                if not core._METRIC_LABEL_NAME_RE.match(''.join(labelname)):
                    raise ValueError("Invalid line: " + text)
                labels[''.join(labelname)] = ''.join(labelvalue)
                labelname = []
                labelvalue = []
                state = 'endoflabelvalue'
            else:
                labelvalue.append(char)
        elif state == 'endoflabelvalue':
            if char == ',':
                state = 'labelname'
            elif char == '}':
                state = 'endoflabels'
            else:
                raise ValueError("Invalid line: " + text)
        elif state == 'labelvalueslash':
            state = 'labelvalue'
            if char == '\\':
                labelvalue.append('\\')
            elif char == 'n':
                labelvalue.append('\n')
            elif char == '"':
                labelvalue.append('"')
            else:
                labelvalue.append('\\' + char)
        elif state == 'endoflabels':
            if char == ' ':
                break
            else:
                raise ValueError("Invalid line: " + text)
    return labels


def _parse_sample(text):
    name = []
    value = []
    timestamp = []
    labels = {}
    exemplar_value = []
    exemplar_timestamp = []
    exemplar_labels = None

    state = 'name'

    it = iter(text)
    for char in it:
        if state == 'name':
            if char == '{':
                labels = _parse_labels(it, text)
                # Space has already been parsed.
                state = 'value'
            elif char == ' ':
                state = 'value'
            else:
                name.append(char)
        elif state == 'value':
            if char == ' ':
                state = 'timestamp'
            else:
                value.append(char)
        elif state == 'timestamp':
            if char == '#' and not timestamp:
                state = 'exemplarspace'
            elif char == ' ':
                state = 'exemplarhash'
            else:
                timestamp.append(char)
        elif state == 'exemplarhash':
            if char == '#':
                state = 'exemplarspace'
            else:
                raise ValueError("Invalid line: " + text)
        elif state == 'exemplarspace':
            if char == ' ':
                state = 'exemplarstartoflabels'
            else:
                raise ValueError("Invalid line: " + text)
        elif state == 'exemplarstartoflabels':
            if char == '{':
                exemplar_labels = _parse_labels(it, text)
                # Space has already been parsed.
                state = 'exemplarvalue'
            else:
                raise ValueError("Invalid line: " + text)
        elif state == 'exemplarvalue':
            if char == ' ':
                state = 'exemplartimestamp'
            else:
                exemplar_value.append(char)
        elif state == 'exemplartimestamp':
            exemplar_timestamp.append(char)

    # Trailing space after value.
    if state == 'timestamp' and not timestamp:
        raise ValueError("Invalid line: " + text)

    # Trailing space after value.
    if state == 'exemplartimestamp' and not exemplar_timestamp:
        raise ValueError("Invalid line: " + text)

    # Incomplete exemplar.
    if state in ['exemplarhash', 'exemplarspace', 'exemplarstartoflabels']:
        raise ValueError("Invalid line: " + text)

    if not value:
        raise ValueError("Invalid line: " + text)
    value = ''.join(value)
    val = _parse_value(value)
    ts = _parse_timestamp(timestamp)
    exemplar = None
    if exemplar_labels is not None:
        exemplar = core.Exemplar(exemplar_labels,
                _parse_value(exemplar_value),
                _parse_timestamp(exemplar_timestamp))

    return core.Sample(''.join(name), labels, val, ts, exemplar)
    

def text_fd_to_metric_families(fd):
    """Parse Prometheus text format from a file descriptor.

    This is a laxer parser than the main Go parser,
    so successful parsing does not imply that the parsed
    text meets the specification.

    Yields core.Metric's.
    """
    name = ''
    documentation = ''
    typ = 'untyped'
    unit = ''
    samples = []
    allowed_names = []
    eof = False

    seen_metrics = set()
    def build_metric(name, documentation, typ, unit, samples):
        if name in seen_metrics:
            raise ValueError("Duplicate metric: " + name)
        seen_metrics.add(name)
        if typ is None:
            typ = 'untyped'
        if documentation is None:
            documentation = ''
        if unit is None:
            unit = ''
        if unit and not name.endswith("_" + unit):
            raise ValueError("Unit does not match metric name: " + name)
        if unit and typ in ['info', 'stateset']:
            raise ValueError("Units not allowed for this metric type: " + name)
        metric = core.Metric(name, documentation, typ, unit)
        # TODO: check labelvalues are valid utf8
        # TODO: check samples are appropriately grouped and ordered
        # TODO: check info/stateset values are 1/0
        # TODO: Check histogram bucket rules being followed
        # TODO: Check for dupliate samples
        # TODO: Check for decresing timestamps
        metric.samples = samples
        return metric

    for line in fd:
        if line[-1] == '\n':
          line = line[:-1]

        if eof:
            raise ValueError("Received line after # EOF: " + line)

        if line == '# EOF':
            eof = True
        elif line.startswith('#'):
            parts = line.split(' ', 3)
            if len(parts) < 4:
                raise ValueError("Invalid line: " + line)
            if parts[2] == name and samples:
                raise ValueError("Received metadata after samples: " + line)
            if parts[2] != name:
                if name != '':
                    yield build_metric(name, documentation, typ, unit, samples)
                # New metric
                name = parts[2]
                unit = None
                typ = None
                documentation = None
                samples = []
                allowed_names = [parts[2]]

            if parts[1] == 'HELP':
                if documentation is not None:
                    raise ValueError("More than one HELP for metric: " + line)
                if len(parts) == 4:
                    documentation = _unescape_help(parts[3])
                elif len(parts) == 3:
                    raise ValueError("Invalid line: " + line)
            elif parts[1] == 'TYPE':
                if typ is not None:
                    raise ValueError("More than one TYPE for metric: " + line)
                typ = parts[3]
                allowed_names = {
                    'counter': ['_total', '_created'],
                    'summary': ['_count', '_sum', '', '_created'],
                    'histogram': ['_count', '_sum', '_bucket', 'created'],
                    'gaugehistogram': ['_gcount', '_gsum', '_bucket'],
                    'info': ['_info'],
                }.get(typ, [''])
                allowed_names = [name + n for n in allowed_names]
            elif parts[1] == 'UNIT':
                if unit is not None:
                    raise ValueError("More than one UNIT for metric: " + line)
                unit = parts[3]
            else:
                raise ValueError("Invalid line: " + line)
        else:
            sample = _parse_sample(line)
            if sample.name not in allowed_names:
                if name != '':
                    yield build_metric(name, documentation, typ, unit, samples)
                # Start an untyped metric.
                name = sample.name
                documentation = ''
                unit = ''
                typ = 'untyped'
                samples = [sample]
                allowed_names = [sample.name]
            else:
                samples.append(sample)
            if sample.exemplar and not (
                    typ in ['histogram', 'gaugehistogram']
                    and sample.name.endswith('_bucket')):
                raise ValueError("Invalid line only histogram/gaugehistogram buckets can have exemplars: " + line)

    if name != '':
        yield build_metric(name, documentation, typ, unit, samples)

    if not eof:
        raise ValueError("Missing # EOF at end")
