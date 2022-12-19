from conan.tools import _check_duplicated_generator
from conan.tools.files.files import save_toolchain_args


class BazelToolchain(object):

    def __init__(self, conanfile, namespace=None):
        _check_duplicated_generator(self, conanfile)
        self._conanfile = conanfile
        self._namespace = namespace

    def generate(self):
        content = {}
        configs = ",".join(self._conanfile.conf.get("tools.google.bazel:configs",
                                                    default=[],
                                                    check_type=list))
        if configs:
            content["bazel_configs"] = configs

        bazelrc = self._conanfile.conf.get("tools.google.bazel:bazelrc_path")
        if bazelrc:
            content["bazelrc_path"] = bazelrc

        save_toolchain_args(content, namespace=self._namespace)
