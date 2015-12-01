from conans.paths import CONANFILE


conanfile_template = r"""
from conans import ConanFile

class {name}Conan(ConanFile):
    name = "{name}"
    version = "{version}"
    requires = ({requires})
    exports = '*'

    def imports(self):
        self.copy("*", "src")

    def build(self):
        pass

    def package(self):
        self.copy('*.go',"", "src")
"""

hello = r'''
package hello%NUMBER%

import (
    "fmt"
%INCLUDES%
)

func Hello() {
    fmt.Printf("Hello %NUMBER%\n")
%OTHER CALLS%
}
'''


main = r'''package main

import (
    "hello%NUMBER%"
)

func main() {
    hello%NUMBER%.Hello()
}
'''


def go_hello_source_files(number=0, deps=None):
    """
    param number: integer, defining name of the conans Hello0, Hello1, HelloX
    param deps: [] list of integers, defining which dependencies this conans
                depends on
    e.g. (3, [4, 7]) means that a Hello3 conans will be created, with message
         "Hello 3", that depends both in Hello4 and Hello7.
         The output of such a conans exe could be like: Hello 3, Hello 4, Hello7
    """
    assert deps is None or isinstance(deps, list)
    deps = deps or []
    ret = {}
    number = str(number)
    other_includes = "\n".join(['    "hello%i"' % i for i in deps])
    ret["src/hello%s_main/main.go" % number] = main.replace("%NUMBER%", number)
    other_calls = "\n".join(["    hello%d.Hello();" % i for i in deps])
    hello_go = hello.replace("%NUMBER%", number)
    hello_go = hello_go.replace("%OTHER CALLS%", other_calls)
    hello_go = hello_go.replace("%INCLUDES%",  other_includes)
    ret["src/hello%s/hello.go" % number] = hello_go
    return ret


def go_hello_conan_files(conan_reference, number=0, deps=None):
    """Generate hello_files, as described above, plus the necessary
    CONANFILE to manage it
    param number: integer, defining name of the conans Hello0, Hello1, HelloX
    param deps: [] list of integers, defining which dependencies this conans
                depends on
    e.g. (3, [4, 7]) means that a Hello3 conans will be created, with message
         "Hello 3", that depends both in Hello4 and Hello7.
         The output of such a conans exe could be like: Hello 3, Hello 4, Hello7"""
    assert deps is None or isinstance(deps, list)
    number = str(number)
    base_files = go_hello_source_files(number, deps)
    requires = []
    for d in deps or []:
        requires.append('"hello%d/0.1@lasote/stable"' % d)
    requires = ", ".join(requires)
    conanfile = conanfile_template.format(name=conan_reference.name,
                                      version=conan_reference.version,
                                      requires=requires)
    base_files[CONANFILE] = conanfile

    return base_files
