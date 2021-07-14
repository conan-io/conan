from conan.tools._check_build_profile import check_using_build_profile
from conan.tools.files import save_toolchain_args


class BazelToolchain(object):

    def __init__(self, conanfile):
        self._conanfile = conanfile
        check_using_build_profile(self._conanfile)

    def generate(self):
        save_toolchain_args({
            "bazel_config": self._conanfile.conf["tools.google.bazel:config"],
            "bazelrc_path": self._conanfile.conf["tools.google.bazel:bazelrc_path"]
        })
