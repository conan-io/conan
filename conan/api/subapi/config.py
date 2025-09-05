import json
import os

from conan.api.output import ConanOutput

from conan.internal.cache.home_paths import HomePaths
from conan.internal.conan_app import ConanApp
from conan.internal.graph.graph import CONTEXT_HOST, RECIPE_VIRTUAL, Node
from conan.internal.graph.graph_builder import DepsGraphBuilder
from conan.internal.graph.profile_node_definer import consumer_definer
from conan.errors import ConanException
from conan.internal.model.conf import BUILT_IN_CONFS
from conan.internal.model.pkg_type import PackageType
from conan.api.model import RecipeReference, PkgReference
from conan.internal.util.files import load, save, rmdir, remove


class ConfigAPI:
    """ This API provides methods to manage the Conan configuration in the Conan home folder.
    It allows installing configurations from various sources, retrieving global configuration
    values, and listing available configurations. It also provides methods to clean the
    Conan home folder, resetting it to a clean state.
    """

    def __init__(self, conan_api, helpers):
        self._conan_api = conan_api
        self._helpers = helpers

    def home(self):
        """ return the current Conan home folder containing the configuration files like
        remotes, settings, profiles, and the packages cache. It is provided for debugging
        purposes. Recall that it is not allowed to write, modify or remove packages in the
        packages cache, and that to automate tasks that uses packages from the cache Conan
        provides mechanisms like deployers or custom commands.
        """
        return self._conan_api.cache_folder

    def install(self, path_or_url, verify_ssl, config_type=None, args=None,
                source_folder=None, target_folder=None):
        """ install Conan configuration from a git repo, from a zip file in an http server
        or a local folder
        """
        from conan.internal.api.config.config_installer import configuration_install
        cache_folder = self._conan_api.cache_folder
        requester = self._conan_api.remotes.requester
        configuration_install(cache_folder, requester, path_or_url, verify_ssl,
                              config_type=config_type, args=args,
                              source_folder=source_folder, target_folder=target_folder)
        self._conan_api.reinit()

    def install_pkg(self, ref, lockfile=None, force=False, remotes=None,
                    profile=None) -> PkgReference:
        """ install configuration stored inside a Conan package
        The installation of configuration will reinitialize the full ConanAPI
        """
        ConanOutput().warning("The 'conan config install-pkg' is experimental",
                              warn_tag="experimental")
        conan_api = self._conan_api
        remotes = conan_api.remotes.list() if remotes is None else remotes
        profile_host = profile_build = profile or conan_api.profiles.get_profile([])

        app = ConanApp(self._conan_api)

        # Computation of a very simple graph that requires "ref"
        conanfile = app.loader.load_virtual(requires=[RecipeReference.loads(ref)])
        consumer_definer(conanfile, profile_host, profile_build)
        root_node = Node(ref=None, conanfile=conanfile, context=CONTEXT_HOST, recipe=RECIPE_VIRTUAL)
        root_node.is_conf = True
        update = ["*"]
        builder = DepsGraphBuilder(app.proxy, app.loader, app.range_resolver, app.cache, remotes,
                                   update, update, self._helpers.global_conf)
        deps_graph = builder.load_graph(root_node, profile_host, profile_build, lockfile)

        # Basic checks of the package: correct package_type and no-dependencies
        deps_graph.report_graph_error()
        pkg = deps_graph.root.edges[0].dst
        ConanOutput().info(f"Configuration from package: {pkg}")
        if pkg.conanfile.package_type is not PackageType.CONF:
            raise ConanException(f'{pkg.conanfile} is not of package_type="configuration"')
        if pkg.edges:
            raise ConanException(f"Configuration package {pkg.ref} cannot have dependencies")

        # The computation of the "package_id" and the download of the package is done as usual
        # By default we allow all remotes, and build_mode=None, always updating
        conan_api.graph.analyze_binaries(deps_graph, None, remotes, update=update, lockfile=lockfile)
        conan_api.install.install_binaries(deps_graph=deps_graph, remotes=remotes)

        # We check if this specific version is already installed
        config_pref = pkg.pref.repr_notime()
        config_versions = []
        config_version_file = HomePaths(conan_api.home_folder).config_version_path
        if os.path.exists(config_version_file):
            config_versions = json.loads(load(config_version_file))
            config_versions = config_versions["config_version"]
            if config_pref in config_versions:
                if force:
                    ConanOutput().info(f"Package '{pkg}' already configured, "
                                       "but re-installation forced")
                else:
                    ConanOutput().info(f"Package '{pkg}' already configured, "
                                       "skipping configuration install")
                    return pkg.pref  # Already installed, we can skip repeating the install

        from conan.internal.api.config.config_installer import configuration_install
        cache_folder = self._conan_api.cache_folder
        requester = self._conan_api.remotes.requester
        configuration_install(cache_folder, requester, uri=pkg.conanfile.package_folder,
                              verify_ssl=False, config_type="dir",
                              ignore=["conaninfo.txt", "conanmanifest.txt"])
        # We save the current package full reference in the file for future
        # And for ``package_id`` computation
        config_versions = {ref.split("/", 1)[0]: ref for ref in config_versions}
        config_versions[pkg.pref.ref.name] = pkg.pref.repr_notime()
        save(config_version_file, json.dumps({"config_version": list(config_versions.values())}))
        self._conan_api.reinit()
        return pkg.pref

    def get(self, name, default=None, check_type=None):
        """ get the value of a global.conf item
        """
        return self._helpers.global_conf.get(name, default=default, check_type=check_type)

    def show(self, pattern) -> dict:
        """ get the values of global.conf for those configurations that matches the pattern
        """
        return self._helpers.global_conf.show(pattern)

    @staticmethod
    def conf_list():
        """ list all the available built-in configurations
        """
        return BUILT_IN_CONFS.copy()

    def clean(self):
        """ reset the Conan home folder to a clean state, removing all the user
        custom configuration, custom files, and resetting modified files
        """
        contents = os.listdir(self.home())
        packages_folder = (self._helpers.global_conf.get("core.cache:storage_path") or
                           os.path.join(self.home(), "p"))
        for content in contents:
            content_path = os.path.join(self.home(), content)
            if content_path == packages_folder:
                continue
            ConanOutput().debug(f"Removing {content_path}")
            if os.path.isdir(content_path):
                rmdir(content_path)
            else:
                remove(content_path)
        self._conan_api.reinit()
        # CHECK: This also generates a remotes.json that is not there after a conan profile show?
        self._conan_api.migrate()
