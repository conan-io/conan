import json
import os

from conan.api.output import ConanOutput

from conan.internal.cache.home_paths import HomePaths
from conan.internal.conan_app import ConanApp
from conan.internal.graph.graph import CONTEXT_HOST, RECIPE_VIRTUAL, Node
from conan.internal.graph.graph_builder import DepsGraphBuilder
from conan.internal.graph.profile_node_definer import consumer_definer
from conan.errors import ConanException

from conan.internal.model.conanconfig import loadconanconfig
from conan.internal.model.conf import BUILT_IN_CONFS
from conan.internal.model.pkg_type import PackageType
from conan.api.model import RecipeReference, PkgReference
from conan.internal.util.files import save, rmdir, remove


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
        requester = self._helpers.requester
        configuration_install(cache_folder, requester, path_or_url, verify_ssl,
                              config_type=config_type, args=args,
                              source_folder=source_folder, target_folder=target_folder)
        self._conan_api.reinit()

    def install_pkg(self, require, lockfile=None, force=False, remotes=None, profile=None):
        ref = self._install_pkg(require, lockfile, force, remotes, profile)
        self._conan_api.reinit()
        return ref

    def install_pkg_file(self, path, lockfile=None, force=False, remotes=None, profile=None):
        if os.path.isdir(path):
            path = os.path.join(path, "conanconfig.json")
        requires = loadconanconfig(path)
        refs = self._handle_reqs(requires, force)
        for require in requires:
            ref = self._install_pkg(require, lockfile, force, remotes, profile)
            refs.append(ref)
        self._conan_api.reinit()
        return refs

    def _handle_reqs(self, requires, force):
        config_version_file = HomePaths(self._conan_api.home_folder).config_version_path
        if not os.path.exists(config_version_file):
            return requires
        config_versions = loadconanconfig(config_version_file)
        config_versions_dict = {r.name: r for r in config_versions}
        if len(config_versions_dict) < len(config_versions):
            raise ConanException("There are multiple requirerements for the same package "
                                 f"with different versions: {config_version_file}")
        result = []
        for require in requires:
            existing = config_versions_dict.get(require.name)
            if not existing:
                result.append(require)
                continue
            if existing == require:
                if force:
                    ConanOutput().info(f"Package '{require}' already configured, "
                                       "but re-installation forced. It is recommended to do a "
                                       "'conan config clean' before.")
                    result.append(require)
                else:
                    ConanOutput().info(f"Package '{require}' already configured, "
                                       "skipping configuration install")
            else:
                if force:
                    ConanOutput().warning(f"Package '{existing}' already configured, forced "
                                          f"installation of '{require} on top. "
                                          f"Recommended a 'conan config clean' before")
                    result.append(require)
                else:
                    raise ConanException(f"Package '{existing}' already configured, but tried "
                                         f"to install '{require}. Do a 'conan config clean' before")
        return result

    def _install_pkg(self, ref, lockfile=None, force=False, remotes=None,
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
        config_pref = pkg.ref.repr_notime()
        xxxx

        from conan.internal.api.config.config_installer import configuration_install
        cache_folder = self._conan_api.cache_folder
        requester = self._helpers.requester
        configuration_install(cache_folder, requester, uri=pkg.conanfile.package_folder,
                              verify_ssl=False, config_type="dir",
                              ignore=["conaninfo.txt", "conanmanifest.txt"])
        # We save the current reference in the file for future
        # To make it latest
        # Not two references for the same package name are allowed, they are assumed to overwrite
        # the previous one. So if pkg1/0.1 exists and pkg1/0.2 is installed, then the later one
        # overwrites the previous one, and also changes the order, being latest in the list
        # But that changes the "package_id" if there are multiple packages, not great
        config_versions = [c for c in config_versions if c.split("/", 1)[0] != pkg.ref.name]
        config_versions.append(pkg.ref.repr_notime())
        save(config_version_file, json.dumps({"config_version": config_versions}))
        return pkg.ref

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

    @property
    def settings_yml(self):
        """ Get the contents of the settings.yml and user_settings.yml files,
            which define the possible values for settings.

            Note that this is different from the settings present in a conanfile,
            which represent the actual values for a specific package, while this
            property represents the possible values for each setting.

            :returns: A read-only object representing the settings scheme, with a
                ``possible_values()`` method that returns a dictionary with the possible values for each setting,
                and a ``fields`` property that returns an ordered list with the fields of each setting.
                Note that it's possible to access nested settings using attribute access,
                such as ``settings_yml.compiler.possible_values()``.
        """

        class SettingsYmlInterface:
            def __init__(self, settings):
                self._settings = settings

            def possible_values(self):
                """ returns a dict with the possible values for each setting """
                return self._settings.possible_values()

            @property
            def fields(self):
                """ returns a dict with the fields of each setting """
                return self._settings.fields

            def __getattr__(self, item):
                return SettingsYmlInterface(getattr(self._settings, item))

            def __str__(self):
                return str(self._settings)

        return SettingsYmlInterface(self._helpers.settings_yml)
