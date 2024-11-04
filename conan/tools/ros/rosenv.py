import os
from conan.api.output import Color
from conan.tools.env import VirtualBuildEnv, Environment
from conan.tools.env.environment import create_env_script
from conan.tools.files import save


class ROSEnv:
    """
    Generator to serve as integration for Robot Operating System 2 development workspaces.

    IMPORTANT: This generator should be used together with CMakeDeps and CMakeToolchain generators.
    """

    def __init__(self, conanfile):
        """
        :param conanfile: ``< ConanFile object >`` The current recipe object. Always use ``self``.
        """
        self._conanfile = conanfile
        self.variables = {}
        self._build_script_file = "conanrosenv-build.sh"
        self._wrapper_script_file = "conanrosenv.sh"

    def generate(self):
        """
        Creates a ``conanrosenv.sh`` with the environment variables that are needed to build and
        execute ROS packages with Conan dependencies.
        """
        cmake_toolchain_path = os.path.join(self._conanfile.generators_folder,
                                            "conan_toolchain.cmake")
        self.variables["CMAKE_TOOLCHAIN_FILE"] = cmake_toolchain_path
        build_type = self._conanfile.settings.get_safe("build_type")
        if build_type:
            self.variables["CMAKE_BUILD_TYPE"] = build_type

        # Add ROS required variables to VirtualBuildEnv
        rosbuildenv = Environment()
        for k, v in self.variables.items():
            rosbuildenv.define(k, v)
        rosbuildenv.vars(self._conanfile, "build").save_script(self._build_script_file)

        # Generate conanrosenv.sh script wrapper that calls conanbuild.sh and conanrun.sh
        # TODO: Windows .bat/.ps1 files still not supported for the wrapper
        conanbuild_path = os.path.join(self._conanfile.generators_folder, "conanbuild.sh")
        conanrun_path = os.path.join(self._conanfile.generators_folder, "conanrun.sh")
        rosenv_wrapper_content = [f". \"{conanbuild_path}\"", f". \"{conanrun_path}\""]
        create_env_script(self._conanfile, "\n".join(rosenv_wrapper_content),
                          self._wrapper_script_file, None)

        conanrosenv_path = os.path.join(self._conanfile.generators_folder, self._wrapper_script_file)
        msg = f"Generated ROSEnv Conan file: {self._wrapper_script_file}\n" + \
              f"Use 'source {conanrosenv_path}' to set the ROSEnv Conan before 'colcon build'"
        self._conanfile.output.info(msg, fg=Color.CYAN)
