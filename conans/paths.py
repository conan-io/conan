import os
from conans.model.ref import ConanFileReference, PackageReference
from conans.util.files import load, relative_dirs, path_exists, save
from os.path import isfile
from os.path import join, normpath
from conans.model.manifest import FileTreeManifest
import platform
import uuid


EXPORT_FOLDER = "export"
MIN_EXPORT_FOLDER = "e"

SRC_FOLDER = "source"
MIN_SRC_FOLDER = "s"

BUILD_FOLDER = "build"
MIN_BUILD_FOLDER = "b"

PACKAGES_FOLDER = "package"
MIN_PACKAGES_FOLDER = "p"

SYSTEM_REQS_FOLDER = "system_reqs"
MIN_SYSTEM_REQS_FOLDER = "srq"


CONANFILE = 'conanfile.py'
CONANFILE_TXT = "conanfile.txt"
CONAN_MANIFEST = "conanmanifest.txt"
BUILD_INFO = 'conanbuildinfo.txt'
BUILD_INFO_GCC = 'conanbuildinfo.gcc'
BUILD_INFO_CMAKE = 'conanbuildinfo.cmake'
BUILD_INFO_QMAKE = 'conanbuildinfo.pri'
BUILD_INFO_QBS = 'conanbuildinfo.qbs'
BUILD_INFO_VISUAL_STUDIO = 'conanbuildinfo.props'
BUILD_INFO_XCODE = 'conanbuildinfo.xcconfig'
BUILD_INFO_YCM = '.ycm_extra_conf.py'
CONANINFO = "conaninfo.txt"
SYSTEM_REQS = "system_reqs.txt"
DIRTY_FILE = ".conan_dirty"

PACKAGE_TGZ_NAME = "conan_package.tgz"
EXPORT_TGZ_NAME = "conan_export.tgz"


def conan_expand_user(path):
    """ wrapper to the original expanduser function, to workaround python returning
    verbatim %USERPROFILE% when some other app (git for windows) sets HOME envvar
    """
    if platform.system() == "Windows":
        # In win these variables should exist and point to user directory, which
        # must exist. Using context to avoid permanent modification of os.environ
        old_env = dict(os.environ)
        try:
            home = os.environ.get("HOME")
            if home and not os.path.exists(home):
                del os.environ["HOME"]
            result = os.path.expanduser(path)
        finally:
            os.environ.clear()
            os.environ.update(old_env)
        return result

    return os.path.expanduser(path)


def shortener(path, shorten):
    if not shorten:
        return path
    link = os.path.join(path, ".conan_link")
    if os.path.exists(link):
        return load(link)

    redirect = os.path.join("F:/Aconantmp", str(uuid.uuid4()))
    save(link, redirect)
    return redirect


