#!/usr/bin/python

from __future__ import unicode_literals

import re

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


ESCAPE_SEQUENCES = {
    '\\\\': '\\',
    '\\n': '\n',
    '\\"': '"',
}


def replace_escape_sequence(match):
    return ESCAPE_SEQUENCES[match.group(0)]


HELP_ESCAPING_RE = re.compile(r'\\[\\n]')
ESCAPING_RE = re.compile(r'\\[\\n"]')


def _replace_help_escaping(s):
    return HELP_ESCAPING_RE.sub(replace_escape_sequence, s)


def _replace_escaping(s):
    return ESCAPING_RE.sub(replace_escape_sequence, s)


LABEL_AND_VALUE_RE = re.compile(
    r"""
    \s*                  # - skip initial whitespace
    ([^=\s]+)            # - label name
    \s*=\s*              # - equal sign ignoring all whitespace around it
    "(                   # - open label value
    [^"\\]*              # - match any number of non-special characters
    (?:(\\.)+[^"\\]*)*   # - match 1+ slash-escaped chars followed by any
                         #   number of non-special chars
    )"                   # - close label value
    \s*                  # - skip whitespace
    (?:,|$)              # - end on a comma or end of string
    """,
    re.VERBOSE,
)


def _parse_labels(labels_string):
    labels = {}
    # Return if we don't have valid labels
    pos = 0
    labels_string_len = len(labels_string)
    while pos < labels_string_len:
        m = LABEL_AND_VALUE_RE.match(labels_string, pos=pos)
        try:
            label_name, label_value, escaped_chars = m.groups()
        except AttributeError:
            if m is None:
                remaining = labels_string[pos:].strip()
                # One trailing comma is consumed by LABEL_AND_VALUE_RE, so the
                # remaining string should always be whitespace-only unless there
                # were no matches.
                comma_is_allowed = pos == 0
                if not remaining or (comma_is_allowed and remaining == ','):
                    return labels
                raise ValueError("Invalid labels: %s" % labels_string)
        if escaped_chars is not None:
            label_value = _replace_escaping(label_value)
        labels[label_name] = label_value
        pos = m.end()
    return labels


SAMPLE_RE = re.compile("""
\s*                # skip initial whitespace
([^{\s]+)          # metric name: all chars except braces and spaces
(?:\s*{(.*)})?     # optional labels with optional whitespace in front
\s+(\S+)           # value
""", re.VERBOSE)


def _parse_sample(text, match=SAMPLE_RE.match):
    m = match(text)
    if m is None:
        raise ValueError('Invalid sample string: %s' % text)
    name, labels, value = m.groups()
    parsed_labels = _parse_labels(labels) if labels is not None else {}
    return name, parsed_labels, float(value)


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
                    documentation = _replace_help_escaping(parts[3])
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
