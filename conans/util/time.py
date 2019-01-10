import datetime


def from_timestamp_to_iso8601(timestamp):
    return "%sZ" % datetime.datetime.utcfromtimestamp(int(timestamp)).isoformat()


def from_iso8601_to_datetime(iso_str):
    return datetime.datetime.strptime(iso_str, '%Y-%m-%dT%H:%M:%SZ')


def datetime_to_str(dt):
    return dt.strftime('%Y-%m-%d %H:%M:%S UTC')