class SimplePaths(object):
    """
    Generate Conan paths. Handles the conan domain path logic. NO DISK ACCESS, just
    path logic responsability
    """
    def __init__(self, store_folder, short_path_refs=None):
        self.short_path_refs = short_path_refs or {}
        self._store_folder = store_folder
        if platform.system() == "Windows":
            self._shortener = shortener
        else:
            self._shortener = lambda x, _: x

    @property
    def store(self):
        return self._store_folder

    def conan(self, conan_reference):
        """ the base conans folder, for each ConanFileReference
        """
        assert isinstance(conan_reference, ConanFileReference)
        if conan_reference in self.short_path_refs:
            return self._conan_short(conan_reference)
        return normpath(join(self._store_folder, "/".join(conan_reference)))

    def _conan_short(self, conan_reference):
        return normpath(self.short_path_refs[conan_reference])

    def export(self, conan_reference):
        assert isinstance(conan_reference, ConanFileReference)
        folder = EXPORT_FOLDER if conan_reference not in self.short_path_refs else MIN_EXPORT_FOLDER
        return normpath(join(self.conan(conan_reference), folder))

    def source(self, conan_reference, shorten=False):
        assert isinstance(conan_reference, ConanFileReference)
        folder = SRC_FOLDER if conan_reference not in self.short_path_refs else MIN_SRC_FOLDER
        p = normpath(join(self.conan(conan_reference), folder))
        return self._shortener(p, shorten)

    def conanfile(self, conan_reference):
        export = self.export(conan_reference)
        return normpath(join(export, CONANFILE))

    def digestfile_conanfile(self, conan_reference):
        export = self.export(conan_reference)
        return normpath(join(export, CONAN_MANIFEST))

    def digestfile_package(self, package_reference):
        assert isinstance(package_reference, PackageReference)
        return normpath(join(self.package(package_reference), CONAN_MANIFEST))

    def builds(self, conan_reference):
        assert isinstance(conan_reference, ConanFileReference)
        folder = BUILD_FOLDER if conan_reference not in self.short_path_refs else MIN_BUILD_FOLDER
        return normpath(join(self.conan(conan_reference), folder))

    def build(self, package_reference, shorten=False):
        assert isinstance(package_reference, PackageReference)
        ref = package_reference.conan
        folder = BUILD_FOLDER if ref not in self.short_path_refs else MIN_BUILD_FOLDER
        pid = package_reference.package_id
        package_id = pid if ref not in self.short_path_refs else self._short_sha(pid)
        p = normpath(join(self.conan(package_reference.conan), folder, package_id))
        return self._shortener(p, shorten)

    def system_reqs(self, conan_reference):
        assert isinstance(conan_reference, ConanFileReference)
        folder = SYSTEM_REQS_FOLDER if conan_reference not in self.short_path_refs else MIN_SYSTEM_REQS_FOLDER
        return normpath(join(self.conan(conan_reference), folder, SYSTEM_REQS))

    def system_reqs_package(self, package_reference):
        assert isinstance(package_reference, PackageReference)
        ref = package_reference.conan
        folder = SYSTEM_REQS_FOLDER if ref not in self.short_path_refs else MIN_SYSTEM_REQS_FOLDER
        pid = package_reference.package_id
        package_id = pid if ref not in self.short_path_refs else self._short_sha(pid)

        return normpath(join(self.conan(package_reference.conan), folder, package_id, SYSTEM_REQS))

    def packages(self, conan_reference):
        assert isinstance(conan_reference, ConanFileReference)
        folder = PACKAGES_FOLDER if conan_reference not in self.short_path_refs else MIN_PACKAGES_FOLDER
        return normpath(join(self.conan(conan_reference), folder))

    def package(self, package_reference):
        assert isinstance(package_reference, PackageReference)
        if package_reference.conan in self.short_path_refs:
            return self._package_short(package_reference)
        return normpath(join(self.conan(package_reference.conan), PACKAGES_FOLDER,
                             package_reference.package_id))

    def _package_short(self, package_reference):
        return normpath(join(self.conan(package_reference.conan), MIN_PACKAGES_FOLDER,
                             self._short_sha(package_reference.package_id)))

    def _short_sha(self, sha):
        return sha[0:6]


# FIXME: Move to client, Should not be necessary in server anymore. Replaced with disk_adapter
class StorePaths(SimplePaths):
    """ Disk storage of conans and binary packages. Useful both in client and
    in server. Accesses to real disk and reads/write things.
    """

    def __init__(self, store_folder, short_path_refs=None):
        super(StorePaths, self).__init__(store_folder, short_path_refs)

    def export_paths(self, conan_reference):
        ''' Returns all file paths for a conans (relative to conans directory)'''
        return relative_dirs(self.export(conan_reference))

    def package_paths(self, package_reference):
        ''' Returns all file paths for a package (relative to conans directory)'''
        return relative_dirs(self.package(package_reference))

    def conan_packages(self, conan_reference):
        """ Returns a list of package_id from a conans """
        assert isinstance(conan_reference, ConanFileReference)
        packages_dir = self.packages(conan_reference)
        try:
            packages = [dirname for dirname in os.listdir(packages_dir)
                        if not isfile(os.path.join(packages_dir, dirname))]
        except:  # if there isn't any package folder
            packages = []
        return packages

    def load_digest(self, conan_reference):
        '''conan_id = sha(zip file)'''
        filename = os.path.join(self.export(conan_reference), CONAN_MANIFEST)
        return FileTreeManifest.loads(load(filename))

    def conan_manifests(self, conan_reference):
        digest_path = self.digestfile_conanfile(conan_reference)
        return self._digests(digest_path)

    def package_manifests(self, package_reference):
        digest_path = self.digestfile_package(package_reference)
        return self._digests(digest_path)

    def _digests(self, digest_path):
        if not path_exists(digest_path, self.store):
            return None, None
        readed_digest = FileTreeManifest.loads(load(digest_path))
        expected_digest = FileTreeManifest.create(os.path.dirname(digest_path))
        return readed_digest, expected_digest
