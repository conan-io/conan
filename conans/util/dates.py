import calendar
import datetime
import re
import time

from dateutil import parser

from conans.errors import ConanException


def from_timestamp_to_iso8601(timestamp):
    return "%sZ" % datetime.datetime.utcfromtimestamp(int(timestamp)).isoformat()


def from_iso8601_to_datetime(iso_str):
    return parser.isoparse(iso_str)


def iso8601_to_str(iso_str):
    dt = from_iso8601_to_datetime(iso_str)
    return dt.strftime('%Y-%m-%d %H:%M:%S UTC')


def timestamp_now():
    # seconds since epoch 0, easy to store, in UTC
    return calendar.timegm(time.gmtime())


def timestamp_to_str(timestamp):
    return datetime.datetime.fromtimestamp(int(timestamp)).strftime('%Y-%m-%d %H:%M:%S UTC')


def timedelta_from_text(interval):
    match = re.search(r"(\d+)([mhd])", interval)
    try:
        value, unit = match.group(1), match.group(2)
        if unit == 'm':
            return datetime.timedelta(minutes=float(value))
        elif unit == 'h':
            return datetime.timedelta(hours=float(value))
        else:
            return datetime.timedelta(days=float(value))
    except Exception:
        raise ConanException("Incorrect time interval definition: %s" % interval)
