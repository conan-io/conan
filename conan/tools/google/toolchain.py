from conan.tools.files.files import save_toolchain_args


class BazelToolchain(object):

    def __init__(self, conanfile, namespace=None):
        if self.__class__.__name__ in conanfile.generators:
            raise ConanException(f"{self.__class__.__name__} is declared in the generators"
                                 "attribute, but was also instantiated in the generate() method."
                                 "It should only be present in one of them.")
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
