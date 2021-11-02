from collections.abc import Iterable


def make_tuple(value):
    """ Converts the value into a tuple if the value is an iterable with the following exceptions:
        * a `None` value will return `None`
        * a string value will return a tuple with the string as the unique member
    """
    if value is None:
        return None

    if isinstance(value, str):
        return value,

    if isinstance(value, Iterable):
        return tuple(value)
    else:
        return value,
