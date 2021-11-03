# coding=utf-8

import os
import platform

if platform.system() == "Windows":
    from conans.util.windows import conan_expand_user
else:
    conan_expand_user = os.path.expanduser

DEFAULT_CONAN_USER_HOME = ".conan2"


def get_conan_user_home():
    user_home = os.getenv("CONAN_USER_HOME")
    if user_home is None:
        # the default, in the user home
        user_home = os.path.join(conan_expand_user("~"), DEFAULT_CONAN_USER_HOME)
    else:  # Do an expansion, just in case the user is using ~/something/here
        user_home = conan_expand_user(user_home)
    if not os.path.isabs(user_home):
        raise Exception("Invalid CONAN_USER_HOME value '%s', "
                        "please specify an absolute or path starting with ~/ "
                        "(relative to user home)" % user_home)
    return user_home


# Files
CONANFILE = 'conanfile.py'
CONANFILE_TXT = "conanfile.txt"
CONAN_MANIFEST = "conanmanifest.txt"
BUILD_INFO_PREMAKE = 'conanbuildinfo.premake.lua'
BUILD_INFO_DEPLOY = 'deploy_manifest.txt'
CONANINFO = "conaninfo.txt"
CONANENV = "conanenv.txt"
SYSTEM_REQS = "system_reqs.txt"
ARTIFACTS_PROPERTIES_FILE = "artifacts.properties"
ARTIFACTS_PROPERTIES_PUT_PREFIX = "artifact_property_"
PACKAGE_TGZ_NAME = "conan_package.tgz"
EXPORT_TGZ_NAME = "conan_export.tgz"
EXPORT_SOURCES_TGZ_NAME = "conan_sources.tgz"
RUN_LOG_NAME = "conan_run.log"
DEFAULT_PROFILE_NAME = "default"
PACKAGE_METADATA = "metadata.json"
CACERT_FILE = "cacert.pem"  # Server authorities file
DATA_YML = "conandata.yml"

# Directories
EXPORT_FOLDER = "export"
EXPORT_SRC_FOLDER = "export_source"
SRC_FOLDER = "source"
BUILD_FOLDER = "build"
PACKAGES_FOLDER = "package"
SYSTEM_REQS_FOLDER = "system_reqs"
SCM_SRC_FOLDER = "scm_source"
