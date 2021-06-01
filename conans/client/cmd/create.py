import os

from conans.client.cmd.test import install_build_and_test
from conans.client.manager import deps_install
from conans.errors import ConanException
from conans.model.ref import ConanFileReference


def _get_test_conanfile_path(tf, conanfile_path):
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


def create(app, ref, profile_host, profile_build, graph_lock, root_ref, remotes, update, build_modes,
           test_build_folder, test_folder, conanfile_path, recorder, is_build_require=False):
    assert isinstance(ref, ConanFileReference), "ref needed"
    assert profile_host is not None
    assert profile_build is not None

    test_conanfile_path = _get_test_conanfile_path(test_folder, conanfile_path)

    if test_conanfile_path:
        if graph_lock:
            # If we have a lockfile, then we are first going to make sure the lockfile is used
            # correctly to build the package in the cache, and only later will try to run
            # test_package
            out = app.out
            out.info("Installing and building %s" % repr(ref))
            deps_install(app=app,
                         ref_or_path=ref,
                         create_reference=ref,
                         install_folder=None,  # Not output conaninfo etc
                         base_folder=None,  # Not output generators
                         remotes=remotes,
                         profile_host=profile_host,
                         profile_build=profile_build,
                         graph_lock=graph_lock,
                         root_ref=root_ref,
                         build_modes=build_modes,
                         update=update,
                         recorder=recorder)
            out.info("Executing test_package %s" % repr(ref))
            try:
                graph_lock.relax()
                # FIXME: It needs to clear the cache, otherwise it fails
                app.binaries_analyzer._evaluated = {}
                # FIXME: Forcing now not building test dependencies, binaries should be there
                install_build_and_test(app, test_conanfile_path, ref, profile_host, profile_build,
                                       graph_lock, root_ref, remotes, update, build_modes=None,
                                       test_build_folder=test_build_folder, recorder=recorder)
            except Exception as e:
                raise ConanException("Something failed while testing '%s' test_package after "
                                     "it was built using the lockfile. Please report this error: %s"
                                     % (str(ref), str(e)))

        else:
            install_build_and_test(app, test_conanfile_path, ref, profile_host, profile_build,
                                   graph_lock, root_ref, remotes, update,
                                   build_modes=build_modes,
                                   test_build_folder=test_build_folder,
                                   recorder=recorder)
    else:
        deps_install(app=app,
                     ref_or_path=ref,
                     create_reference=ref,
                     install_folder=None,  # Not output infos etc
                     base_folder=None,  # Not output generators
                     remotes=remotes,
                     profile_host=profile_host,
                     profile_build=profile_build,
                     graph_lock=graph_lock,
                     root_ref=root_ref,
                     build_modes=build_modes,
                     update=update,
                     recorder=recorder,
                     is_build_require=is_build_require)
