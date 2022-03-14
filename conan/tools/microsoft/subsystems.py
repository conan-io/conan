from conans.client.subsystems import deduce_subsystem, subsystem_path


def unix_path(conanfile, path):
    if not conanfile.win_bash:
        return path
    subsystem = deduce_subsystem(conanfile, scope="build")
    return subsystem_path(subsystem, path)
