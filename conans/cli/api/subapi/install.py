import os

from conans import ConanFile
from conans.cli.api.model import Remote
from conans.cli.api.subapi import api_method
from conans.cli.conan_app import ConanApp
from conans.cli.output import ConanOutput
from conans.client.conan_api import _make_abs_path
from conans.client.generators import write_generators
from conans.client.graph.build_mode import BuildMode
from conans.client.graph.graph import RECIPE_VIRTUAL
from conans.client.graph.printer import print_graph
from conans.client.importer import run_imports, run_deploy
from conans.client.installer import BinaryInstaller, call_system_requirements
from conans.errors import ConanException
from conans.model.graph_lock import LOCKFILE, Lockfile
from conans.model.recipe_ref import RecipeReference


def get_graph_info(name=None, version=None, user=None, channel=None, lockfile=None):
    root_ref = RecipeReference(name, version, user, channel)

    graph_lock = None
    if lockfile:
        lockfile = lockfile if os.path.isfile(lockfile) else os.path.join(lockfile, LOCKFILE)
        graph_lock = Lockfile.load(lockfile)
        ConanOutput().info("Using lockfile: '{}'".format(lockfile))

    return graph_lock, root_ref


class InstallAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    @api_method
    def install_binaries(self, deps_graph, install_folder,
                         build_modes=None, generators=None, no_imports=False, create_reference=None,
                         remote_name=None, update=False):
        """ Install binaries for dependency graph
        @param deps_graph: Dependency graphs
        """
        app = ConanApp(self.conan_api.cache_folder)
        # FIXME: remote_name should be remote
        app.load_remotes([Remote(remote_name, None)], update=update)

        out = ConanOutput()

        root_node = deps_graph.root
        conanfile = root_node.conanfile

        # TODO: maybe we want a way to get this directly from the DepsGraph?
        reference = deps_graph.nodes[1] if root_node.recipe == RECIPE_VIRTUAL else None

        if root_node.recipe == RECIPE_VIRTUAL:
            out.highlight("Installing package: %s" % str(reference))
        else:
            conanfile.output.highlight("Installing package")
        print_graph(deps_graph)

        installer = BinaryInstaller(app)
        # TODO: Extract this from the GraphManager, reuse same object, check args earlier
        build_modes = BuildMode(build_modes)
        installer.install(deps_graph, build_modes)

        if install_folder:
            # Write generators
            tmp = list(conanfile.generators)  # Add the command line specified generators
            generators = set(generators) if generators else set()
            tmp.extend([g for g in generators if g not in tmp])
            conanfile.generators = tmp
            write_generators(conanfile)

            if not no_imports:
                run_imports(conanfile)
            if type(conanfile).system_requirements != ConanFile.system_requirements:
                call_system_requirements(conanfile)

            if not create_reference and reference:
                # The conanfile loaded is a virtual one. The one w deploy is the first level one
                neighbours = deps_graph.root.neighbors()
                deploy_conanfile = neighbours[0].conanfile
                if hasattr(deploy_conanfile, "deploy") and callable(deploy_conanfile.deploy):
                    run_deploy(deploy_conanfile, install_folder)

        return deps_graph

    @api_method
    def install(self, path="", reference="", name=None, version=None, user=None, channel=None,
                profile_host=None, profile_build=None, remote_name=None, build=None, update=False,
                generators=None, no_imports=False, install_folder=None, lockfile=None,
                lockfile_out=None, is_build_require=None, require_overrides=None):

        if path and reference:
            raise ConanException("Both path and reference arguments were provided. Please provide "
                                 "only one of them")

        if reference and (name or version or user or channel):
            raise ConanException("Can't use --name, --version, --user or --channel arguments with "
                                 "--reference")

        cwd = os.getcwd()
        lockfile = _make_abs_path(lockfile, cwd) if lockfile else None

        graph_lock, root_ref = get_graph_info(name=name,
                                              version=version,
                                              user=user,
                                              channel=channel,
                                              lockfile=lockfile)

        # Make lockfile strict for consuming and install
        if graph_lock is not None:
            graph_lock.strict = True

        install_folder = _make_abs_path(install_folder, cwd)

        # deps_install is replaced by APIV2.graph.load_graph + APIV2.install.install_binaries
        deps_graph = self.conan_api.graph.load_graph(reference=reference,
                                                     path=path,
                                                     profile_host=profile_host,
                                                     profile_build=profile_build,
                                                     graph_lock=graph_lock,
                                                     root_ref=root_ref,
                                                     install_folder=install_folder,
                                                     base_folder=cwd,
                                                     build_modes=build,
                                                     is_build_require=is_build_require,
                                                     require_overrides=require_overrides,
                                                     remote_name=remote_name, update=update)

        self.install_binaries(deps_graph=deps_graph, install_folder=install_folder,
                              build_modes=build, generators=generators, no_imports=no_imports,
                              remote_name=remote_name, update=update)

        if lockfile_out:
            lockfile_out = _make_abs_path(lockfile_out, cwd)
            graph_lock.save(lockfile_out)
