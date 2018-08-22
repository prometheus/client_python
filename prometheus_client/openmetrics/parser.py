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


def _parse_sample(text):
    name = []
    labelname = []
    labelvalue = []
    value = []
    timestamp = []
    labels = {}

    state = 'name'

    for char in text:
        if state == 'name':
            if char == '{':
                state = 'startoflabelname'
            elif char == ' ':
                state = 'value'
            else:
                name.append(char)
        elif state == 'startoflabelname':
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
                state = 'value'
            else:
                raise ValueError("Invalid line: " + text)
        elif state == 'value':
            if char == ' ':
                state = 'timestamp'
            else:
                value.append(char)
        elif state == 'timestamp':
            if char == ' ':
                # examplars are not supported, halt
                break
            else:
                timestamp.append(char)

    # Trailing space after value.
    if state == 'timestamp' and not timestamp:
        raise ValueError("Invalid line: " + text)

    if not value:
        raise ValueError("Invalid line: " + text)
    value = ''.join(value)
    val = None
    try:
        val = int(value)
    except ValueError:
        val = float(value)

    ts = None
    timestamp = ''.join(timestamp)
    if timestamp:
        try:
            # Simple int.
            ts = core.Timestamp(int(timestamp), 0)
        except ValueError:
            try:
                # aaaa.bbbb. Nanosecond resolution supported.
                parts = timestamp.split('.', 1)
                ts = core.Timestamp(int(parts[0]), int(parts[1][:9].ljust(9, "0")))
            except ValueError:
                # Float.
                ts = float(timestamp)

    return core.Sample(''.join(name), labels, val, ts)
    

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
        metric = core.Metric(name, documentation, typ, unit)
        # TODO: check labelvalues are valid utf8
        # TODO: check only histogram buckets have exemplars.
        # TODO: Info and stateset can't have units
        # TODO: check samples are appropriately grouped and ordered
        # TODO: check for metadata in middle of samples
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
            if parts[1] == 'HELP':
                if parts[2] != name:
                    if name != '':
                        yield build_metric(name, documentation, typ, unit, samples)
                    # New metric
                    name = parts[2]
                    unit = ''
                    typ = 'untyped'
                    samples = []
                    allowed_names = [parts[2]]
                if len(parts) == 4:
                    documentation = _unescape_help(parts[3])
                elif len(parts) == 3:
                    raise ValueError("Invalid line: " + line)
            elif parts[1] == 'TYPE':
                if parts[2] != name:
                    if name != '':
                        yield build_metric(name, documentation, typ, unit, samples)
                    # New metric
                    name = parts[2]
                    documentation = ''
                    unit = ''
                    samples = []
                typ = parts[3]
                allowed_names = {
                    'counter': ['_total', '_created'],
                    'summary': ['_count', '_sum', '', '_created'],
                    'histogram': ['_count', '_sum', '_bucket', 'created'],
                    'gaugehistogram': ['_bucket'],
                }.get(typ, [''])
                allowed_names = [name + n for n in allowed_names]
            elif parts[1] == 'UNIT':
                if parts[2] != name:
                    if name != '':
                        yield build_metric(name, documentation, typ, unit, samples)
                    # New metric
                    name = parts[2]
                    typ = 'untyped'
                    samples = []
                    allowed_names = [parts[2]]
                unit = parts[3]
            else:
                raise ValueError("Invalid line: " + line)
        else:
            sample = _parse_sample(line)
            if sample[0] not in allowed_names:
                if name != '':
                    yield build_metric(name, documentation, typ, unit, samples)
                # Start an untyped metric.
                name = sample[0]
                documentation = ''
                unit = ''
                typ = 'untyped'
                samples = [sample]
                allowed_names = [sample[0]]
            else:
                samples.append(sample)

    if name != '':
        yield build_metric(name, documentation, typ, unit, samples)

    if not eof:
        raise ValueError("Missing # EOF at end")
