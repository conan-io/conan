_conanfile = '''\
from conan import ConanFile

class BarebonesConanfile(ConanFile):
    name = "barebones"
    version = "0.0"
    description = "A bare-bones recipe"
'''


barebones_file = {"conanfile.py": _conanfile}
