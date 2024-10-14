import os
from conan.api.output import Color
from conan.tools.env import VirtualBuildEnv, VirtualRunEnv, Environment
from conan.tools.files import save
from conan.errors import ConanException


cmake_toolchain_exists_bash = """\
if [ ! -e "$CMAKE_TOOLCHAIN_FILE" ]; then
    echo "Error: CMAKE_TOOLCHAIN_FILE path not found at '$CMAKE_TOOLCHAIN_FILE'."
    echo "Make sure you are using CMakeToolchain and CMakeDeps generators too."
    exit 1
fi
"""


class ROSEnv(object):
    """
    Generator to serve as integration for Robot Operating System 2 development workspaces.
    It generates a conanrosenv.bash file that when sources sets variables so the Conan
    dependencies are found by CMake and the run environment is also set.

    IMPORTANT: This generator should be used together with CMakeDeps and CMakeToolchain generators.
    """

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self.variables = {}
        self._virtualbuildenv = VirtualBuildEnv(conanfile)
        self._virtualbuildenv.basename = "conanrosenv"
        self._virtualrunenv = VirtualRunEnv(conanfile)

    def generate(self):
        output_folder = self._conanfile.generators_folder
        self.variables.setdefault("CMAKE_TOOLCHAIN_FILE",
                                  os.path.join(output_folder, "conan_toolchain.cmake"))
        build_type = self._conanfile.settings.get_safe("build_type")
        if build_type:
            self.variables.setdefault("CMAKE_BUILD_TYPE", build_type)
        # Add ROS required variables to VirtualBuildEnv
        rosbuildenv = Environment()
        for k, v in self.variables.items():
            rosbuildenv.define(k, v)
        self._virtualbuildenv._buildenv = rosbuildenv
        # Add VirtualRunEnv variables to VirtualBuildEnv
        self._virtualbuildenv._buildenv.compose_env(self._virtualrunenv.environment())
        self._virtualbuildenv.generate()
        conanrosenv_path = os.path.join(self._conanfile.generators_folder, "conanrosenv.sh")
        msg = f"Generated ROSEnv Conan file: conanrosenv.sh\n" + \
              f"Use 'source {conanrosenv_path}' to set the ROSEnv Conan before 'colcon build'"
        self._conanfile.output.info(msg, fg=Color.CYAN)
