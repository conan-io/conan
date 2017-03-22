import os
from conans.model.ref import ConanFileReference, PackageReference
from conans.util.files import load, save, rmdir
from os.path import join, normpath
import platform
import tempfile
from conans.errors import ConanException


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
CONANENV = "conanenv.txt"
SYSTEM_REQS = "system_reqs.txt"
DIRTY_FILE = ".conan_dirty"
PUT_HEADERS = "artifacts.properties"

PACKAGE_TGZ_NAME = "conan_package.tgz"
EXPORT_TGZ_NAME = "conan_export.tgz"
EXPORT_SOURCES_TGZ_NAME = "conan_sources.tgz"
EXPORT_SOURCES_DIR = ".c_src"
CONAN_LINK = ".conan_link"

RUN_LOG_NAME = "conan_run.log"


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
            # Problematic cases of wrong HOME variable
            # - HOME = %USERPROFILE% verbatim, as messed by some other tools
            # - MSYS console, that defines a different user home in /c/mingw/msys/users/xxx
            # In these cases, it is safe to remove it and rely on USERPROFILE directly
            if home and (not os.path.exists(home) or
                         (os.getenv("MSYSTEM") and os.getenv("USERPROFILE"))):
                del os.environ["HOME"]
            result = os.path.expanduser(path)
        finally:
            os.environ.clear()
            os.environ.update(old_env)
        return result

    return os.path.expanduser(path)


if platform.system() == "Windows":
    def _rm_conandir(path):
        ''' removal of a directory that might contain a link to a short path
        '''
        link = os.path.join(path, CONAN_LINK)
        if os.path.exists(link):
            short_path = load(link)
            rmdir(os.path.dirname(short_path))
        rmdir(path)
    rm_conandir = _rm_conandir
else:
    rm_conandir = rmdir


def is_case_insensitive_os():
    system = platform.system()
    return system != "Linux" and system != "FreeBSD" and system != "SunOS"


if is_case_insensitive_os():
    def _check_ref_case(conan_reference, conan_folder, store_folder):
        if not os.path.exists(conan_folder):  # If it doesn't exist, not a problem
            return
        # If exists, lets check path
        tmp = store_folder
        for part in conan_reference:
            items = os.listdir(tmp)
            if part not in items:
                offending = ""
                for item in items:
                    if item.lower() == part.lower():
                        offending = item
                        break
                raise ConanException("Requested '%s' but found case incompatible '%s'\n"
                                     "Case insensitive filesystem can't manage this"
                                     % (str(conan_reference), offending))
            tmp = os.path.normpath(tmp + os.sep + part)
else:
    def _check_ref_case(conan_reference, conan_folder, store_folder):  # @UnusedVariable
        pass


def _shortener(path, short_paths):
    """ short_paths is 4-state:
    False: Never shorten the path
    True: Always shorten the path, create link if not existing
    None: Use shorten path only if already exists, not create
    Other: Integrity check. Consumer knows it should be short, but it isn't
    """
    if short_paths is False:
        return path
    link = os.path.join(path, CONAN_LINK)
    if os.path.exists(link):
        return load(link)
    elif short_paths is None:
        return path
    elif short_paths is not True:
        raise ConanException("This path should be short, but it isn't: %s\n"
                             "Try to remove these packages and re-build them" % path)

    short_home = os.getenv("CONAN_USER_HOME_SHORT")
    if not short_home:
        drive = os.path.splitdrive(path)[0]
        short_home = drive + "/.conan"
    try:
        os.makedirs(short_home)
    except:
        pass
    redirect = tempfile.mkdtemp(dir=short_home, prefix="")
    # This "1" is the way to have a non-existing directory, so commands like
    # shutil.copytree() to it, works. It can be removed without compromising the
    # temp folder generator and conan-links consistency
    redirect = os.path.join(redirect, "1")
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
            self._shortener = _shortener
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

    def source(self, conan_reference, short_paths=False):
        assert isinstance(conan_reference, ConanFileReference)
        p = normpath(join(self.conan(conan_reference), SRC_FOLDER))
        return self._shortener(p, short_paths)

    def conanfile(self, conan_reference):
        export = self.export(conan_reference)
        _check_ref_case(conan_reference, export, self.store)
        return normpath(join(export, CONANFILE))

    def digestfile_conanfile(self, conan_reference):
        export = self.export(conan_reference)
        _check_ref_case(conan_reference, export, self.store)
        return normpath(join(export, CONAN_MANIFEST))

    def digestfile_package(self, package_reference, short_paths=False):
        assert isinstance(package_reference, PackageReference)
        return normpath(join(self.package(package_reference, short_paths), CONAN_MANIFEST))

    def builds(self, conan_reference):
        assert isinstance(conan_reference, ConanFileReference)
        return normpath(join(self.conan(conan_reference), BUILD_FOLDER))

    def build(self, package_reference, short_paths=False):
        assert isinstance(package_reference, PackageReference)
        p = normpath(join(self.conan(package_reference.conan), BUILD_FOLDER,
                          package_reference.package_id))
        return self._shortener(p, short_paths)

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

    def package(self, package_reference, short_paths=False):
        assert isinstance(package_reference, PackageReference)
        p = normpath(join(self.conan(package_reference.conan), PACKAGES_FOLDER,
                          package_reference.package_id))
        return self._shortener(p, short_paths)
