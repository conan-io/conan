import os

from conans.cli.api.model import Remote
from conans.cli.api.subapi import api_method
from conans.cli.conan_app import ConanApp
from conans.client.cache.cache import ClientCache
from conans.client.conan_api import ProfileData, _make_abs_path, get_graph_info, _get_conanfile_path
from conans.client.manager import deps_install
from conans.errors import ConanException
from conans.util.files import mkdir


class InstallAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    @api_method
    def install_reference(self, reference, settings=None, options=None, env=None,
                          remote_name=None, build=None, profile_names=None,
                          update=False, generators=None, install_folder=None, cwd=None,
                          lockfile=None, lockfile_out=None, profile_build=None,
                          is_build_require=False, conf=None,
                          require_overrides=None):
        app = ConanApp(self.conan_api.cache_folder)
        # FIXME: remote_name should be remote
        app.load_remotes([Remote(remote_name, None)], update=update)
        profile_host = ProfileData(profiles=profile_names, settings=settings, options=options,
                                   env=env, conf=conf)

        cwd = cwd or os.getcwd()
        try:
            lockfile = _make_abs_path(lockfile, cwd) if lockfile else None
            profile_host, profile_build, graph_lock, root_ref = get_graph_info(profile_host,
                                                                               profile_build, cwd,
                                                                               app.cache,
                                                                               lockfile=lockfile)

            if graph_lock is not None:
                graph_lock.strict = True
            install_folder = _make_abs_path(install_folder, cwd)

            mkdir(install_folder)
            deps_install(app, ref_or_path=reference, install_folder=install_folder, base_folder=cwd,
                         profile_host=profile_host, profile_build=profile_build,
                         graph_lock=graph_lock, root_ref=root_ref, build_modes=build,
                         generators=generators,
                         is_build_require=is_build_require,
                         require_overrides=require_overrides)

            if lockfile_out:
                lockfile_out = _make_abs_path(lockfile_out, cwd)
                graph_lock.save(lockfile_out)
        except ConanException as exc:
            raise

    @api_method
    def install(self, path="", name=None, version=None, user=None, channel=None,
                settings=None, options=None, env=None,
                remote_name=None, build=None, profile_names=None,
                update=False, generators=None, no_imports=False, install_folder=None, cwd=None,
                lockfile=None, lockfile_out=None, profile_build=None, conf=None,
                require_overrides=None):
        app = ConanApp(self.conan_api.cache_folder)
        # FIXME: remote_name should be remote
        app.load_remotes([Remote(remote_name, None)], update=update)
        profile_host = ProfileData(profiles=profile_names, settings=settings, options=options,
                                   env=env, conf=conf)

        cwd = cwd or os.getcwd()
        try:
            lockfile = _make_abs_path(lockfile, cwd) if lockfile else None
            profile_host, profile_build, graph_lock, root_ref = get_graph_info(profile_host,
                                                                               profile_build, cwd,
                                                                               app.cache,
                                                                               name=name,
                                                                               version=version,
                                                                               user=user,
                                                                               channel=channel,
                                                                               lockfile=lockfile)

            install_folder = _make_abs_path(install_folder, cwd)
            conanfile_path = _get_conanfile_path(path, cwd, py=None)

            # Make lockfile strict for consuming and install
            if graph_lock is not None:
                graph_lock.strict = True
            deps_install(app=app,
                         ref_or_path=conanfile_path,
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
                         conanfile_path=os.path.dirname(conanfile_path))

            if lockfile_out:
                lockfile_out = _make_abs_path(lockfile_out, cwd)
                graph_lock.save(lockfile_out)
        except ConanException as exc:
            raise
