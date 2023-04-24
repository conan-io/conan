import os

from conan.api.output import ConanOutput

EXTENSIONS_FOLDER = "extensions"


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
