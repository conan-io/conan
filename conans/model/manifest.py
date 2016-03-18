import os
import calendar
import time
from conans.util.files import md5sum


class FileTreeManifest(object):

    def __init__(self, time, file_sums):
        """file_sums is a dict with filepaths and md5's: {filepath/to/file.txt: md5}"""
        self.time = time
        self.file_sums = file_sums

    def __repr__(self):
        ret = "%s" % (self.time)
        for filepath, file_md5 in self.file_sums.items():
            ret += "\n%s: %s" % (filepath, file_md5)
        return ret

    @staticmethod
    def loads(text):
        """ parses a string representation, generated with __repr__ of a
        ConanDigest
        """
        tokens = text.split("\n")
        time = int(tokens[0])
        file_sums = {}
        for md5line in tokens[1:]:
            filename, file_md5 = md5line.split(": ")
            file_sums[filename] = file_md5
        return FileTreeManifest(time, file_sums)

    @classmethod
    def create(cls, folder):
        """ Walks a folder and create a TreeDigest for it, reading file contents
        from disk, and capturing current time
        """
        file_dict = {}
        for root, _, files in os.walk(folder):
            relative_path = os.path.relpath(root, folder)
            for f in files:
                abs_path = os.path.join(root, f)
                rel_path = os.path.normpath(os.path.join(relative_path, f))
                rel_path = rel_path.replace("\\", "/")
                file_dict[rel_path] = md5sum(abs_path)

        date = calendar.timegm(time.gmtime())
        from conans.paths import CONAN_MANIFEST, CONANFILE
        file_dict.pop(CONAN_MANIFEST, None)  # Exclude the MANIFEST itself
        file_dict.pop(CONANFILE + "c", None)  # Exclude the CONANFILE.pyc
        file_dict.pop(".DS_Store", None)  # Exclude tmp in mac
        
        file_dict = {key:value for key, value in file_dict.items() if not key.startswith("__pycache__")}

        return cls(date, file_dict)

    def __eq__(self, other):
        return self.time == other.time and self.file_sums == other.file_sums

    def __ne__(self, other):
        return not self.__eq__(other)
