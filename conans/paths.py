import os
from conans.model.ref import ConanFileReference, PackageReference
from conans.util.files import load, save
from os.path import join, normpath
import platform
import tempfile


EXPORT_FOLDER = "export"
SRC_FOLDER = "source"
BUILD_FOLDER = "build"
PACKAGES_FOLDER = "package"
SYSTEM_REQS_FOLDER = "system_reqs"


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

    drive = os.path.splitdrive(path)[0]
    short_path = drive + "/.conan"
    try:
        os.makedirs(short_path)
    except:
        pass
    redirect = tempfile.mkdtemp(dir=short_path)
    save(link, redirect)
    return redirect


class SimplePaths(object):
    """
    Generate Conan paths. Handles the conan domain path logic. NO DISK ACCESS, just
    path logic responsability
    """
    def __init__(self, store_folder):
        self._store_folder = store_folder
        if platform.system() == "Windows":
            self._shortener = shortener
        else:
            self._shortener = lambda x, _: x

    @property
    def store(self):
        return self._store_folder

    def conan(self, conan_reference):
        """ the base folder for this package reference, for each ConanFileReference
        """
        assert isinstance(conan_reference, ConanFileReference)
        return normpath(join(self._store_folder, "/".join(conan_reference)))

    def export(self, conan_reference):
        assert isinstance(conan_reference, ConanFileReference)
        return normpath(join(self.conan(conan_reference), EXPORT_FOLDER))

    def source(self, conan_reference, shorten=False):
        assert isinstance(conan_reference, ConanFileReference)
        p = normpath(join(self.conan(conan_reference), SRC_FOLDER))
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
        return normpath(join(self.conan(conan_reference), BUILD_FOLDER))

    def build(self, package_reference, shorten=False):
        assert isinstance(package_reference, PackageReference)
        p = normpath(join(self.conan(package_reference.conan), BUILD_FOLDER,
                          package_reference.package_id))
        return self._shortener(p, shorten)

    def system_reqs(self, conan_reference):
        assert isinstance(conan_reference, ConanFileReference)
        return normpath(join(self.conan(conan_reference), SYSTEM_REQS_FOLDER, SYSTEM_REQS))

    def system_reqs_package(self, package_reference):
        assert isinstance(package_reference, PackageReference)
        return normpath(join(self.conan(package_reference.conan), SYSTEM_REQS_FOLDER,
                             package_reference.package_id, SYSTEM_REQS))

    def packages(self, conan_reference):
        assert isinstance(conan_reference, ConanFileReference)
        return normpath(join(self.conan(conan_reference), PACKAGES_FOLDER))

    def package(self, package_reference):
        assert isinstance(package_reference, PackageReference)
        return normpath(join(self.conan(package_reference.conan), PACKAGES_FOLDER,
                             package_reference.package_id))

