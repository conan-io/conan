import os
import json

from conan.tools import CONAN_TOOLCHAIN_ARGS_FILE
from conans.util.files import load

class Bazel(object):
    def __init__(self, conanfile):
        self._conanfile = conanfile
        self._get_bazel_project_configuration()

    def configure(self, args=None):
        pass

    def build(self, args=None, label=None):
        # TODO: Change the directory where bazel builds the project (by default, /var/tmp/_bazel_<username> )

        bazelrc_path = '--bazelrc={}'.format(self._bazelrc_path) if self._bazelrc_path else ''
        bazel_config = '--config={}'.format(self._bazel_config) if self._bazel_config else ''

        # arch = self._conanfile.settings.get_safe("arch")
        # cpu = {
        #     "armv8": "arm64",
        #     "x86_64": ""
        # }.get(arch, arch)
        #
        # command = 'bazel {} build --sandbox_debug --subcommands=pretty_print --cpu={} {} {}'.format(
        #     bazelrc_path,
        #     cpu,
        #     bazel_config,
        #     label
        # )

        command = 'bazel {} build {} {}'.format(
            bazelrc_path,
            bazel_config,
            label
        )

        self._conanfile.run(command)

    def _get_bazel_project_configuration(self):
        self._bazel_config = None
        self._bazelrc_path = None

        if os.path.exists(CONAN_TOOLCHAIN_ARGS_FILE):
            conan_toolchain_args = json.loads(load(CONAN_TOOLCHAIN_ARGS_FILE))
            self._bazel_config = conan_toolchain_args.get("bazel_config", None)
            self._bazelrc_path = conan_toolchain_args.get("bazelrc_path", None)
