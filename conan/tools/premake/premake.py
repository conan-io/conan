class Premake:
    def __init__(self, conanfile):
        self._conanfile = conanfile

    # automatically chooses premake action based on used compiler
    def configure(self):
        if "msvc" in self._conanfile.settings.compiler:
            _visuals = {'190': '2015',
                        '191': '2017',
                        '192': '2019',
                        '193': '2022',
                        '194': '2023'}
            version = _visuals.get(str(self._conanfile.settings.compiler.version))
            premake_command = f"premake5 vs{version}"
            self._conanfile.run(premake_command)
        else:
            self._conanfile.run("premake5 gmake2")
