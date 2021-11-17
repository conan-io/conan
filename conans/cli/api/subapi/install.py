import os

from conans.cli.api.model import Remote
from conans.cli.api.subapi import api_method
from conans.cli.conan_app import ConanApp
from conans.client.conan_api import _make_abs_path, get_graph_info
from conans.client.manager import deps_install
from conans.errors import ConanException


class InstallAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    @api_method
    def install(self, path="", reference="",
                profile_host=None, profile_build=None,
                remote_name=None, build=None,
                update=False, generators=None, no_imports=False, install_folder=None,
                lockfile=None, lockfile_out=None, is_build_require=None,
                require_overrides=None):

        if path and reference:
            raise ConanException("Both path and reference arguments were provided. Please provide "
                                 "only one of them")

        if not reference and ".txt" not in path and ".py" not in path:
            raise ConanException("Please, add the full path to the conanfile with the filename "
                                 "and extension")

        app = ConanApp(self.conan_api.cache_folder)
        # FIXME: remote_name should be remote
        app.load_remotes([Remote(remote_name, None)], update=update)

        cwd = os.getcwd()
        try:
            lockfile = _make_abs_path(lockfile, cwd) if lockfile else None
            profile_host, profile_build, graph_lock, root_ref = get_graph_info(profile_host,
                                                                               profile_build, cwd,
                                                                               app.cache,
                                                                               lockfile=lockfile)

            # Make lockfile strict for consuming and install
            if graph_lock is not None:
                graph_lock.strict = True

            install_folder = _make_abs_path(install_folder, cwd)

            deps_install(app=app,
                         ref_or_path=path or reference,
                         install_folder=install_folder,
                         base_folder=cwd,
                         profile_host=profile_host,
                         profile_build=profile_build,
                         graph_lock=graph_lock,
                         root_ref=root_ref,
                         build_modes=build,
                         generators=generators,
                         no_imports=no_imports,
                         require_overrides=require_overrides,
                         is_build_require=is_build_require)

            if lockfile_out:
                lockfile_out = _make_abs_path(lockfile_out, cwd)
                graph_lock.save(lockfile_out)
        except ConanException as exc:
            raise
