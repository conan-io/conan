from conans.client.envvars.environment import env_files, BAT_FLAVOR, PS1_FLAVOR, SH_FLAVOR
from conans.client.tools.oss import OSInfo
from conans.model import Generator


class VirtualEnvGenerator(Generator):
    append_with_spaces = ["CPPFLAGS", "CFLAGS", "CXXFLAGS", "LIBS", "LDFLAGS", "CL", "_LINK_"]
    suffix = ""
    venv_name = "conanenv"

    def __init__(self, conanfile):
        super(VirtualEnvGenerator, self).__init__(conanfile)
        self.conanfile = conanfile
        self.env = conanfile.env
        self.normalize = False

    @property
    def filename(self):
        return

    @property
    def content(self):
        result = {}
        os_info = OSInfo()
        if os_info.is_windows and not os_info.is_posix:
            result.update(env_files(self.env, self.append_with_spaces, BAT_FLAVOR, self.output_path,
                                    self.suffix, self.venv_name))
        result.update(env_files(self.env, self.append_with_spaces, PS1_FLAVOR, self.output_path,
                                self.suffix, self.venv_name))
        result.update(env_files(self.env, self.append_with_spaces, SH_FLAVOR, self.output_path,
                                self.suffix, self.venv_name))
        return result
