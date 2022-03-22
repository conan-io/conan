from conan.tools.files.files import load_toolchain_args


class Bazel(object):
    def __init__(self, conanfile, namespace=None):
        self._conanfile = conanfile
        self._namespace = namespace
        self._get_bazel_project_configuration()

    def configure(self, args=None):
        pass

    def build(self, args=None, label=None):
        # TODO: Change the directory where bazel builds the project (by default, /var/tmp/_bazel_<username> )

        bazelrc_path = '--bazelrc={}'.format(self._bazelrc_path) if self._bazelrc_path else ''
        bazel_config = " ".join(['--config={}'.format(conf) for conf in self._bazel_config])

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
        toolchain_file_content = load_toolchain_args(self._conanfile.generators_folder,
                                                     namespace=self._namespace)
        configs = toolchain_file_content.get("bazel_configs")
        self._bazel_config = configs.split(",") if configs else []
        self._bazelrc_path = toolchain_file_content.get("bazelrc_path")
