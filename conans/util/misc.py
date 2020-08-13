import six

try:
    from collections.abc import Iterable
except ImportError:  # FIXME: Remove if Python2 support is removed
    from collections import Iterable


def make_tuple(value):
    """ Converts the value into a tuple if the value is an iterable with the following exceptions:
        * a `None` value will return `None`
        * a string value will return a tuple with the string as the unique member
    """
    if value is None:
        return None

    if isinstance(value, six.string_types):
        return value,

    if isinstance(value, Iterable):
        return tuple(value)
    else:
        return value,
