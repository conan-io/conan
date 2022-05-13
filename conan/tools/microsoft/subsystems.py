from conans.client.subsystems import deduce_subsystem, subsystem_path


def unix_path(conanfile, path):
    """
    Transforms the specified path into the correct one according to the subsystem.
    To determine the subsystem:

        * The ``settings_build.os`` is checked to verify that we are running on “Windows”
          otherwise, the path is returned without changes.
        * If ``settings_build.os.subsystem`` is specified (meaning we are running Conan
          under that subsystem) it will be returned.
        * If ``conanfile.win_bash==True`` (meaning we have to run the commands inside the
          subsystem), the conf ``tools.microsoft.bash:subsystem`` has to be declared or it
          will raise an Exception.
        * Otherwise the path is returned without changes.

    :param conanfile: ``< ConanFile object >`` The current recipe object. Always use ``self``.
    :param path:
    :return:
    """
    if not conanfile.win_bash:
        return path
    subsystem = deduce_subsystem(conanfile, scope="build")
    return subsystem_path(subsystem, path)
