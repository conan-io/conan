from conans.util.log import logger
from conans.errors import ConanException
from conans.model.ref import PackageReference
from conans.paths import SYSTEM_REQS
import os
from conans.util.files import rmdir


class DiskRemover(object):
    def __init__(self, paths):
        self._paths = paths

    def _remove(self, path, conan_ref, msg=""):
        try:
            logger.debug("Removing folder %s" % path)
            rmdir(path)
        except OSError as e:
            raise ConanException("Unable to remove %s %s\n\t%s" % (repr(conan_ref), msg, str(e)))

    def _remove_file(self, path, conan_ref, msg=""):
        try:
            logger.debug("Removing folder %s" % path)
            if os.path.exists(path):
                os.remove(path)
        except OSError as e:
            raise ConanException("Unable to remove %s %s\n\t%s" % (repr(conan_ref), msg, str(e)))

    def remove(self, conan_ref):
        self._remove(self._paths.conan(conan_ref), conan_ref)

    def remove_src(self, conan_ref):
        self._remove(self._paths.source(conan_ref), conan_ref, "src folder")

    def remove_builds(self, conan_ref, ids=None):
        if not ids:
            self._remove(self._paths.builds(conan_ref), conan_ref, "builds")
        else:
            for id_ in ids:
                self._remove(self._paths.build(PackageReference(conan_ref, id_)), conan_ref,
                             "package:%s" % id_)

    def remove_packages(self, conan_ref, ids_filter=None):
        if not ids_filter:  # Remove all
            self._remove(self._paths.packages(conan_ref), conan_ref, "packages")
            self._remove_file(self._paths.system_reqs(conan_ref), conan_ref, SYSTEM_REQS)
        else:
            for id_ in ids_filter:  # remove just the specified packages
                package_ref = PackageReference(conan_ref, id_)
                self._remove(self._paths.package(package_ref), conan_ref, "package:%s" % id_)
                self._remove_file(self._paths.system_reqs_package(package_ref),
                                  conan_ref, "%s/%s" % (id_, SYSTEM_REQS))
