import os
import platform
import textwrap
import yaml
from jinja2 import Environment, FileSystemLoader

from conan import conan_version
from conans.client.conf import default_settings_yml
from conan.internal.api import detect_api
from conan.internal.cache.home_paths import HomePaths
from conan.internal.conan_app import ConanApp
from conans.client.graph.graph import CONTEXT_HOST, RECIPE_VIRTUAL, Node
from conans.client.graph.graph_builder import DepsGraphBuilder
from conans.client.graph.profile_node_definer import consumer_definer
from conans.errors import ConanException
from conans.model.conf import ConfDefinition, BUILT_IN_CONFS
from conans.model.pkg_type import PackageType
from conans.model.recipe_ref import RecipeReference
from conans.model.settings import Settings
from conans.util.files import load, save


class ConfigAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api
        self._new_config = None

    def home(self):
        return self.conan_api.cache_folder

    def install(self, path_or_url, verify_ssl, config_type=None, args=None,
                source_folder=None, target_folder=None):
        # TODO: We probably want to split this into git-folder-http cases?
        from conans.client.conf.config_installer import configuration_install
        app = ConanApp(self.conan_api)
        configuration_install(app, path_or_url, verify_ssl, config_type=config_type, args=args,
                              source_folder=source_folder, target_folder=target_folder)

    def install_pkg(self, ref):
        conan_api = self.conan_api
        remotes = conan_api.remotes.list()  # ready to use remotes arguments
        lockfile = None  # Ready to pass a lockfile if we want and use it
        # Ready to use profiles as inputs
        profile_host = profile_build = conan_api.profiles.get_profile([])

        app = ConanApp(self.conan_api)
        conanfile = app.loader.load_virtual(requires=[RecipeReference.loads(ref)])
        consumer_definer(conanfile, profile_build, profile_host)
        root_node = Node(ref=None, conanfile=conanfile, context=CONTEXT_HOST, recipe=RECIPE_VIRTUAL)
        remotes = remotes or []
        update = ["*"]
        builder = DepsGraphBuilder(app.proxy, app.loader, app.range_resolver, app.cache, remotes,
                                   update, update, self.conan_api.config.global_conf,
                                   no_conf=False)
        deps_graph = builder.load_graph(root_node, profile_host, profile_build, lockfile)
        deps_graph.report_graph_error()
        pkg = deps_graph.root.dependencies[0].dst
        if pkg.conanfile.package_type is not PackageType.CONF:
            raise ConanException(f'{pkg.conanfile} is not of package_type="configuration"')
        if pkg.dependencies:
            raise ConanException(f"Configuration package {pkg.ref} cannot have dependencies")

        conan_api.graph.analyze_binaries(deps_graph, None, remotes, update=update, lockfile=lockfile)
        conan_api.install.install_binaries(deps_graph=deps_graph, remotes=remotes)

        # We check if this specific version is already installed
        config_pref = pkg.pref.repr_notime()
        config_version_file = HomePaths(conan_api.home_folder).config_version_path
        if os.path.exists(config_version_file):
            version = load(config_version_file)
            if version == config_pref:
                print("EQUAL TO THE PREVIOUS ONE ", repr(config_pref))
                return  # Already installed, we can skip repeating the install

        uri = pkg.conanfile.package_folder
        config_type = "dir"
        from conans.client.conf.config_installer import configuration_install
        app = ConanApp(self.conan_api)
        configuration_install(app, uri, verify_ssl=False, config_type=config_type,
                              ignore=["conaninfo.txt", "conanmanifest.txt"])
        save(config_version_file, config_pref)

    def get(self, name, default=None, check_type=None):
        return self.global_conf.get(name, default=default, check_type=check_type)

    def show(self, pattern):
        return self.global_conf.show(pattern)

    @property
    def global_conf(self):
        """ this is the new global.conf to replace the old conan.conf that contains
        configuration defined with the new syntax as in profiles, this config will be composed
        to the profile ones and passed to the conanfiles.conf, which can be passed to collaborators
        """
        if self._new_config is None:
            cache_folder = self.conan_api.cache_folder
            self._new_config = self.load_config(cache_folder)
        return self._new_config

    @staticmethod
    def load_config(home_folder):
        # Do not document yet, keep it private
        home_paths = HomePaths(home_folder)
        global_conf_path = home_paths.global_conf_path
        new_config = ConfDefinition()
        if os.path.exists(global_conf_path):
            text = load(global_conf_path)
            distro = None
            if platform.system() in ["Linux", "FreeBSD"]:
                import distro
            template = Environment(loader=FileSystemLoader(home_folder)).from_string(text)
            content = template.render({"platform": platform, "os": os, "distro": distro,
                                       "conan_version": conan_version,
                                       "conan_home_folder": home_folder,
                                       "detect_api": detect_api})
            new_config.loads(content)
        else:  # creation of a blank global.conf file for user convenience
            default_global_conf = textwrap.dedent("""\
                # Core configuration (type 'conan config list' to list possible values)
                # e.g, for CI systems, to raise if user input would block
                # core:non_interactive = True
                # some tools.xxx config also possible, though generally better in profiles
                # tools.android:ndk_path = my/path/to/android/ndk
                """)
            save(global_conf_path, default_global_conf)
        return new_config

    @property
    def builtin_confs(self):
        return BUILT_IN_CONFS

    @property
    def settings_yml(self):
        """Returns {setting: [value, ...]} defining all the possible
                   settings without values"""
        _home_paths = HomePaths(self.conan_api.cache_folder)
        settings_path = _home_paths.settings_path
        if not os.path.exists(settings_path):
            save(settings_path, default_settings_yml)
            save(settings_path + ".orig", default_settings_yml)  # stores a copy, to check migrations

        def _load_settings(path):
            try:
                return yaml.safe_load(load(path)) or {}
            except yaml.YAMLError as ye:
                raise ConanException("Invalid settings.yml format: {}".format(ye))

        settings = _load_settings(settings_path)
        user_settings_file = _home_paths.settings_path_user
        if os.path.exists(user_settings_file):
            settings_user = _load_settings(user_settings_file)

            def appending_recursive_dict_update(d, u):
                # Not the same behavior as conandata_update, because this append lists
                for k, v in u.items():
                    if isinstance(v, list):
                        current = d.get(k) or []
                        d[k] = current + [value for value in v if value not in current]
                    elif isinstance(v, dict):
                        current = d.get(k) or {}
                        if isinstance(current, list):  # convert to dict lists
                            current = {k: None for k in current}
                        d[k] = appending_recursive_dict_update(current, v)
                    else:
                        d[k] = v
                return d

            appending_recursive_dict_update(settings, settings_user)

        return Settings(settings)
