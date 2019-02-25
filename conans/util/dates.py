import datetime
import re


def from_timestamp_to_iso8601(timestamp):
    return "%sZ" % datetime.datetime.utcfromtimestamp(int(timestamp)).isoformat()


def from_iso8601_to_datetime(iso_str):

    def transform_to_z_notation(the_str):
        for p in ("+00:00", "+0000", "+00"):
            if the_str.endswith(p):
                the_str = the_str[0:-len(p)]
                return "{}Z".format(the_str)
        return the_str

    base_pattern = "%Y-%m-%dT%H:%M:%S"
    if "." in iso_str:
        pattern = "{}.%fZ".format(base_pattern)
    else:
        pattern = '{}Z'.format(base_pattern)

    iso_str = transform_to_z_notation(iso_str)
    if not iso_str.endswith("Z"):
        iso_str += "Z"
    return datetime.datetime.strptime(iso_str, pattern)


def iso8601_to_str(iso_str):
    dt = from_iso8601_to_datetime(iso_str)
    return dt.strftime('%Y-%m-%d %H:%M:%S UTC')


def valid_iso8601(the_date):
    regex = r'^(-?(?:[1-9][0-9]*)?[0-9]{4})-(1[0-2]|0[1-9])-(3[01]|0[1-9]|[12][0-9])T' \
            r'(2[0-3]|[01][0-9]):([0-5][0-9]):([0-5][0-9])(\.[0-9]+)?(Z|[+-]' \
            r'(?:2[0-3]|[01][0-9]):' \
            r'[0-5][0-9])?$'
    return re.match(regex, the_date)
