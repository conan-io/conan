class Premake(object):
    def __init__(self, conanfile):
        self._conanfile = conanfile

    # automatically chooses premake action based on used compiler
    def configure(self):
        if "Visual Studio" in self.settings.compiler:
            _visuals = {'8': '2005',
                        '9': '2008',
                        '10': '2010',
                        '11': '2012',
                        '12': '2013',
                        '14': '2015',
                        '15': '2017',
                        '16': '2019'}
            premake_command = "premake5 vs%s" % _visuals.get(str(self.settings.compiler.version), "UnknownVersion %s" % str(self.settings.compiler.version))
            self.run(premake_command)
        else:
            self.run("premake5 gmake2")