from conans.model import Generator
from conans.paths import CONANENV


class ConanEnvGenerator(Generator):

    @property
    def filename(self):
        return CONANENV

    @property
    def content(self):
        return self.deps_env_info.dumps()
