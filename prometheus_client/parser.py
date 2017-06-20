#!/usr/bin/python

from __future__ import unicode_literals

try:
    import StringIO
except ImportError:
    # Python 3
    import io as StringIO

from . import core


def text_string_to_metric_families(text):
    """Parse Prometheus text format from a unicode string.

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
    labels = {}

    state = 'name'

    for char in text:
        if state == 'name':
            if char == '{':
                state = 'startoflabelname'
            elif char == ' ' or char == '\t':
                state = 'endofname'
            else:
                name.append(char)
        elif state == 'endofname':
            if char == ' ' or char == '\t':
                pass
            elif char == '{':
                state = 'startoflabelname'
            else:
                value.append(char)
                state = 'value'
        elif state == 'startoflabelname':
            if char == ' ' or char == '\t' or char == ',':
                pass
            elif char == '}':
                state = 'endoflabels'
            else:
                state = 'labelname'
                labelname.append(char)
        elif state == 'labelname':
            if char == '=':
                state = 'labelvaluequote'
            elif char == ' ' or char == '\t':
                state = 'labelvalueequals'
            else:
                labelname.append(char)
        elif state == 'labelvalueequals':
            if char == '=':
                state = 'labelvaluequote'
            elif char == ' ' or char == '\t':
                pass
            else:
                raise ValueError("Invalid line: " + text)
        elif state == 'labelvaluequote':
            if char == '"':
                state = 'labelvalue'
            elif char == ' ' or char == '\t':
                pass
            else:
                raise ValueError("Invalid line: " + text)
        elif state == 'labelvalue':
            if char == '\\':
                state = 'labelvalueslash'
            elif char == '"':
                labels[''.join(labelname)] = ''.join(labelvalue)
                labelname = []
                labelvalue = []
                state = 'nextlabel'
            else:
                labelvalue.append(char)
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
        elif state == 'nextlabel':
            if char == ',':
                state = 'startoflabelname'
            elif char == '}':
                state = 'endoflabels'
            elif char == ' ' or char == '\t':
                pass
            else:
                raise ValueError("Invalid line: " + text)
        elif state == 'endoflabels':
            if char == ' ' or char == '\t':
                pass
            else:
                value.append(char)
                state = 'value'
        elif state == 'value':
            if char == ' ' or char == '\t':
                # Timestamps are not supported, halt
                break
            else:
                value.append(char)
    return (''.join(name), labels, float(''.join(value)))
    

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
    samples = []
    allowed_names = []

    def build_metric(name, documentation, typ, samples):
        metric = core.Metric(name, documentation, typ)
        metric.samples = samples
        return metric

    for line in fd:
        line = line.strip()

        if line.startswith('#'):
            parts = line.split(None, 3)
            if len(parts) < 2:
                continue
            if parts[1] == 'HELP':
                if parts[2] != name:
                    if name != '':
                        yield build_metric(name, documentation, typ, samples)
                    # New metric
                    name = parts[2]
                    typ = 'untyped'
                    samples = []
                    allowed_names = [parts[2]]
                if len(parts) == 4:
                  documentation = _unescape_help(parts[3])
                else:
                  documentation = ''
            elif parts[1] == 'TYPE':
                if parts[2] != name:
                    if name != '':
                        yield build_metric(name, documentation, typ, samples)
                    # New metric
                    name = parts[2]
                    documentation = ''
                    samples = []
                typ = parts[3]
                allowed_names = {
                    'counter': [''],
                    'gauge': [''],
                    'summary': ['_count', '_sum', ''],
                    'histogram': ['_count', '_sum', '_bucket'],
                    }.get(typ, [''])
                allowed_names = [name + n for n in allowed_names]
            else:
                # Ignore other comment tokens
                pass
        elif line == '':
            # Ignore blank lines
            pass
        else:
            sample = _parse_sample(line)
            if sample[0] not in allowed_names:
                  if name != '':
                      yield build_metric(name, documentation, typ, samples)
                  # New metric, yield immediately as untyped singleton
                  name = ''
                  documentation = ''
                  typ = 'untyped'
                  samples = []
                  allowed_names = []
                  yield build_metric(sample[0], documentation, typ, [sample])
            else:
              samples.append(sample)

    if name != '':
        yield build_metric(name, documentation, typ, samples)
