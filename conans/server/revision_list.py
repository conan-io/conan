import json

import time

from conans.errors import ConanException


class RevisionList(object):

    def __init__(self):
        self._data = {"revisions": list()}

    @staticmethod
    def loads(contents):
        ret = RevisionList()
        ret._data = json.loads(contents)
        return ret

    def dumps(self):
        return json.dumps(self._data)

    def add_revision(self, revision_id):
        if self.latest_revision() == revision_id:
            # Each uploaded file calls to update the revision
            return
        if self._find_revision_index(revision_id) is not None:
            raise ConanException("Revision already exists: %s" % revision_id)
        now = time.time()
        self._data["revisions"].append({"id": revision_id, "time": now})

    def latest_revision(self):
        if not self._data["revisions"]:
            return None
        return self._data["revisions"][-1]["id"]

    def remove_revision(self, revision_id):
        index = self._find_revision_index(revision_id)
        if not index:
            return
        self._data["revisions"].pop(index)

    def _find_revision_index(self, revision_id):
        for i, rev in enumerate(self._data["revisions"]):
            if rev["id"] == revision_id:
                return i
        return None



