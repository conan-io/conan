from conans.client.subsystems import deduce_subsystem, subsystem_path


def unix_path(conanfile, path):
    """
    Transforms the specified path into the correct one according to the subsystem.
    To determine the subsystem:

        * The ``settings_build.os`` is checked to verify that we are running on “Windows”,
          otherwise, the path is returned without changes.
        * If ``settings_build.os.subsystem`` is specified (meaning we are running Conan
          under that subsystem) it will be returned.
        * If ``conanfile.win_bash==True`` (meaning we have to run the commands inside the
          subsystem), the conf ``tools.microsoft.bash:subsystem`` has to be declared or it
          will raise an Exception.
        * Otherwise the path is returned without changes.

    For instance:

    .. code:: python

        from conan.tools.microsoft import unix_path

        def build(self):
            adjusted_path = unix_path(self, "C:\\path\\to\\stuff")

    In the example above, ``adjusted_path`` will be:

        * ``/c/path/to/stuff`` if msys2 or msys.
        * ``/cygdrive/c/path/to/stuff`` if cygwin.
        * ``/mnt/c/path/to/stuff`` if wsl.
        * ``/dev/fs/C/path/to/stuff`` if sfu.

    :param conanfile: ``< ConanFile object >`` The current recipe object. Always use ``self``.
    :param path: ``str`` any folder path.
    :return: ``str`` the proper UNIX path.
    """
    if not conanfile.win_bash:
        return path
    subsystem = deduce_subsystem(conanfile, scope="build")
    return subsystem_path(subsystem, path)
