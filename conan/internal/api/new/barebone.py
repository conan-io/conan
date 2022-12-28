_conanfile = '''\
from conan import ConanFile

class BarebonesConanfile(ConanFile):
    name = "barebone"
    version = "0.0"
    description = "A bare-bones recipe"
'''


barebone_file = {"conanfile.py": _conanfile}
