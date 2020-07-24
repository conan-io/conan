from conans.client.tools import system_pm as tools_system_pm


class SystemPackageTool(tools_system_pm.SystemPackageTool):
    def __init__(self, conanfile, *args, **kwargs):
        super(SystemPackageTool, self).__init__(output=conanfile.output, *args, **kwargs)


class NullTool(tools_system_pm.NullTool):
    def __init__(self, conanfile, *args, **kwargs):
        super(NullTool, self).__init__(output=conanfile.output, *args, **kwargs)


class AptTool(tools_system_pm.AptTool):
    def __init__(self, conanfile, *args, **kwargs):
        super(AptTool, self).__init__(output=conanfile.output, *args, **kwargs)


class DnfTool(tools_system_pm.DnfTool):
    def __init__(self, conanfile, *args, **kwargs):
        super(DnfTool, self).__init__(output=conanfile.output, *args, **kwargs)


class YumTool(tools_system_pm.YumTool):
    def __init__(self, conanfile, *args, **kwargs):
        super(YumTool, self).__init__(output=conanfile.output, *args, **kwargs)


class BrewTool(tools_system_pm.BrewTool):
    def __init__(self, conanfile, *args, **kwargs):
        super(BrewTool, self).__init__(output=conanfile.output, *args, **kwargs)


class PkgTool(tools_system_pm.PkgTool):
    def __init__(self, conanfile, *args, **kwargs):
        super(PkgTool, self).__init__(output=conanfile.output, *args, **kwargs)


class ChocolateyTool(tools_system_pm.ChocolateyTool):
    def __init__(self, conanfile, *args, **kwargs):
        super(ChocolateyTool, self).__init__(output=conanfile.output, *args, **kwargs)


class PkgUtilTool(tools_system_pm.PkgUtilTool):
    def __init__(self, conanfile, *args, **kwargs):
        super(PkgUtilTool, self).__init__(output=conanfile.output, *args, **kwargs)


class PacManTool(tools_system_pm.PacManTool):
    def __init__(self, conanfile, *args, **kwargs):
        super(PacManTool, self).__init__(output=conanfile.output, *args, **kwargs)


class ZypperTool(tools_system_pm.ZypperTool):
    def __init__(self, conanfile, *args, **kwargs):
        super(ZypperTool, self).__init__(output=conanfile.output, *args, **kwargs)
