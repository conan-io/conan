from conans.test.utils.cpp_test_files import cpp_hello_source_files, cpp_hello_conan_files
from conans.test.utils.go_test_files import go_hello_source_files, go_hello_conan_files
import os
from conans.paths import PACKAGE_TGZ_NAME
import tempfile
from conans.test import CONAN_TEST_FOLDER
from conans.tools import untargz
from conans.errors import ConanException


def temp_folder():
    t = tempfile.mkdtemp(suffix='conans', dir=CONAN_TEST_FOLDER)
    nt = os.path.join(t, "path with spaces")
    os.makedirs(nt)
    return nt


def uncompress_packaged_files(paths, package_reference):
    package_path = paths.package(package_reference)
    if not(os.path.exists(os.path.join(package_path, PACKAGE_TGZ_NAME))):
        raise ConanException("%s not found in %s" % (PACKAGE_TGZ_NAME, package_path))
    tmp = temp_folder()
    untargz(os.path.join(package_path, PACKAGE_TGZ_NAME), tmp)
    return tmp


def scan_folder(folder):
    scanned_files = []
    for root, _, files in os.walk(folder):
        relative_path = os.path.relpath(root, folder)
        for f in files:
            relative_name = os.path.normpath(os.path.join(relative_path, f)).replace("\\", "/")
            scanned_files.append(relative_name)

    return sorted(scanned_files)


def hello_source_files(number=0, deps=None, lang='cpp'):
    """
    param number: integer, defining name of the conans Hello0, Hello1, HelloX
    param deps: [] list of integers, defining which dependencies this conans
                depends on
    e.g. (3, [4, 7]) means that a Hello3 conans will be created, with message
         "Hello 3", that depends both in Hello4 and Hello7.
         The output of such a conans exe could be like: Hello 3, Hello 4, Hello7
    """
    if lang == 'cpp':
        return cpp_hello_source_files(number, deps)
    elif lang == 'go':
        return go_hello_source_files(number, deps)


def hello_conan_files(conan_reference, number=0, deps=None, language=0, lang='cpp'):
    """Generate hello_files, as described above, plus the necessary
    CONANFILE to manage it
    param number: integer, defining name of the conans Hello0, Hello1, HelloX
    param deps: [] list of integers, defining which dependencies this conans
                depends on
    param language: 0 = English, 1 = Spanish
    e.g. (3, [4, 7]) means that a Hello3 conans will be created, with message
         "Hello 3", that depends both in Hello4 and Hello7.
         The output of such a conans exe could be like: Hello 3, Hello 4, Hello7"""
    if lang == 'cpp':
        return cpp_hello_conan_files(conan_reference, number, deps, language)
    elif lang == 'go':
        return go_hello_conan_files(conan_reference, number, deps)
