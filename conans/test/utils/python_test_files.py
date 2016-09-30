from conans.paths import CONANFILE
from __builtin__ import file


conanfile_template = r"""
from conans import ConanFile

class {name}Conan(ConanFile):
    name = "{name}"
    version = "{version}"
    requires = ({requires})
    exports = '*'
    generators = "virtualenv"
    build_policy = "missing"

    def package(self):
        self.copy('*.py')

    def package_info(self):
        self.env_info.PYTHONPATH.append(self.package_folder)
"""

hello = r'''
%INCLUDES%

def hello():
    print("Hello %NUMBER%")
%OTHER CALLS%

'''


main = r'''
from hello%NUMBER% import hello as h%NUMBER%

if __name__ == "__main__":
    h%NUMBER%.hello()

'''


def py_hello_source_files(number=0, deps=None):
    assert deps is None or isinstance(deps, list)
    deps = deps or []
    ret = {}
    number = str(number).split("/", 1)[0]
    deps_names = [str(n).split("/", 1)[0] for n in deps]
    other_includes = "\n".join(['from hello%s import hello as h%s' % (i, i) for i in deps_names])
    ret["main.py"] = main.replace("%NUMBER%", number)
    other_calls = "\n".join(["    h%s.hello()" % i for i in deps_names])
    hello_py = hello.replace("%NUMBER%", number)
    hello_py = hello_py.replace("%OTHER CALLS%", other_calls)
    hello_py = hello_py.replace("%INCLUDES%",  other_includes)
    ret["hello%s/hello.py" % number] = hello_py
    ret["hello%s/__init__.py" % number] = ""
    return ret


def py_hello_conan_files(name, version, deps=None):
    assert deps is None or isinstance(deps, list)
    base_files = py_hello_source_files(name, deps)
    requires = []
    for d in deps or []:
        requires.append(d)
    requires = ", ".join('"%s"' % r for r in requires)
    conanfile = conanfile_template.format(name=name, version=version, requires=requires)
    base_files[CONANFILE] = conanfile

    return base_files
