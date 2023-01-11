from conans.client.subsystems import deduce_subsystem, subsystem_path
from conans.client.tools.win import unix_path as unix_path_legacy_tools


def unix_path(conanfile, path, scope="build"):
    subsystem = deduce_subsystem(conanfile, scope=scope)
    return subsystem_path(subsystem, path)

def unix_path_package_info_legacy(conanfile, path, path_flavor=None):
    # Call legacy implementation, which has different logic
    # to autodeduce the subsystem type for the conversion.
    return unix_path_legacy_tools(path, path_flavor)
