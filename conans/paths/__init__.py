# coding=utf-8

import os
import platform

if platform.system() == "Windows":
    from conans.util.windows import conan_expand_user, rm_conandir
else:
    from conans.util.files import rmdir

    conan_expand_user = os.path.expanduser
    rm_conandir = rmdir


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


# Files
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
BUILD_INFO_PREMAKE = 'conanbuildinfo.premake.lua'
BUILD_INFO_MAKE = 'conanbuildinfo.mak'
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
SCM_FOLDER = "scm_folder.txt"
PACKAGE_METADATA = "metadata.json"
CACERT_FILE = "cacert.pem"  # Server authorities file

# Directories
EXPORT_FOLDER = "export"
EXPORT_SRC_FOLDER = "export_source"
SRC_FOLDER = "source"
BUILD_FOLDER = "build"
PACKAGES_FOLDER = "package"
SYSTEM_REQS_FOLDER = "system_reqs"
