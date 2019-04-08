from math import floor

import time
import unittest

from conans.server.revision_list import RevisionList
from conans.util.dates import from_timestamp_to_iso8601


class RevisionListTest(unittest.TestCase):

    def test_remove_latest(self):
        rev = RevisionList()
        rev.add_revision("rev1")
        rev.add_revision("rev2")

        dumped = rev.dumps()
        loaded = RevisionList.loads(dumped)
        self.assertEqual(rev, loaded)
        self.assertEqual(loaded.latest_revision().revision, "rev2")

        loaded.remove_revision("rev2")
        self.assertEqual(loaded.latest_revision().revision, "rev1")

    def test_remove_non_latest(self):
        rev = RevisionList()
        rev.add_revision("rev1")
        rev.add_revision("rev2")

        dumped = rev.dumps()
        loaded = RevisionList.loads(dumped)
        loaded.remove_revision("rev1")
        self.assertEqual(loaded.latest_revision().revision, "rev2")

    def test_compatibility_with_timestamps(self):
        the_time = float(floor(time.time()))
        iso = from_timestamp_to_iso8601(the_time)
        old_contents = '{"revisions": [{"revision": "rev1", "time": %s}, ' \
                       '{"revision": "rev2", "time": "%s"}]}' % (the_time, the_time)
        r_list = RevisionList.loads(old_contents)
        when = r_list.get_time("rev1")
        self.assertEqual(when, iso)
