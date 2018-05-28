import os
from conans.model.ref import ConanFileReference, PackageReference
from os.path import join, normpath
import platform
from conans.errors import ConanException
from conans.util.files import rmdir


if platform.system() == "Windows":
    from conans.util.windows import path_shortener, rm_conandir, conan_expand_user
else:
    def path_shortener(x, _):
        return x
    conan_expand_user = os.path.expanduser
    rm_conandir = rmdir


EXPORT_FOLDER = "export"
EXPORT_SRC_FOLDER = "export_source"
SRC_FOLDER = "source"
BUILD_FOLDER = "build"
PACKAGES_FOLDER = "package"
SYSTEM_REQS_FOLDER = "system_reqs"


CONANFILE = 'conanfile.py'
CONANFILE_TXT = "conanfile.txt"
CONAN_MANIFEST = "conanmanifest.txt"
BUILD_INFO = 'conanbuildinfo.txt'
BUILD_INFO_GCC = 'conanbuildinfo.gcc'
BUILD_INFO_COMPILER_ARGS = 'conanbuildinfo.args'
BUILD_INFO_CMAKE = 'conanbuildinfo.cmake'
BUILD_INFO_QMAKE = 'conanbuildinfo.pri'
BUILD_INFO_QBS = 'conanbuildinfo.qbs'
BUILD_INFO_VISUAL_STUDIO = 'conanbuildinfo.props'
BUILD_INFO_XCODE = 'conanbuildinfo.xcconfig'
CONANINFO = "conaninfo.txt"
CONANENV = "conanenv.txt"
SYSTEM_REQS = "system_reqs.txt"
PUT_HEADERS = "artifacts.properties"
SCM_FOLDER = "scm_folder.txt"

PACKAGE_TGZ_NAME = "conan_package.tgz"
EXPORT_TGZ_NAME = "conan_export.tgz"
EXPORT_SOURCES_TGZ_NAME = "conan_sources.tgz"
EXPORT_SOURCES_DIR_OLD = ".c_src"

RUN_LOG_NAME = "conan_run.log"

DEFAULT_PROFILE_NAME = "default"


def get_conan_user_home():
    user_home = os.getenv("CONAN_USER_HOME", "~")
    tmp = conan_expand_user(user_home)
    if not os.path.isabs(tmp):
        raise Exception("Invalid CONAN_USER_HOME value '%s', "
                        "please specify an absolute or path starting with ~/ "
                        "(relative to user home)" % tmp)
    return os.path.abspath(tmp)


def is_case_insensitive_os():
    system = platform.system()
    return system != "Linux" and system != "FreeBSD" and system != "SunOS"


if is_case_insensitive_os():
    def check_ref_case(conan_reference, conan_folder, store_folder):
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
    def check_ref_case(conan_reference, conan_folder, store_folder):  # @UnusedVariable
        pass


class SimplePaths(object):
    """
    Generate Conan paths. Handles the conan domain path logic. NO DISK ACCESS, just
    path logic responsability
    """
    def __init__(self, store_folder):
        self._store_folder = store_folder

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

    def export_sources(self, conan_reference, short_paths=False):
        assert isinstance(conan_reference, ConanFileReference)
        p = normpath(join(self.conan(conan_reference), EXPORT_SRC_FOLDER))
        return path_shortener(p, short_paths)

    def source(self, conan_reference, short_paths=False):
        assert isinstance(conan_reference, ConanFileReference)
        p = normpath(join(self.conan(conan_reference), SRC_FOLDER))
        return path_shortener(p, short_paths)

    def conanfile(self, conan_reference):
        export = self.export(conan_reference)
        check_ref_case(conan_reference, export, self.store)
        return normpath(join(export, CONANFILE))

    def builds(self, conan_reference):
        assert isinstance(conan_reference, ConanFileReference)
        return normpath(join(self.conan(conan_reference), BUILD_FOLDER))

    def build(self, package_reference, short_paths=False):
        assert isinstance(package_reference, PackageReference)
        p = normpath(join(self.conan(package_reference.conan), BUILD_FOLDER,
                          package_reference.package_id))
        return path_shortener(p, short_paths)

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
        return path_shortener(p, short_paths)

    def scm_folder(self, conan_reference):
        return normpath(join(self.conan(conan_reference), SCM_FOLDER))
