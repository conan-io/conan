import datetime
import unittest

from dateutil.tz import tzutc

from conans.util.dates import from_timestamp_to_iso8601, from_iso8601_to_datetime


class TimeTest(unittest.TestCase):

    def test_time_conversions(self):
        timestamp = "1547138099"
        iso = from_timestamp_to_iso8601(timestamp)
        self.assertEqual(iso, "2019-01-10T16:34:59Z")

        dt = from_iso8601_to_datetime(iso)
        expected = datetime.datetime(year=2019, month=1, day=10, hour=16, minute=34, second=59,
                                     tzinfo=tzutc())
        self.assertEqual(dt, expected)

        artifactory_ret = '2019-02-20T13:54:47.543+0000'
        dt = from_iso8601_to_datetime(artifactory_ret)
        expected = datetime.datetime(year=2019, month=2, day=20, hour=13, minute=54, second=47,
                                     microsecond=543000, tzinfo=tzutc())
        self.assertEqual(dt, expected)

        artifactory_ret = '2019-05-14T16:52:28.383+0100'
        dt = from_iso8601_to_datetime(artifactory_ret)  # UTC one hour less
        expected = datetime.datetime(year=2019, month=5, day=14, hour=15, minute=52, second=28,
                                     microsecond=383000, tzinfo=tzutc())
        self.assertEqual(dt, expected)
