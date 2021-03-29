import platform

from conan.tools.env import VirtualEnv
from conan.tools.gnu import AutotoolsToolchain, AutotoolsDeps


class AutotoolsGen:
    def __init__(self, conanfile):
        self.toolchain = AutotoolsToolchain(conanfile)
        self.deps = AutotoolsDeps(conanfile)
        self.env = VirtualEnv(conanfile)

    def build_environment(self):
        envtoolchain = self.toolchain.environment()
        envdeps = self.deps.environment()
        build_env = self.env.build_environment()
        build_env.compose(envtoolchain)
        build_env.compose(envdeps)
        return build_env

    def run_environment(self):
        run_env = self.env.run_environment()
        return run_env

    def generate(self):
        build_env = self.build_environment()
        run_env = self.run_environment()
        # FIXME: Use settings, not platform Not always defined :(
        # os_ = self._conanfile.settings_build.get_safe("os")
        if platform.system() == "Windows":
            build_env.save_bat("conanbuildenv.bat")
            run_env.save_bat("conanrunenv.bat")
        else:
            build_env.save_sh("conanbuildenv.sh")
            run_env.save_sh("conanrunenv.sh")
