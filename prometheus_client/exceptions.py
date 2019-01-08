

class MetricErrorBase(BaseException):

    def __init__(self, metric, *args):
        self.metric = metric
        super(MetricErrorBase, self).__init__(*args)


class MetricTypeError(MetricErrorBase, TypeError):
    pass


class MetricValueError(MetricErrorBase, ValueError):
    pass


class MetricAttributeError(MetricErrorBase, AttributeError):
    pass


Exceptions = {
    TypeError: MetricTypeError,
    ValueError: MetricValueError,
    AttributeError: MetricAttributeError,
}


def from_exception(metric, exception):
    # Fetch the exception class from the dictionary
    type_ = Exceptions[type(exception)]
    # Init the exception and add the metric
    instance = type_(*exception.args)
    instance.metric = metric
    return instance
