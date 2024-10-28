import os
import re

METRIC_NAME_RE = re.compile(r'^[a-zA-Z_:][a-zA-Z0-9_:]*$')
METRIC_LABEL_NAME_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
RESERVED_METRIC_LABEL_NAME_RE = re.compile(r'^__.*$')


def _init_legacy_validation() -> bool:
    """Retrieve name validation setting from environment."""
    return os.environ.get("PROMETHEUS_LEGACY_NAME_VALIDATION", 'False').lower() in ('true', '1', 't')


_legacy_validation = _init_legacy_validation()


def get_legacy_validation() -> bool:
    global _legacy_validation
    return _legacy_validation


def disable_legacy_validation():
    """Disable legacy name validation, instead allowing all UTF8 characters."""
    global _legacy_validation
    _legacy_validation = False


def enable_legacy_validation():
    """Enable legacy name validation instead of allowing all UTF8 characters."""
    global _legacy_validation
    _legacy_validation = True


def validate_metric_name(name: str) -> bool:
    if not name:
        return False
    global _legacy_validation
    if _legacy_validation:
        return METRIC_NAME_RE.match(name)
    try:
        name.encode('utf-8')
        return True
    except UnicodeDecodeError:
        return False
       

def validate_metric_name_token(tok: str) -> bool:
    """Check validity of a parsed metric name token. UTF-8 names must be quoted."""
    if not tok:
        return False
    global _legacy_validation
    quoted = tok[0] == '"' and tok[-1] == '"'
    if not quoted or _legacy_validation:
        return METRIC_NAME_RE.match(tok)
    try:
        tok.encode('utf-8')
        return True
    except UnicodeDecodeError:
        return False 


def validate_metric_label_name_token(tok: str) -> bool:
    """Check validity of a parsed label name token. UTF-8 names must be quoted."""
    if not tok:
        return False
    global _legacy_validation
    quoted = tok[0] == '"' and tok[-1] == '"'
    if not quoted or _legacy_validation:
        return METRIC_LABEL_NAME_RE.match(tok)
    try:
        tok.encode('utf-8')
        return True
    except UnicodeDecodeError:
        return False


def validate_labelname(l):
    if get_legacy_validation():
        if not METRIC_LABEL_NAME_RE.match(l):
            raise ValueError('Invalid label metric name: ' + l)
        if RESERVED_METRIC_LABEL_NAME_RE.match(l):
            raise ValueError('Reserved label metric name: ' + l)
    else:
        try:
            l.encode('utf-8')
        except UnicodeDecodeError:
            raise ValueError('Invalid label metric name: ' + l)
        if RESERVED_METRIC_LABEL_NAME_RE.match(l):
            raise ValueError('Reserved label metric name: ' + l)


def validate_labelnames(cls, labelnames):
    labelnames = tuple(labelnames)
    for l in labelnames:
        validate_labelname(l)
        if l in cls._reserved_labelnames:
            raise ValueError('Reserved label metric name: ' + l)
    return labelnames


def validate_exemplar(exemplar):
    runes = 0
    for k, v in exemplar.items():
        validate_labelname(k)
        runes += len(k)
        runes += len(v)
    if runes > 128:
        raise ValueError('Exemplar labels have %d UTF-8 characters, exceeding the limit of 128')
