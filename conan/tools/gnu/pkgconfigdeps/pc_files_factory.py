
from conan.tools.gnu.pkgconfigdeps.templates import PCFilesTemplate


class PCFilesAndContentFactory(object):

    def __init__(self, conanfile, dep):
        self._conanfile = conanfile
        self._dep = dep
        self._templates_manager = PCFilesTemplate(conanfile, dep)
        self._requires_names = Psfgsad()

    @property
    def aliases_files_and_content(self):
        """Get all the *.pc files content for the aliases defined previously"""
        pc_files = {}
        for pkg_config_name, aliases in self._requires_names._aliases.items():
            for alias in aliases:
                pc_file = self._templates_manager.get_wrapper_pc_filename_and_content(
                    [pkg_config_name],
                    alias,
                    description="Alias %s for %s" % (alias, pkg_config_name),
                )
                pc_files.update(pc_file)
        return pc_files

    @property
    def components_files_and_content(self):
        """Get all the *.pc files content for the dependency and each of its components"""
        pc_files = {}
        pkg_comp_names = []
        # Loop through all the package's components
        for pkg_comp_name, (comp_requires_names, comp_cpp_info) in self._requires_names._components_names.items():
            pkg_comp_names.append(pkg_comp_name)
            # Get the *.pc file content for each component
            pc_files.update(self._templates_manager.get_pc_filename_and_content(comp_requires_names,
                                                               pkg_comp_name,
                                                               "Conan component: %s" % pkg_comp_name,
                                                               cpp_info=comp_cpp_info))
        # Let's create a *.pc file for the main package
        pc_files.update(self._templates_manager.get_wrapper_pc_filename_and_content(
            pkg_comp_names,
            self._requires_names.pkg_name,
            self._conanfile.description or "Conan package: %s" % self._requires_names.pkg_name)
        )
        return pc_files

    @property
    def package_file_and_content(self):
        requires = self._requires.pkg_requires_names()
        name = self._requires_names.pkg_name
        description = self._conanfile.description or "Conan package: %s" % name
        pc_files = self._templates_manager.get_pc_filename_and_content(requires, name, description)
        return pc_files

    @property
    def pc_files_and_content(self):
        pc_files = {}
        # Components
        if self._dep.cpp_info.has_components:
            pc_files.update(self.components_files_and_content)
        else:  # Package
            pc_files.update(self.package_file_and_content)
        # Package and components aliases
        pc_files.update(self.aliases_files_and_content)
        return pc_files
