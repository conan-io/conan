from conans.model import Generator


class ConanEnvGenerator(Generator):

    @property
    def filename(self):
        return "conanenv.txt"

    @property
    def content(self):
        return self.deps_env_info.dumps()
