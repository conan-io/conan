import calendar
import datetime
import os
import time

from conans.errors import ConanException
from conans.paths import CONAN_MANIFEST, EXPORT_SOURCES_TGZ_NAME, EXPORT_TGZ_NAME, PACKAGE_TGZ_NAME
from conans.util.env_reader import get_env
from conans.util.files import load, md5, md5sum, save, walk


def discarded_file(filename):
    """
    # The __conan pattern is to be prepared for the future, in case we want to manage our
    own files that shouldn't be uploaded
    """
    return (filename == ".DS_Store" or filename.endswith(".pyc") or
            filename.endswith(".pyo") or filename == "__pycache__" or
            filename.startswith("__conan"))


def gather_files(folder):
    file_dict = {}
    symlinks = {}
    for root, dirs, files in walk(folder):
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
                if not get_env("CONAN_SKIP_BROKEN_SYMLINKS_CHECK", False):
                    raise ConanException("The file is a broken symlink, verify that "
                                         "you are packaging the needed destination files: '%s'."
                                         "You can skip this check adjusting the "
                                         "'general.skip_broken_symlinks_check' at the conan.conf "
                                         "file."
                                         % abs_path)

    return file_dict, symlinks


class FileTreeManifest(object):

    def __init__(self, the_time, file_sums):
        """file_sums is a dict with filepaths and md5's: {filepath/to/file.txt: md5}"""
        self.time = the_time
        self.file_sums = file_sums

    def files(self):
        return self.file_sums.keys()

    @property
    def summary_hash(self):
        s = ["%s: %s" % (f, fmd5) for f, fmd5 in sorted(self.file_sums.items())]
        s.append("")
        return md5("\n".join(s))

    @property
    def time_str(self):
        return datetime.datetime.fromtimestamp(int(self.time)).strftime('%Y-%m-%d %H:%M:%S')

    @staticmethod
    def loads(text):
        """ parses a string representation, generated with __repr__ of a
        ConanDigest
        """
        tokens = text.split("\n")
        the_time = int(tokens[0])
        file_sums = {}
        for md5line in tokens[1:]:
            if md5line:
                filename, file_md5 = md5line.split(": ")
                if not discarded_file(filename):
                    file_sums[filename] = file_md5
        return FileTreeManifest(the_time, file_sums)

    @staticmethod
    def load(folder):
        text = load(os.path.join(folder, CONAN_MANIFEST))
        return FileTreeManifest.loads(text)

    def __repr__(self):
        ret = ["%s" % self.time]
        for file_path, file_md5 in sorted(self.file_sums.items()):
            ret.append("%s: %s" % (file_path, file_md5))
        ret.append("")
        content = "\n".join(ret)
        return content

    def __str__(self):
        dt = datetime.datetime.utcfromtimestamp(self.time).strftime('%Y-%m-%d %H:%M:%S')
        ret = ["Time: %s" % dt]
        for file_path, file_md5 in sorted(self.file_sums.items()):
            ret.append("%s, MD5: %s" % (file_path, file_md5))
        ret.append("")
        content = "\n".join(ret)
        return content

    def save(self, folder, filename=CONAN_MANIFEST):
        path = os.path.join(folder, filename)
        save(path, repr(self))

    @classmethod
    def create(cls, folder, exports_sources_folder=None):
        """ Walks a folder and create a FileTreeManifest for it, reading file contents
        from disk, and capturing current time
        """
        files, _ = gather_files(folder)
        for f in (PACKAGE_TGZ_NAME, EXPORT_TGZ_NAME, CONAN_MANIFEST, EXPORT_SOURCES_TGZ_NAME):
            files.pop(f, None)

        file_dict = {}
        for name, filepath in files.items():
            file_dict[name] = md5sum(filepath)

        if exports_sources_folder:
            export_files, _ = gather_files(exports_sources_folder)
            for name, filepath in export_files.items():
                file_dict["export_source/%s" % name] = md5sum(filepath)

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
