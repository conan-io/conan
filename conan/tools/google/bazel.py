import os
import platform

from conan.tools.google import BazelToolchain


class Bazel(object):

    def __init__(self, conanfile, namespace=None):
        self._conanfile = conanfile
        # TODO: Remove namespace in Conan 2.x
        if namespace:
            self._conanfile.output.warning("In Bazel() call, namespace param has been "
                                           "deprecated as it's not used anymore.")

    def configure(self, args=None):
        # TODO: Remove in Conan 2.x. Keeping it backward compatible
        self._conanfile.output.warning("Bazel.configure() function has been deprecated."
                                       " Removing in Conan 2.x.")
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

    def build(self, args=None, label=None, target="//...", clean=True):
        """
        Runs "bazel <rcpaths> build <configs> <args> <targets>"

        :param label: DEPRECATED: It'll disappear in Conan 2.x. It is the target label
        :param target: It is the target label
        :param args: list of extra arguments
        :param clean: bool that indicates to run a "bazel clean" before running the "bazel build".
                      Notice that this is important to ensure a fresh bazel cache.
        :return:
        """
        # TODO: Remove in Conan 2.x. Superseded by target
        if label:
            self._conanfile.output.warning("In Bazel.build() call, label param has been deprecated."
                                        " Migrating to target.")
            target = label
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
        # TODO: Legacy Bazel allowed only one value. Remove for Conan 2.x and check list-type.
        rc_paths = self._conanfile.conf.get("tools.google.bazel:bazelrc_path", default=[])
        rc_paths = [rc_paths.strip()] if isinstance(rc_paths, str) else rc_paths
        bazelrc_paths.extend(rc_paths)
        command = "bazel"
        for rc in bazelrc_paths:
            rc = rc.replace("\\", "/")
            command += f" --bazelrc={rc}"
        command += " build"
        # TODO: Legacy Bazel allowed only one value or several ones separate by commas.
        #       Remove for Conan 2.x and check list-type.
        configs = self._conanfile.conf.get("tools.google.bazel:configs", default=[])
        configs = [c.strip() for c in configs.split(",")] if isinstance(configs, str) else configs
        bazelrc_configs.extend(configs)
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
