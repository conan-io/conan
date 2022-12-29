from conans.client.subsystems import deduce_subsystem, subsystem_path


def unix_path(conanfile, path, scope="build"):
    subsystem = deduce_subsystem(conanfile, scope=scope)
    return subsystem_path(subsystem, path)
