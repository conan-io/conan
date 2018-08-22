import json

import time

from conans.errors import ConanException


class RevisionList(object):

    def __init__(self):
        self._data = []

    @staticmethod
    def loads(contents):
        ret = RevisionList()
        ret._data = json.loads(contents)["revisions"]
        return ret

    def dumps(self):
        return json.dumps({"revisions": self._data})

    def add_revision(self, revision_id):
        if self.latest_revision() == revision_id:
            # Each uploaded file calls to update the revision
            return
        if self._find_revision_index(revision_id) is not None:
            raise ConanException("Revision already exists: %s" % revision_id)
        now = time.time()
        self._data.append({"id": revision_id, "time": now})

    def latest_revision(self):
        if not self._data:
            return None
        return self._data[-1]["id"]

    def remove_revision(self, revision_id):
        index = self._find_revision_index(revision_id)
        if index is None:
            return
        self._data.pop(index)

    def _find_revision_index(self, revision_id):
        for i, rev in enumerate(self._data):
            if rev["id"] == revision_id:
                return i
        return None



