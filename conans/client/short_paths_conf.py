from conans.util.files import load, save
import os
from conans.errors import ConanException
from conans.model.ref import ConanFileReference
from os.path import normpath


SHORTED_REFERENCES_FILENAME = "short_paths.conf"


class ShortPathsReferences(dict):

    def __init__(self, file_folder):
        self._file_path = os.path.join(file_folder,
                                       SHORTED_REFERENCES_FILENAME)
        self._loads()

    def _loads(self):
        try:
            contents = load(self._file_path)
        except:
            save(self._file_path, "")
            contents = ""

        for line in contents.splitlines():
            line = line.strip()
            if line and line[0] != "#":
                chunks = line.split(":", 1)
                try:
                    ref = ConanFileReference.loads(chunks[0].strip())
                    path = chunks[1].strip()
                    self[ref] = normpath(path)
                except:
                    raise ConanException("Bad file format: %s" % self._file_path)
