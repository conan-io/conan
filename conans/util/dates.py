import datetime
import re


def from_timestamp_to_iso8601(timestamp):
    return "%sZ" % datetime.datetime.utcfromtimestamp(int(timestamp)).isoformat()


def from_iso8601_to_datetime(iso_str):
    return datetime.datetime.strptime(iso_str, '%Y-%m-%dT%H:%M:%SZ')


def iso8601_to_str(iso_str):
    dt = from_iso8601_to_datetime(iso_str)
    return dt.strftime('%Y-%m-%d %H:%M:%S UTC')


def valid_iso8601(the_date):
    regex = r'^(-?(?:[1-9][0-9]*)?[0-9]{4})-(1[0-2]|0[1-9])-(3[01]|0[1-9]|[12][0-9])T' \
            r'(2[0-3]|[01][0-9]):([0-5][0-9]):([0-5][0-9])(\.[0-9]+)?(Z|[+-]' \
            r'(?:2[0-3]|[01][0-9]):' \
            r'[0-5][0-9])?$'
    match_iso8601 = re.compile(regex).match
    return match_iso8601(the_date) is not None
