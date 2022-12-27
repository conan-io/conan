from conan.internal import check_duplicated_generator
from conan.tools.build.flags import build_type_flags, cppstd_flag
from conan.tools.env import Environment


class NMakeToolchain(object):
    """
    https://learn.microsoft.com/en-us/cpp/build/reference/running-nmake?view=msvc-170#toolsini-and-nmake
    We have also explored the usage of Tools.ini:
    https://learn.microsoft.com/en-us/cpp/build/reference/running-nmake?view=msvc-170
    but not possible, because it cannot include other files, it will also potentially collide with
    a user Tool.ini, without easy resolution. At least the environment is additive.
    """
    def __init__(self, conanfile):
        """
        :param conanfile: ``< ConanFile object >`` The current recipe object. Always use ``self``.
        """
        self._conanfile = conanfile
        self._environment = None

    @property
    def cl_flags(self):
        cppflags = []
        build_type = self._conanfile.settings.get_safe("build_type")
        if build_type in ['Release', 'RelWithDebInfo', 'MinSizeRel']:
            cppflags.append("/DNDEBUG")

        bt = build_type_flags(self._conanfile.settings)
        if bt:
            cppflags.extend(bt)

        cppstd = cppstd_flag(self._conanfile.settings)
        if cppstd:
            cppflags.append(cppstd)
        from conan.tools.microsoft import msvc_runtime_flag
        flag = msvc_runtime_flag(self._conanfile)
        if flag:
            cppflags.append("-{}".format(flag))
        return " ".join(cppflags).replace("-", "/")

    @property
    def environment(self):
        # TODO: Seems we want to make this uniform, equal to other generators
        if self._environment is None:
            env = Environment()
            # The whole injection of toolchain happens in CL env-var, the others LIBS, _LINK_
            env.append("CL", self.cl_flags)
            self._environment = env
        return self._environment

    def vars(self, scope="build"):
        return self.environment.vars(self._conanfile, scope=scope)

    def generate(self, scope="build"):
        check_duplicated_generator(self, self._conanfile)
        self.vars(scope).save_script("conannmaketoolchain")
        from conan.tools.microsoft import VCVars
        VCVars(self._conanfile).generate()
