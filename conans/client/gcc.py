from conans.errors import ConanException
from conans.model.settings import Settings


class GCC(object):

    def __init__(self, settings):
        assert isinstance(settings, Settings)
        self._settings = settings
        self.build_type = self._get_setting_safe("build_type")
        self.arch = self._get_setting_safe("arch")

    @property
    def command_line(self):
        """
            gcc = GCC(self.settings)
            command = 'gcc main.c @conanbuildinfo.gcc -o main %s' % gcc.command_line
            self.run(command)
        """
        print("""
        ***********************************************************************

            WARNING!!!

            GCC helper class is deprecated and will be removed soon.
            It's not needed anymore due the improvement of "gcc" generator.

            Use "gcc" generator and invoke the compiler:

                gcc main.c @conanbuildinfo.gcc -o main

            Check docs.conan.io


        ***********************************************************************
                """)
        flags = ""
        if self.build_type:
            flags += self.build_type_flags
        if self.arch:
            flags += self.arch_flags
        return flags

    @property
    def build_type_flags(self):
        if self.build_type == "Release":
            return "-s -DNDEBUG "
        elif self.build_type == "Debug":
            return "-g "
        return ""

    @property
    def arch_flags(self):
        if self.arch == "x86":  # FIXME: If platform is x86_64
            return "-m32"
        return ""

    def _get_setting_safe(self, name):
        try:
            return getattr(self._settings, name)
        except ConanException:
            return None
