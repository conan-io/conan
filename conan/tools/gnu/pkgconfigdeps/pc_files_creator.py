from conan.tools.gnu.pkgconfigdeps.pc_files_templates import PCFilesTemplate
from conan.tools.gnu.pkgconfigdeps.pc_info_loader import PCInfoLoader


class PCFilesCreator(object):

    def __init__(self, conanfile, dep):
        self._conanfile = conanfile
        self._dep = dep
        self._pc_info_loader = PCInfoLoader(conanfile, dep)
        self._pc_files_templates = PCFilesTemplate(conanfile, dep)

    @property
    def _aliases_pc_files_and_content(self):
        """Get all the *.pc files content for the aliases defined previously"""
        self._pc_info_loader.load_aliases_info()
        pc_files = {}
        for name, aliases in self._pc_info_loader.aliases_info.items():
            for alias in aliases:
                pc_wrapper_file = self._pc_files_templates.get_wrapper_pc_filename_and_content(
                    alias,
                    [name],  # require is the own name which is being used the aliases for.
                    description="Alias %s for %s" % (alias, name),
                )
                pc_files.update(pc_wrapper_file)
        return pc_files

    def _get_components_pc_files_and_content(self):
        pc_files = {}
        # Loop through all the package's components
        for pc_info_component in self._pc_info_loader.components_info:
            # Get the *.pc file content for each component
            description = "Conan component: %s" % pc_info_component.name
            pc_file = self._pc_files_templates.get_pc_filename_and_content(
                pc_info_component.name,
                pc_info_component.requires,
                description,
                cpp_info=pc_info_component.cpp_info)
            pc_files.update(pc_file)
        return pc_files

    @property
    def _package_with_components_pc_files_and_content(self):
        self._pc_info_loader.load_package_with_components_info()
        pc_files = {}
        pc_files.update(self._get_components_pc_files_and_content())
        pkg_info = self._pc_info_loader.package_info
        description = self._conanfile.description or "Conan package: %s" % pkg_info.name
        pc_wrapper_file_pkg = self._pc_files_templates.get_wrapper_pc_filename_and_content(
            pkg_info.name,
            pkg_info.requires,
            description
        )
        pc_files.update(pc_wrapper_file_pkg)
        return pc_files

    @property
    def _single_package_pc_file_and_content(self):
        self._pc_info_loader.load_single_package_info()
        pkg_info = self._pc_info_loader.package_info
        description = self._conanfile.description or "Conan package: %s" % pkg_info.name
        pc_file = self._pc_files_templates.get_pc_filename_and_content(pkg_info.name,
                                                                       pkg_info.requires,
                                                                       description)
        return pc_file

    @property
    def pc_files_and_content(self):
        pc_files = {}
        if self._dep.cpp_info.has_components:
            pc_files.update(self._package_with_components_pc_files_and_content)
        else:
            pc_files.update(self._single_package_pc_file_and_content)
        # Package and components aliases
        pc_files.update(self._aliases_pc_files_and_content)
        return pc_files
