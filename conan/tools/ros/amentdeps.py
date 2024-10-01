from conan.tools.files import save
from conan.tools.cmake import CMakeDeps

import os

class AmentDeps(object):
    """
    Generator to serve as integration for Robot Operating System 2 development workspaces.
    It is able to generate CMake files and place them correctly so they can be found by Colcon.
    """

    def __init__(self, conanfile):
        self.cmakedeps_files = None
        self.cmakedeps = CMakeDeps(conanfile)
        self._conanfile = conanfile

    def generate(self):
        # This is called here so the CMakeDeps output is only showed once
        self.cmakedeps_files = self.cmakedeps.content

        output_folder = self._conanfile.generators_folder
        if not output_folder.endswith("install"):
            self._conanfile.output.warning("The output folder for the Ament generator should be"
                                           " always 'install'. Make sure you are using "
                                           "'--output-folder install' in your 'conan install'"
                                           "command")
        # Get the name of the ROS package that requires the Conan packages
        ros_package_name = os.path.basename(self._conanfile.source_folder)
        self._conanfile.output.info(f"ROS2 workspace install folder: {output_folder}")

        for require, _ in self._conanfile.dependencies.items():
            self.generate_cmake_files(output_folder, ros_package_name, require.ref.name)

    def generate_cmake_files(self, install_folder, ros_package_name, require_name):
        """
        Generate CMakeDeps files in <install_folder>/<ros_package_name>/share/<require_name>/cmake
        Fox example : install/consumer/share/bzip2/cmake

        @param install_folder: folder to generate the
        @param ros_package_name: name of ROS package that has de Conan dependencies
        @param require_name: name of the dependency
        """
        self._conanfile.output.info(f"Generating CMake files for {require_name} dependency")
        for generator_file, content in self.cmakedeps_files.items():
            # Create CMake files in install/<ros_package_name>/share/<require_name>/cmake directory
            if require_name in generator_file.lower() or \
                    "cmakedeps_macros.cmake" in generator_file.lower():
                self._conanfile.output.info(f"Generating CMake file {generator_file}")
                # FIXME: This is a way to save only the require_name related cmake files
                #  (and helper cmake files), however, names might not match!!
                file_path = os.path.join(install_folder, ros_package_name, "share", require_name,
                                         "cmake", generator_file)
                save(self._conanfile, file_path, content)
