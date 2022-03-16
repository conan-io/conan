from conan.tools.gnu.pkgconfigdeps.pc_files_templates import get_alias_pc_filename_and_content, \
    get_pc_filename_and_content
from conan.tools.gnu.pkgconfigdeps.pc_info_loader import get_package_with_components_info, \
    get_single_package_info, get_aliases_info


def _get_aliases_pc_files_and_content(conanfile, dep, aliases_info, root_pc_files):
    """
    Get all the PC files and content for the aliases defined previously
    for package and components names
    """
    pc_files = {}
    for name, aliases in aliases_info.items():
        for alias in aliases:
            pc_name, pc_content = get_alias_pc_filename_and_content(
                dep,
                alias,
                [name],  # require is the own name which is being used the aliases for.
                description="Alias %s for %s" % (alias, name),
            )
            if pc_name in pc_files:
                conanfile.output.warn("[%s] The PC alias name %s already exists and it matches with "
                                      "another alias one. Please, review all the "
                                      "pkg_config_aliases defined. Skipping it!"
                                      % (dep, pc_name))
            elif pc_name in root_pc_files:
                conanfile.output.warn("[%s] The PC alias name %s already exists and it matches with "
                                      "another package/component one. Please, review all the "
                                      "pkg_config_aliases defined. Skipping it!"
                                      % (dep, pc_name))
            else:
                pc_files[pc_name] = pc_content
    return pc_files


def _get_components_pc_files_and_content(conanfile, dep, package_info, components_info):
    """
    Get the PC files and content for dependency's components
    """
    pc_files = {}
    # Loop through all the package's components
    for pc_info_component in components_info:
        # Get the *.pc file content for each component
        description = "Conan component: %s-%s" % (package_info.name, pc_info_component.name)
        pc_name, pc_content = get_pc_filename_and_content(
            conanfile,
            dep,
            pc_info_component.name,
            pc_info_component.requires,
            description,
            cpp_info=pc_info_component.cpp_info)
        if pc_name in pc_files:
            conanfile.output.warn("[%s] The PC component name %s already exists and it matches with "
                                  "another component one. Please, review all the "
                                  "component's pkg_config_name defined. Skipping it!"
                                  % (dep, pc_name))
        else:
            pc_files[pc_name] = pc_content
    return pc_files


def _get_package_with_components_pc_files_and_content(conanfile, dep, package_info, components_info):
    """
    Get the PC files and content for dependencies with components.
    The PC files will be saved in this order:
        1- Package components.
        2- Root component.

    Note: If the root-package PC name matches with any other of the components one, the first one
    is not going to be created. Components have more priority than root package.
    """
    pc_files = {}
    # First, let's load all the components PC files
    pc_files.update(_get_components_pc_files_and_content(conanfile, dep, package_info, components_info))
    description = "Conan package: %s" % package_info.name
    pc_name, pc_content = get_alias_pc_filename_and_content(
        dep,
        package_info.name,
        package_info.requires,
        description
    )
    # Second, let's load the root package's PC file ONLY
    # if it does not already exist in components one
    # Issue related: https://github.com/conan-io/conan/issues/10341
    if pc_name in pc_files:
        conanfile.output.warn("[%s] The PC package name %s already exists and it matches with "
                              "another component one. Please, review all the "
                              "component's pkg_config_name defined. Skipping it!" % (dep, pc_name))
    else:
        pc_files[pc_name] = pc_content
    return pc_files


def _get_single_package_pc_file_and_content(conanfile, dep, package_info):
    """
    Get the PC files for dependencies without components
    """
    description = "Conan package: %s" % package_info.name
    pc_name, pc_content = get_pc_filename_and_content(conanfile, dep, package_info.name,
                                                      package_info.requires, description)
    return {pc_name: pc_content}


def get_pc_files_and_content(conanfile, dep):
    """
    Get all the PC files given a dependency (package, components and alias ones)
    """
    pc_files = {}
    if dep.cpp_info.has_components:  # Package with components
        pkg_info, components_info = get_package_with_components_info(dep)
        pc_files.update(_get_package_with_components_pc_files_and_content(conanfile, dep, pkg_info,
                                                                          components_info))
    else:
        # Package without components
        pkg_info = get_single_package_info(dep)
        components_info = []
        pc_files.update(_get_single_package_pc_file_and_content(conanfile, dep, pkg_info))
    # Package and components names aliases
    aliases_info = get_aliases_info(dep, pkg_info, components_info)
    pc_files.update(_get_aliases_pc_files_and_content(conanfile, dep, aliases_info, pc_files))
    return pc_files
