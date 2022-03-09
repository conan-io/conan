from conans.client.subsystems import deduce_subsystem, subsystem_path


def unix_path(conanfile, path, subsystem=None):
    if not conanfile.win_bash:
        return path
    subsystem = subsystem or deduce_subsystem(conanfile, scope="build")
    return subsystem_path(subsystem, path)
