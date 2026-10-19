import calendar
import datetime
import sys
import time

# https://docs.python.org/3.11/whatsnew/3.11.html#datetime
if sys.version_info < (3, 11):
    from dateutil import parser


    def _from_iso8601_to_datetime(iso_str):
        return parser.isoparse(iso_str)
else:
    def _from_iso8601_to_datetime(iso_str):
        return datetime.datetime.fromisoformat(iso_str)


def from_timestamp_to_iso8601(timestamp):
    # Used exclusively by conan_server to return the date in iso format (same as artifactory)
    return "%s" % datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc).isoformat()


def from_iso8601_to_timestamp(iso_str):
    # used by RestClient v2 to transform from HTTP API (iso) to Conan internal timestamp
    datetime_time = _from_iso8601_to_datetime(iso_str)
    return datetime_time.timestamp()


def timestamp_now():
    # seconds since epoch 0, easy to store, in UTC
    # Used in Manifest timestamp, in packagesDB LRU and in timestamp of backup-sources json
    return calendar.timegm(time.gmtime())


def revision_timestamp_now():
    return time.time()


def timestamp_to_str(timestamp):
    # used by ref.repr_humantime() to print human readable time
    assert timestamp is not None
    return datetime.datetime.fromtimestamp(int(timestamp), datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
