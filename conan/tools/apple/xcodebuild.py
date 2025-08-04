from conan.tools.apple.apple import to_apple_arch, xcodebuild_deployment_target_key


class XcodeBuild(object):
    def __init__(self, conanfile, use_build_folder=False):
        """
        :param conanfile: The current recipe object. Always use ``self``.
        :param use_build_folder: If build files/artifacts should be placed in ``self.build_folder``.
                                 If ``False``, by default they will be placed in the directory of Xcode project.
        """
        self._conanfile = conanfile
        self._build_type = conanfile.settings.get_safe("build_type")
        self._arch = to_apple_arch(self._conanfile)
        self._sdk = conanfile.settings.get_safe("os.sdk") or ""
        self._sdk_version = conanfile.settings.get_safe("os.sdk_version") or ""
        self._os = conanfile.settings.get_safe("os")
        self._os_version = conanfile.settings.get_safe("os.version")
        self._use_build_folder = use_build_folder

    @property
    def _verbosity(self):
        verbosity = self._conanfile.conf.get("tools.build:verbosity", choices=("quiet", "verbose")) \
                    or self._conanfile.conf.get("tools.compilation:verbosity",
                                                choices=("quiet", "verbose"))
        return "-" + verbosity if verbosity is not None else ""

    @property
    def _sdkroot(self):
        # User's sdk_path has priority, then if specified try to compose sdk argument
        # with sdk/sdk_version settings, leave blank otherwise and the sdk will be automatically
        # chosen by the build system
        sdk = self._conanfile.conf.get("tools.apple:sdk_path")
        if not sdk and self._sdk:
            sdk = "{}{}".format(self._sdk, self._sdk_version)
        return "SDKROOT={}".format(sdk) if sdk else ""

    def build(self, xcodeproj, target=None, configuration=None, build_options=None):
        """
        Call to ``xcodebuild`` to build a Xcode project.

        :param xcodeproj: the *xcodeproj* file to build.
        :param target: the target to build, in case this argument is passed to the ``build()``
                       method it will add the ``-target`` argument to the build system call. If not passed, it
                       will build all the targets passing the ``-alltargets`` argument instead.
        :param configuration: the configuration to build, defaults to profile's ``settings.build_type``.
        :param build_options: arbitrary options (list of strings) to be passed to ``xcodebuild`` as is.
        :return: the return code for the launched ``xcodebuild`` command.
        """
        target = "-target '{}'".format(target) if target else "-alltargets"
        build_config = configuration or self._build_type
        cmd = "xcodebuild -project '{}' -configuration {} -arch {} " \
              "{} {} {}".format(xcodeproj, build_config, self._arch,
                                self._sdkroot, self._verbosity, target)
        if self._use_build_folder:
            cmd += f" SYMROOT='{self._conanfile.build_folder}' OBJROOT='{self._conanfile.build_folder}'"

        deployment_target_key = xcodebuild_deployment_target_key(self._os)
        if deployment_target_key and self._os_version:
            cmd += f" {deployment_target_key}={self._os_version}"

        cmd += f" {' '.join(build_options or [])}"
        self._conanfile.run(cmd)
