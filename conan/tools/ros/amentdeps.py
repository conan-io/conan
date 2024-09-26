from conan.tools.files import save
from conan.tools.cmake import CMakeDeps

import os

# File templates for this generator can be found at https://github.com/ament/ament_package

package_xml = """\
<?xml version="1.0"?>
<?xml-model href="http://download.ros.org/schema/package_format3.xsd" schematypens="http://www.w3.org/2001/XMLSchema"?>
<package format="3">
  <name>{ref_name}</name>
  <version>{ref_version}</version>
  <description>{ref_description}</description>
  <maintainer email="info@conan.io">conan</maintainer>
  <license>{ref_license}</license>

  <buildtool_depend>ament_cmake</buildtool_depend>

  <export>
    <build_type>ament_cmake</build_type>
  </export>
</package>
"""

library_path_dsv = """\
prepend-non-duplicate;LD_LIBRARY_PATH;{run_paths}
"""

cmakelists_txt = """\
cmake_minimum_required(VERSION 3.8)
project({ref_name})

find_package(ament_cmake REQUIRED)

install(FILES ${{CMAKE_SOURCE_DIR}}/package.xml DESTINATION data)

ament_package()
"""

gitignore = """\
*
"""


class AmentDeps(object):
    """
    Generator to serve as integration for Robot Operating System 2 development workspaces.
    It is able to generate files in the similar way Ament does by injecting the Conan-retrieved library's information
    into the proper directories and files.
    The directory tree is then recognized by Colcon so packages in the workspace can be built and run using the Conan
    package's libraries from the Conan cache.
    """

    def __init__(self, conanfile):
        self.cmakedeps = CMakeDeps(conanfile)
        self._conanfile = conanfile
        self.cmakedeps_files = None

    def generate(self):
        self.cmakedeps_files = self.cmakedeps.content

        output_folder = self._conanfile.generators_folder
        if not output_folder.endswith("install"):
          self._conanfile.output.warning("The output folder for the Ament generator should be always 'install'. Make sure you are using '--output-folder install' in your 'conan install' command")
        root_folder = os.path.sep.join(output_folder.split(os.path.sep)[:-1])  # This should be the workspace root folder
        self._conanfile.output.info(f"ROS2 workspace root folder: {root_folder}")
        self._conanfile.output.info(f"ROS2 workspace install folder: {output_folder}")

        for require, dep in self._conanfile.dependencies.items():
            if not require.direct:
                # Only direct depdendencies should be included
                continue
            ref_name = require.ref.name
            ament_ref_name = f"conan_{ref_name}"
            ref_version = require.ref.version
            ref_description = dep.description or "unknown"
            ref_license = dep.license or "unknown"
            run_paths = self.get_run_paths(require, dep)

            self.generate_direct_dependency(root_folder, output_folder, ament_ref_name, ref_name, ref_version, ref_description, ref_license, run_paths)
            dependencies = ", ".join([dep.ref.name for _, dep in dep.dependencies.items()])
            self._conanfile.output.info(f"{ref_name} dependencies: {dependencies}")
            for req, _ in dep.dependencies.items():
                self.generate_cmake_files(output_folder, ament_ref_name, req.ref.name)

    def generate_direct_dependency(self, root_folder, install_folder, ament_ref_name, ref_name, ref_version, ref_description, ref_license, run_paths):
        """
        Generate correct directory structure for a direct dependency.
        -> conan_<require>: Mock dependency inside workspace.
        -> install/conan_<require>/share/conan_<require>: Common package files.
        -> install/conan_<require>/share/colcon-core: To mark package as installed for Colcon.
        -> install/conan_<require>/ament_index/conan_<require>: To mark package as installed for Ament.
        -> install/conan_<require>/ament_index/conan_<require>/environment: Files to set up the running environment.
        -> install/conan_<require>/ament_index/conan_<require>/hook: Files to set up the building environment.

        @param ament_ref_name: Name of the dependency with the 'conan_' prefix.
        @param ref_name: Name of the Conan reference.
        @param ref_version: Version of the Conan reference.
        @param ref_description: Description of the recipe.
        @param ref_license: License of the recipe.
        @param run_paths: List of libdirs to inject into the environment files.
        @return:
        """
        direct_dependency_folder = os.path.join(root_folder, ament_ref_name)
        self._conanfile.output.info(f"Creating Conan direct dependency folder at: {direct_dependency_folder}")

        paths_content = [
            (os.path.join(direct_dependency_folder, "package.xml"),
             package_xml.format(ref_name=ament_ref_name, ref_version=ref_version,
                                ref_description=ref_description, ref_license=ref_license)),
            (os.path.join(direct_dependency_folder, ".gitignore"), gitignore),
            (os.path.join(direct_dependency_folder, "CMakeLists.txt"),
             cmakelists_txt.format(ref_name=ament_ref_name)),
            (os.path.join(install_folder, ament_ref_name, "share", ament_ref_name, "environment",
                          "library_path.dsv"), library_path_dsv.format(run_paths=run_paths)),
        ]
        for path, content in paths_content:
            save(self._conanfile, path, content)

        self.generate_cmake_files(install_folder, ament_ref_name, ref_name)

    def generate_cmake_files(self, install_folder, ament_ref_name, require_name):
        """
        Generate CMakeDeps files inside install/<ament_ref_name>/share/<require_name>/cmake directory
        Fox example : install/conan_boost/share/bzip2/cmake

        @param ament_ref_name: name of the direct dependency
        @param require_name: name of the transitive dependency
        """
        self._conanfile.output.info(f"Generating CMake files for {require_name} dependency")
        for generator_file, content in self.cmakedeps_files.items():
            # Create CMake files in install/<ament_ref_name>/share/<require_name>/cmake directory
            if require_name in generator_file.lower() or "cmakedeps_macros.cmake" in generator_file.lower():
              self._conanfile.output.info(f"Generating CMake file {generator_file}")
              # FIXME: This is a way to save only the require_name related cmake files (and helper cmake files), however, names might not match!!
              file_path = os.path.join(install_folder, ament_ref_name, "share", require_name, "cmake", generator_file)
              save(self._conanfile, file_path, content)

    @staticmethod
    def get_run_paths(require, dependency):
        """
        Collects the libdirs of each dependency into a list in inverse order

        @param require: conanfile object
        @param dependency: requires node structure of the graph
        @return: string of ; separated library dirs of dependencies in inverse order
        """
        run_paths = []

        def _get_cpp_info_libdirs(req, dep):
            paths = []
            if req.run:  # Only if the require is run (shared or application to be run)
                cpp_info = dep.cpp_info.aggregated_components()
                for d in cpp_info.libdirs:
                    if os.path.exists(d):
                      paths.insert(0, d)
            return paths

        run_paths[:0] = _get_cpp_info_libdirs(require, dependency)

        for r, d in dependency.dependencies.items():
            run_paths[:0] = _get_cpp_info_libdirs(r, d)

        if run_paths:
            return ";".join(run_paths)
        else:
            return "lib"  # default value
