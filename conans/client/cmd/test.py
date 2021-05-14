import hashlib
import os
import tempfile

from conans.client.cmd.build import cmd_build
from conans.client.manager import deps_install
from conans.util.env_reader import get_env
from conans.util.files import rmdir


def install_build_and_test(app, conanfile_abs_path, reference, profile_host, profile_build,
                           graph_lock, root_ref, remotes, update, build_modes=None,
                           test_build_folder=None, recorder=None):
    """
    Installs the reference (specified by the parameters or extracted from the test conanfile)
    and builds the test_package/conanfile.py running the test() method.
    """
    base_folder = os.path.dirname(conanfile_abs_path)
    test_build_folder, delete_after_build = _build_folder(test_build_folder, profile_host,
                                                          base_folder)
    rmdir(test_build_folder)
    if build_modes is None:
        build_modes = ["never"]
    try:
        deps_info = deps_install(app=app,
                                 create_reference=reference,
                                 ref_or_path=conanfile_abs_path,
                                 install_folder=test_build_folder,
                                 base_folder=test_build_folder,
                                 remotes=remotes,
                                 profile_host=profile_host,
                                 profile_build=profile_build,
                                 graph_lock=graph_lock,
                                 root_ref=root_ref,
                                 update=update,
                                 build_modes=build_modes,
                                 recorder=recorder)
        conanfile = deps_info.root.conanfile
        cmd_build(app, conanfile_abs_path, conanfile, base_folder,
                  source_folder=base_folder, build_folder=test_build_folder,
                  package_folder=os.path.join(test_build_folder, "package"),
                  install_folder=test_build_folder, test=reference)
    finally:
        if delete_after_build:
            # Required for windows where deleting the cwd is not possible.
            os.chdir(base_folder)
            rmdir(test_build_folder)


def _build_folder(test_build_folder, profile, base_folder):
    # Use the specified build folder when available.
    if test_build_folder:
        return os.path.abspath(test_build_folder), False

    # Otherwise, generate a new test folder depending on the configuration.
    if get_env('CONAN_TEMP_TEST_FOLDER', False):
        return tempfile.mkdtemp(prefix='conans'), True

    sha = hashlib.sha1("".join(profile.dumps()).encode()).hexdigest()
    build_folder = os.path.join(base_folder, "build", sha)
    return build_folder, False
