import os
import platform

from conan.tools.google import BazelToolchain


class Bazel(object):

    def __init__(self, conanfile):
        self._conanfile = conanfile

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

    def build(self, args=None, target="//...", clean=True):
        """
        Runs "bazel <rcpaths> build <configs> <args> <targets>"

        :param target: It is the target label
        :param args: list of extra arguments
        :param clean: bool that indicates to run a "bazel clean" before running the "bazel build".
                      Notice that this is important to ensure a fresh bazel cache.
        :return:
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
        bazelrc_paths.extend(self._conanfile.conf.get("tools.google.bazel:bazelrc_path", default=[],
                                                      check_type=list))
        command = "bazel"
        for rc in bazelrc_paths:
            rc = rc.replace("\\", "/")
            command += f" --bazelrc={rc}"
        command += " build"
        bazelrc_configs.extend(self._conanfile.conf.get("tools.google.bazel:configs", default=[],
                                                        check_type=list))
        for config in bazelrc_configs:
            command += f" --config={config}"
        if args:
            command += " ".join(f" {arg}" for arg in args)
        command += f" {target}"
        if clean:
            self._safe_run_command("bazel clean")
        self._safe_run_command(command)

    def test(self, target=None):
        """
        Runs "bazel test <target>"
        """
        if self._conanfile.conf.get("tools.build:skip_test", check_type=bool) or target is None:
            return
        self._safe_run_command(f'bazel test {target}')
