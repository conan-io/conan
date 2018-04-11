import os
from conans.model.ref import ConanFileReference, PackageReference, ConanName
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

PACKAGE_TGZ_NAME = "conan_package.tgz"
EXPORT_TGZ_NAME = "conan_export.tgz"
EXPORT_SOURCES_TGZ_NAME = "conan_sources.tgz"
EXPORT_SOURCES_DIR_OLD = ".c_src"

RUN_LOG_NAME = "conan_run.log"

DEFAULT_PROFILE_NAME = "default"


REVISIONS_SEPARATOR_PATH = "___"


def get_conan_user_home():
    tmp = conan_expand_user(os.getenv("CONAN_USER_HOME", "~"))
    if not os.path.isabs(tmp):
        raise Exception("Invalid CONAN_USER_HOME value '%s', "
                        "please specify an absolute or path starting with ~/ "
                        "(relative to user home)" % tmp)
    return os.path.abspath(tmp)


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
                if offending:
                    raise ConanException("Requested '%s' but found case incompatible '%s'\n"
                                         "Case insensitive filesystem can't manage this"
                                         % (str(conan_reference), offending))
            tmp = os.path.normpath(tmp + os.sep + part)
else:
    def _check_ref_case(conan_reference, conan_folder, store_folder):  # @UnusedVariable
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
        if conan_reference.revision:
            path = "/".join([conan_reference.name,
                            conan_reference.version,
                            conan_reference.user,
                            "%s%s%s" % (conan_reference.channel_without_revision,
                                        REVISIONS_SEPARATOR_PATH,
                                        conan_reference.revision)])
        else:
            path = "/".join(conan_reference)

        return normpath(join(self._store_folder, path))

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

    def channels_path(self, name, version, user):
        return normpath(join(self._store_folder, "/".join([name, version, user])))

    def package(self, package_reference, short_paths=False):
        assert isinstance(package_reference, PackageReference)
        p = normpath(join(self.conan(package_reference.conan), PACKAGES_FOLDER,
                          package_reference.package_id))
        return path_shortener(p, short_paths)

    def get_latest_revision_reference(self, conan_reference):
        if conan_reference.revision is not None:
            return conan_reference
        try:
            path = self.channels_path(conan_reference.name,
                                      conan_reference.version, conan_reference.user)
            channels = [channel for channel in os.listdir(path)
                        if os.path.isdir(join(path, channel)) and
                           conan_reference.channel_without_revision ==
                           channel.split(REVISIONS_SEPARATOR_PATH, 1)[0]]

        except OSError:  # if there isn't any package folder
            channels = []

        max_revision = None
        for channel in channels:
            channel = channel.replace(REVISIONS_SEPARATOR_PATH, ConanName.revision_separator)
            ref = ConanFileReference(conan_reference.name, conan_reference.version,
                                     conan_reference.user, channel)
            if not max_revision or (ref.revision is not None and ref.revision > max_revision):
                max_revision = ref.revision

        if not max_revision:  # There are not references with revisions
            return conan_reference
        else:
            new_channel = "%s%s%s" % (conan_reference.channel_without_revision,
                                      ConanName.revision_separator,
                                      max_revision)
            ref = ConanFileReference(conan_reference.name, conan_reference.version,
                                     conan_reference.user, new_channel)
            # self._output.info("Using latest revision '%s'" % str(ref))
            return ref
