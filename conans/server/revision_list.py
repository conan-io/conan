import json
import time
from collections import namedtuple

from conans.util.dates import from_timestamp_to_iso8601, valid_iso8601

_RevisionEntry = namedtuple("RevisionEntry", "revision time")


class RevisionList(object):

    def __init__(self):
        self._data = []

    @staticmethod
    def loads(contents):
        ret = RevisionList()
        ret._data = [_RevisionEntry(e["revision"], RevisionList._fix_timestamp(e["time"]))
                     for e in json.loads(contents)["revisions"]]
        return ret

    @staticmethod
    def _fix_timestamp(the_time):
        """The time field has been converted to ISO8601 from timestamp, so we keep compatibility
        by knowing how to read a file with timestamps.
        FIXME: This function could be removed in Conan 2.0"""

        if not isinstance(the_time, float):
            return the_time
        else:
            return from_timestamp_to_iso8601(the_time)

    def dumps(self):
        return json.dumps({"revisions": [{"revision": e.revision,
                                          "time": e.time} for e in self._data]})

    def add_revision(self, revision_id):
        lt = self.latest_revision()
        if lt and lt.revision == revision_id:
            # Each uploaded file calls to update the revision
            return
        index = self._find_revision_index(revision_id)
        if index:
            self._data.pop(index)

        self._data.append(_RevisionEntry(revision_id, self._now()))

    @staticmethod
    def _now():
        return from_timestamp_to_iso8601(time.time())

    def latest_revision(self):
        if not self._data:
            return None
        return self._data[-1]

    def get_time(self, revision):
        tmp = self._find_revision_index(revision)
        if tmp is None:
            return None
        return self._data[tmp].time

    def as_list(self):
        return list(reversed(self._data))

    def remove_revision(self, revision_id):
        index = self._find_revision_index(revision_id)
        if index is None:
            return
        self._data.pop(index)

    def _find_revision_index(self, revision_id):
        for i, rev in enumerate(self._data):
            if rev.revision == revision_id:
                return i
        return None

    def __eq__(self, other):
        return self.dumps() == other.dumps()
