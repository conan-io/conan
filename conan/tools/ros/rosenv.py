import os
from conan.api.output import Color
from conan.tools.env import VirtualBuildEnv, Environment
from conan.tools.files import save


class ROSEnv:
    """
    Generator to serve as integration for Robot Operating System 2 development workspaces.
    It generates a conanrosenv.sh file that when sources sets variables so the Conan
    dependencies are found by CMake and the run environment is also set.

    IMPORTANT: This generator should be used together with CMakeDeps and CMakeToolchain generators.
    """

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self._variables = {}
        self.variables = {}
        self._virtualbuildenv = VirtualBuildEnv(self._conanfile, auto_generate=True)
        self._virtualbuildenv.basename = "conanrosenv"
        self._rosenv_wrapper = "conanrosenv.sh"

    def generate(self):
        output_folder = self._conanfile.generators_folder
        self._variables["CMAKE_TOOLCHAIN_FILE"] = os.path.join(output_folder, "conan_toolchain.cmake")
        build_type = self._conanfile.settings.get_safe("build_type")
        if build_type:
            self._variables["CMAKE_BUILD_TYPE"] = build_type
        self.variables.update(self._variables)

        # Add ROS required variables to VirtualBuildEnv
        rosbuildenv = Environment()
        for k, v in self._variables.items():
            rosbuildenv.define(k, v)
        self._virtualbuildenv._buildenv = rosbuildenv
        self._virtualbuildenv.generate()

        # Generate conanrosenv.sh script wrapper that calls conanbuild.sh and conanrun.sh
        conanbuild_path = os.path.join(self._conanfile.generators_folder, "conanbuild.sh")
        cmd_wrapper = [f". \"{conanbuild_path}\""]
        conanrun_path = os.path.join(self._conanfile.generators_folder, "conanrun.sh")
        if os.path.exists(conanrun_path):
            cmd_wrapper.append(f". \"{conanrun_path}\"")
        conanrosenv_path = os.path.join(self._conanfile.generators_folder, self._rosenv_wrapper)
        save(self._conanfile, conanrosenv_path, "\n".join(cmd_wrapper))

        msg = f"Generated ROSEnv Conan file: conanrosenv.sh\n" + \
              f"Use 'source {conanrosenv_path}' to set the ROSEnv Conan before 'colcon build'"
        self._conanfile.output.info(msg, fg=Color.CYAN)
