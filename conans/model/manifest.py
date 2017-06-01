import os
import calendar
import time
from conans.util.files import md5sum, md5
from conans.paths import PACKAGE_TGZ_NAME, EXPORT_TGZ_NAME, CONAN_MANIFEST, EXPORT_SOURCES_TGZ_NAME
from conans.errors import ConanException
import datetime


def discarded_file(filename):
    return filename == ".DS_Store" or filename.endswith(".pyc") or filename.endswith(".pyo")


def gather_files(folder):
    file_dict = {}
    symlinks = {}
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d != "__pycache__"]  # Avoid recursing pycache
        for d in dirs:
            abs_path = os.path.join(root, d)
            if os.path.islink(abs_path):
                rel_path = abs_path[len(folder) + 1:].replace("\\", "/")
                symlinks[rel_path] = os.readlink(abs_path)
        for f in files:
            if discarded_file(f):
                continue
            abs_path = os.path.join(root, f)
            rel_path = abs_path[len(folder) + 1:].replace("\\", "/")
            if os.path.exists(abs_path):
                file_dict[rel_path] = abs_path
            else:
                raise ConanException("The file is a broken symlink, verify that "
                                     "you are packaging the needed destination files: '%s'"
                                     % abs_path)

    return file_dict, symlinks


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

    def files(self):
        return self.file_sums.keys()

    @property
    def summary_hash(self):
        ret = ""  # Do not include the timestamp in the summary hash
        for filepath, file_md5 in sorted(self.file_sums.items()):
            ret += "%s: %s\n" % (filepath, file_md5)
        return md5(ret)

    @property
    def time_str(self):
        return datetime.datetime.fromtimestamp(int(self.time)).strftime('%Y-%m-%d %H:%M:%S')

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
                if not discarded_file(filename):
                    file_sums[filename] = file_md5
        return FileTreeManifest(time, file_sums)

    @classmethod
    def create(cls, folder):
        """ Walks a folder and create a FileTreeManifest for it, reading file contents
        from disk, and capturing current time
        """
        files, _ = gather_files(folder)
        for f in (PACKAGE_TGZ_NAME, EXPORT_TGZ_NAME, CONAN_MANIFEST, EXPORT_SOURCES_TGZ_NAME):
            files.pop(f, None)

        file_dict = {}
        for name, filepath in files.items():
            file_dict[name] = md5sum(filepath)

        date = calendar.timegm(time.gmtime())

        return cls(date, file_dict)

    def __eq__(self, other):
        """ Two manifests are equal if file_sums
        """
        return self.file_sums == other.file_sums

    def __ne__(self, other):
        return not self.__eq__(other)

    def difference(self, other):
        result = {}
        for f, h in self.file_sums.items():
            h2 = other.file_sums.get(f)
            if h != h2:
                result[f] = h, h2
        for f, h in other.file_sums.items():
            h2 = self.file_sums.get(f)
            if h != h2:
                result[f] = h2, h
        return result
