import hashlib
import os

from conans.util.files import rmdir


class PackageTester(object):

    def __init__(self, manager, user_io):
        self._manager = manager
        self._user_io = user_io

    def install_build_and_test(self, conanfile_abs_path, reference, profile,
                               remote, update, build_modes=None, manifest_folder=None,
                               manifest_verify=False, manifest_interactive=False, keep_build=False):
        """
        Installs the reference (specified by the parameters or extracted from the test conanfile)
        and builds the test_package/conanfile.py running the test() method.
        """
        base_folder = os.path.dirname(conanfile_abs_path)
        build_folder = self._build_folder(profile, base_folder)
        rmdir(build_folder)
        if build_modes is None:
            build_modes = ["never"]
        self._manager.install(inject_require=reference,
                              reference=conanfile_abs_path,
                              install_folder=build_folder,
                              remote=remote,
                              profile=profile,
                              update=update,
                              build_modes=build_modes,
                              manifest_folder=manifest_folder,
                              manifest_verify=manifest_verify,
                              manifest_interactive=manifest_interactive,
                              keep_build=keep_build)
        self._manager.build(conanfile_abs_path, base_folder, build_folder, package_folder=None,
                            install_folder=build_folder, test=str(reference))

    @staticmethod
    def _build_folder(profile, test_folder):
        sha = hashlib.sha1("".join(profile.dumps()).encode()).hexdigest()
        build_folder = os.path.join(test_folder, "build", sha)
        return build_folder
