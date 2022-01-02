class Premake(object):
    def __init__(self, conanfile):
        self._conanfile = conanfile

    # automatically chooses premake action based on used compiler
    def configure(self):
        if "Visual Studio" in self._conanfile.settings.compiler:
            _visuals = {'8': '2005',
                        '9': '2008',
                        '10': '2010',
                        '11': '2012',
                        '12': '2013',
                        '14': '2015',
                        '15': '2017',
                        '16': '2019'}
            premake_command = "premake5 vs%s" % _visuals.get(str(self._conanfile.settings.compiler.version))
            self._conanfile.run(premake_command)
        elif "msvc" in self._conanfile.settings.compiler:
            _visuals = {'14.0': '2005',
                        '15.0': '2008',
                        '16.0': '2010',
                        '17.0': '2012',
                        '18.0': '2013',
                        '19.0': '2015',
                        # add non-trailing 0 variation manually
                        '19.1': '2017',
                        '19.2': '2019'}
            # generate VS2017 versions
            for i in range(0,7):
                ver = '19.1' + str(i)
                _visuals[ver] = '2017'
            # generate VS2019 versions
            for i in range(0,10):
                ver = '19.2' + str(i)
                _visuals[ver] = '2019'
            premake_command = "premake5 vs%s" % _visuals.get(str(self._conanfile.settings.compiler.version))
            self._conanfile.run(premake_command)
        else:
            self._conanfile.run("premake5 gmake2")
