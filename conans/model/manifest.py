import os
import calendar
import time
from conans.util.files import md5sum, md5
from conans.paths import PACKAGE_TGZ_NAME, EXPORT_TGZ_NAME, CONAN_MANIFEST, CONANFILE
from conans.errors import ConanException


class FileTreeManifest(object):

    def __init__(self, time, file_sums):
        """file_sums is a dict with filepaths and md5's: {filepath/to/file.txt: md5}"""
        self.time = time
        self.file_sums = file_sums

    def __repr__(self):
        ret = "%s\n" % (self.time)
        for filepath, file_md5 in sorted(self.file_sums.items()):
            ret += "%s: %s\n" % (filepath, file_md5)
        return ret

    @property
    def summary_hash(self):
        ret = ""  # Do not include the timestamp in the summary hash
        for filepath, file_md5 in sorted(self.file_sums.items()):
            ret += "%s: %s\n" % (filepath, file_md5)
        return md5(ret)

    @staticmethod
    def loads(text):
        """ parses a string representation, generated with __repr__ of a
        ConanDigest
        """
        tokens = text.split("\n")
        time = int(tokens[0])
        file_sums = {}
        for md5line in tokens[1:]:
            if md5line:
                filename, file_md5 = md5line.split(": ")
                file_sums[filename] = file_md5
        return FileTreeManifest(time, file_sums)

    @classmethod
    def create(cls, folder):
        """ Walks a folder and create a FileTreeManifest for it, reading file contents
        from disk, and capturing current time
        """
        filterfiles = (PACKAGE_TGZ_NAME, EXPORT_TGZ_NAME, CONAN_MANIFEST, CONANFILE + "c",
                       ".DS_Store")
        file_dict = {}
        for root, dirs, files in os.walk(folder):
            dirs[:] = [d for d in dirs if d != "__pycache__"]  # Avoid recursing pycache
            relative_path = os.path.relpath(root, folder)
            files = [f for f in files if f not in filterfiles]  # Avoid md5 of big TGZ files
            for f in files:
                abs_path = os.path.join(root, f)
                rel_path = os.path.normpath(os.path.join(relative_path, f))
                rel_path = rel_path.replace("\\", "/")
                if os.path.exists(abs_path):
                    file_dict[rel_path] = md5sum(abs_path)
                else:
                    raise ConanException("The file is a broken symlink, verify that "
                                         "you are packaging the needed destination files: '%s'"
                                         % abs_path)
        date = calendar.timegm(time.gmtime())

        return cls(date, file_dict)

    def __eq__(self, other):
        return self.time == other.time and self.file_sums == other.file_sums

    def __ne__(self, other):
        return not self.__eq__(other)
