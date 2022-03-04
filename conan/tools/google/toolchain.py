from conan.tools.files.files import save_toolchain_args


class BazelToolchain(object):

    def __init__(self, conanfile, namespace=None):
        self._conanfile = conanfile
        self._namespace = namespace

    def generate(self):
        save_toolchain_args({
            "bazel_config": self._conanfile.conf.get("tools.google.bazel:config"),
            "bazelrc_path": self._conanfile.conf.get("tools.google.bazel:bazelrc_path")
        }, namespace=self._namespace)
