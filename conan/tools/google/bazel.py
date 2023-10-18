import os
import platform

from conan.tools.google import BazelToolchain


class Bazel(object):

    def __init__(self, conanfile):
        self._conanfile = conanfile

    def build(self, target=None, cli_args=None):
        """
        Runs "bazel <rcpaths> build <configs> <cli_args> <targets>"
        """
        # Use BazelToolchain generated file if exists
        conan_bazelrc = os.path.join(self._conanfile.generators_folder, BazelToolchain.bazelrc_name)
        use_conan_config = os.path.exists(conan_bazelrc)
        bazelrc_paths = []
        bazelrc_configs = []
        if use_conan_config:
            bazelrc_paths.append(conan_bazelrc)
            bazelrc_configs.append(BazelToolchain.bazelrc_config)
        # User bazelrc paths have more prio than Conan one
        # See more info in https://bazel.build/run/bazelrc
        bazelrc_paths.extend(self._conanfile.conf.get("tools.google.bazel:bazelrc_path",
                                                      default=[], check_type=list))
        command = "bazel"
        for rc in bazelrc_paths:
            command += f" --bazelrc='{rc}'"
        command += " build"
        bazelrc_configs.extend(self._conanfile.conf.get("tools.google.bazel:configs",
                                                        default=[], check_type=list))
        for config in bazelrc_configs:
            command += f" --config={config}"
        if cli_args:
            command += " ".join(f" {arg}" for arg in cli_args)
        command += f" {target}"
        self._conanfile.run(command)
        # This is very important for Windows, as otherwise the bazel server locks files
        if platform.system() == "Windows":
            self._conanfile.run("bazel shutdown")

    def test(self, target=None):
        """
        Runs "bazel test <target>"
        """
        if self._conanfile.conf.get("tools.build:skip_test", check_type=bool) or target is None:
            return
        self._conanfile.run(f'bazel test {target}')
