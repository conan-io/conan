import os

from conan.api.output import ConanOutput

EXTENSIONS_FOLDER = "extensions"
HOOKS_EXTENSION_FOLDER = "hooks"
PROFILES_FOLDER = "profiles"
REMOTES = "remotes.json"
CONAN_SETTINGS = "settings.yml"


class HomePaths:
    """ pure computing of paths in the home, not caching anything
    """
    def __init__(self, home_folder):
        self._home = home_folder

    @property
    def custom_commands_path(self):
        return os.path.join(self._home, EXTENSIONS_FOLDER, "commands")

    @property
    def deployers_path(self):
        deploy = os.path.join(self._home, EXTENSIONS_FOLDER, "deploy")
        if os.path.exists(deploy):
            ConanOutput().warning("Use 'deployers' cache folder for deployers instead of 'deploy'",
                                  warn_tag="deprecated")
            return deploy
        return os.path.join(self._home, EXTENSIONS_FOLDER, "deployers")

    @property
    def custom_generators_path(self):
        return os.path.join(self._home, EXTENSIONS_FOLDER, "generators")

    @property
    def hooks_path(self):
        return os.path.join(self._home, EXTENSIONS_FOLDER, HOOKS_EXTENSION_FOLDER)

    @property
    def wrapper_path(self):
        return os.path.join(self._home, "extensions", "plugins", "cmd_wrapper.py")

    @property
    def profiles_path(self):
        return os.path.join(self._home, PROFILES_FOLDER)

    @property
    def profile_plugin_path(self):
        return os.path.join(self._home, "extensions", "plugins", "profile.py")

    @property
    def sign_plugin_path(self):
        return os.path.join(self._home, "extensions", "plugins", "sign", "sign.py")

    @property
    def remotes_path(self):
        return os.path.join(self._home, REMOTES)

    @property
    def compatibility_plugin_path(self):
        return os.path.join(self._home, "extensions", "plugins", "compatibility")

    @property
    def default_sources_backup_folder(self):
        return os.path.join(self._home, "sources")

    @property
    def settings_path(self):
        return os.path.join(self._home, CONAN_SETTINGS)

    @property
    def settings_path_user(self):
        return os.path.join(self._home, "settings_user.yml")
