import os
from conans.client.cmd.test import PackageTester
from conans.errors import ConanException


def get_test_conanfile_path(tf, conanfile_path):
    """Searches in the declared test_folder or in the standard locations"""

    if tf is False:
        # Look up for testing conanfile can be disabled if tf (test folder) is False
        return None

    test_folders = [tf] if tf else ["test_package", "test"]
    base_folder = os.path.dirname(conanfile_path)
    for test_folder_name in test_folders:
        test_folder = os.path.join(base_folder, test_folder_name)
        test_conanfile_path = os.path.join(test_folder, "conanfile.py")
        if os.path.exists(test_conanfile_path):
            return test_conanfile_path
    else:
        if tf:
            raise ConanException("test folder '%s' not available, or it doesn't have a conanfile.py"
                                 % tf)


def create(reference, manager, user_io, profile, remote_name, update, build_modes, manifest_folder,
           manifest_verify, manifest_interactive, keep_build, test_build_folder, test_folder,
           conanfile_path):

    test_conanfile_path = get_test_conanfile_path(test_folder, conanfile_path)

    if test_conanfile_path:
        pt = PackageTester(manager, user_io)
        pt.install_build_and_test(test_conanfile_path, reference, profile, remote_name, update,
                                  build_modes=build_modes,
                                  manifest_folder=manifest_folder,
                                  manifest_verify=manifest_verify,
                                  manifest_interactive=manifest_interactive,
                                  keep_build=keep_build,
                                  test_build_folder=test_build_folder)
    else:
        manager.install(reference=reference,
                        create_reference=reference,
                        install_folder=None,  # Not output anything
                        manifest_folder=manifest_folder,
                        manifest_verify=manifest_verify,
                        manifest_interactive=manifest_interactive,
                        remote_name=remote_name,
                        profile=profile,
                        build_modes=build_modes,
                        update=update,
                        keep_build=keep_build)
