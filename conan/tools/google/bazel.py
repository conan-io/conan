import os
import platform

from conan.tools.google import BazelToolchain


class Bazel(object):

    def __init__(self, conanfile):
        self._conanfile = conanfile

    def configure(self, args=None):
        # TODO: Remove in Conan 2.x. Keeping it backward compatible
        pass

    def _safe_run_command(self, command):
        """
        Windows is having problems for stopping bazel processes, so it ends up locking
        some files if something goes wrong. Better to shut down the Bazel server after running
        each command.
        """
        try:
            self._conanfile.run(command)
        finally:
            if platform.system() == "Windows":
                self._conanfile.run("bazel shutdown")

    def build(self, args=None, label=None, target="//..."):
        """
        Runs "bazel <rcpaths> build <configs> <args> <targets>"

        :param label: DEPRECATED: It'll disappear in Conan 2.x. It is the target label
        :param target: It is the target label
        :param args: list of extra arguments
        :return:
        """
        # TODO: Remove in Conan 2.x. Superseded by target
        label = label or target
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
            command += f" --bazelrc={rc}"
        command += " build"
        bazelrc_configs.extend(self._conanfile.conf.get("tools.google.bazel:configs",
                                                        default=[], check_type=list))
        for config in bazelrc_configs:
            command += f" --config={config}"
        if args:
            command += " ".join(f" {arg}" for arg in args)
        command += f" {label}"
        self._safe_run_command(command)

    def test(self, target=None):
        """
        Runs "bazel test <target>"
        """
        if self._conanfile.conf.get("tools.build:skip_test", check_type=bool) or target is None:
            return
        self._safe_run_command(f'bazel test {target}')
