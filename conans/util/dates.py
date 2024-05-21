import calendar
import datetime
import time

from dateutil import parser

from conans.errors import ConanException


def from_timestamp_to_iso8601(timestamp):
    # Used exclusively by conan_server to return the date in iso format (same as artifactory)
    return "%s" % datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc).isoformat()


def _from_iso8601_to_datetime(iso_str):
    return parser.isoparse(iso_str)


def from_iso8601_to_timestamp(iso_str):
    # used by RestClient v2 to transform from HTTP API (iso) to Conan internal timestamp
    datetime_time = _from_iso8601_to_datetime(iso_str)
    return datetime_time.timestamp()


def timestamp_now():
    # seconds since epoch 0, easy to store, in UTC
    return calendar.timegm(time.gmtime())


def revision_timestamp_now():
    return time.time()


def timestamp_to_str(timestamp):
    # used by ref.repr_humantime() to print human readable time
    assert timestamp is not None
    return datetime.datetime.fromtimestamp(int(timestamp), datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')


def timelimit(expression):
    """ convert an expression like "2d" (2 days) or "3h" (3 hours) to a timestamp in the past
    with respect to current time
    """
    time_value = expression[:-1]
    try:
        time_value = int(time_value)
    except TypeError:
        raise ConanException(f"Time value '{time_value}' must be an integer")
    time_units = expression[-1]
    units = {"y": 365 * 24 * 60 * 60,
             "M": 30 * 24 * 60 * 60,
             "w": 7 * 24 * 60 * 60,
             "d": 24 * 60 * 60,
             "h": 60 * 60,
             "m": 60,
             "s": 1}
    try:
        lru_value = time_value * units[time_units]
    except KeyError:
        raise ConanException(f"Unrecognized time unit: '{time_units}'. Use: {list(units)}")

    limit = timestamp_now() - lru_value
    return limit
