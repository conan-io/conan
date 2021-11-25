import os

from conans import ConanFile
from conans.cli.api.subapi import api_method
from conans.cli.common import get_lockfile
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
from conans.model.recipe_ref import RecipeReference


class InstallAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    @api_method
    def install_binaries(self, deps_graph, install_folder, base_folder, conanfile_folder,
                         build_modes=None, generators=None, no_imports=False, create_reference=None,
                         remote=None, update=False, test=None):
        """ Install binaries for dependency graph
        @param deps_graph: Dependency graph to intall packages for
        @param install_folder:
        @param base_folder: Tipically current folder
        @param conanfile_folder: Folder where the conanfile is located
        @param build_modes:
        @param generators:
        @param no_imports:
        @param create_reference:
        @param remote:
        @param update:
        @param test:
        """
        app = ConanApp(self.conan_api.cache_folder)

        remote = [remote] if remote is not None else None
        app.load_remotes(remote, update=update)

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

        root_node = deps_graph.root
        conanfile = root_node.conanfile

        if hasattr(conanfile, "layout") and not test:
            conanfile.folders.set_base_install(conanfile_folder)
            conanfile.folders.set_base_imports(conanfile_folder)
            conanfile.folders.set_base_generators(conanfile_folder)
        else:
            conanfile.folders.set_base_install(install_folder)
            conanfile.folders.set_base_imports(install_folder)
            conanfile.folders.set_base_generators(base_folder)

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

    # maybe this is not wanted as API method, for the moment just leaving this to not
    # explode things too much
    @api_method
    def install(self, path="", reference="", name=None, version=None, user=None, channel=None,
                profile_host=None, profile_build=None, remote=None, build=None, update=False,
                generators=None, no_imports=False, install_folder=None, lockfile_in=None,
                lockfile_out=None, is_build_require=None, require_overrides=None):

        if reference and (name or version or user or channel):
            raise ConanException("Can't use --name, --version, --user or --channel arguments with "
                                 "--reference")

        cwd = os.getcwd()
        lockfile_path = _make_abs_path(lockfile_in, cwd) if lockfile_in else None

        lockfile = get_lockfile(lockfile=lockfile_path)

        root_ref = RecipeReference(name, version, user, channel)

        # Make lockfile strict for consuming and install
        if lockfile is not None:
            lockfile.strict = True

        install_folder = _make_abs_path(install_folder, cwd)
        conanfile_folder = os.path.dirname(path) if path else None

        # deps_install is replaced by APIV2.graph.load_graph + APIV2.install.install_binaries
        deps_graph = self.conan_api.graph.load_graph(reference=reference,
                                                     path=path,
                                                     profile_host=profile_host,
                                                     profile_build=profile_build,
                                                     lockfile=lockfile,
                                                     root_ref=root_ref,
                                                     build_modes=build,
                                                     is_build_require=is_build_require,
                                                     require_overrides=require_overrides,
                                                     remote=remote, update=update)

        self.install_binaries(deps_graph=deps_graph, install_folder=install_folder, base_folder=cwd,
                              conanfile_folder=conanfile_folder, build_modes=build,
                              generators=generators, no_imports=no_imports, remote=remote,
                              update=update)

        if lockfile_out:
            lockfile_out = _make_abs_path(lockfile_out, cwd)
            lockfile.save(lockfile_out)
