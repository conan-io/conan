import os
from conans.errors import ConanException, NotFoundException
from conans.model.ref import PackageReference


class ConanUploader(object):

    def __init__(self, paths, user_io, remote_proxy):
        self._paths = paths
        self._user_io = user_io
        self._remote_proxy = remote_proxy

    def upload_conan(self, conan_ref, force=False, all_packages=False):
        """Uploads the conans identified by conan_ref"""
        export_path = self._paths.export(conan_ref)
        if os.path.exists(export_path):
            if not force:
                self._check_package_date(conan_ref)

            self._user_io.out.info("Uploading %s" % str(conan_ref))
            self._remote_proxy.upload_conan(conan_ref)

            if all_packages:
                for index, package_id in enumerate(self._paths.conan_packages(conan_ref)):
                    total = len(self._paths.conan_packages(conan_ref))
                    self.upload_package(PackageReference(conan_ref, package_id), index + 1, total)
        else:
            self._user_io.out.error("There is no local conanfile exported as %s"
                                    % str(conan_ref))

    def upload_package(self, package_ref, index=1, total=1):
        """Uploads the package identified by package_id"""
        msg = ("Uploading package %d/%d: %s" % (index, total, str(package_ref.package_id)))
        self._user_io.out.info(msg)
        self._remote_proxy.upload_package(package_ref)

    def _check_package_date(self, conan_ref):
        try:
            remote_conan_digest = self._remote_proxy.get_conan_digest(conan_ref)
        except NotFoundException:
            return  # First upload

        local_digest = self._paths.load_digest(conan_ref)

        if remote_conan_digest.time > local_digest.time:
            raise ConanException("Remote conans is newer than local conans: "
                                 "\n Remote date: %s\n Local date: %s" %
                                 (remote_conan_digest.time, local_digest.time))
