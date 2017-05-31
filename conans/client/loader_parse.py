import imp
import inspect
import os
import sys
import uuid

from conans.client.generators import _save_generator
from conans.errors import ConanException, NotFoundException
from conans.model.conan_file import ConanFile
from conans.model.conan_generator import Generator
from conans.util.config_parser import ConfigParser
from conans.util.files import rmdir


def load_conanfile_class(conanfile_path):
    loaded, filename = _parse_file(conanfile_path)
    try:
        return _parse_module(loaded, filename)
    except Exception as e:  # re-raise with file name
        raise ConanException("%s: %s" % (conanfile_path, str(e)))


def _parse_module(conanfile_module, filename):
    """ Parses a python in-memory module, to extract the classes, mainly the main
    class defining the Recipe, but also process possible existing generators
    @param conanfile_module: the module to be processed
    @param consumer: if this is a root node in the hierarchy, the consumer project
    @return: the main ConanFile class from the module
    """
    result = None
    for name, attr in conanfile_module.__dict__.items():
        if "_" in name:
            continue
        if (inspect.isclass(attr) and issubclass(attr, ConanFile) and attr != ConanFile and
                attr.__dict__["__module__"] == filename):
            if result is None:
                result = attr
            else:
                raise ConanException("More than 1 conanfile in the file")
        if (inspect.isclass(attr) and issubclass(attr, Generator) and attr != Generator and
                attr.__dict__["__module__"] == filename):
                _save_generator(attr.__name__, attr)

    if result is None:
        raise ConanException("No subclass of ConanFile")

    return result


def _parse_file(conan_file_path):
    """ From a given path, obtain the in memory python import module
    """
    # Check if precompiled exist, delete it
    if os.path.exists(conan_file_path + "c"):
        os.unlink(conan_file_path + "c")

    # Python 3
    pycache = os.path.join(os.path.dirname(conan_file_path), "__pycache__")
    if os.path.exists(pycache):
        rmdir(pycache)

    if not os.path.exists(conan_file_path):
        raise NotFoundException("%s not found!" % conan_file_path)

    filename = os.path.splitext(os.path.basename(conan_file_path))[0]

    try:
        current_dir = os.path.dirname(conan_file_path)
        sys.path.append(current_dir)
        old_modules = list(sys.modules.keys())
        loaded = imp.load_source(filename, conan_file_path)
        # Put all imported files under a new package name
        module_id = uuid.uuid1()
        added_modules = set(sys.modules).difference(old_modules)
        for added in added_modules:
            module = sys.modules[added]
            if module:
                folder = os.path.dirname(module.__file__)
                if folder.startswith(current_dir):
                    module = sys.modules.pop(added)
                    sys.modules["%s.%s" % (module_id, added)] = module
    except Exception:
        import traceback
        trace = traceback.format_exc().split('\n')
        raise ConanException("Unable to load conanfile in %s\n%s" % (conan_file_path,
                                                                     '\n'.join(trace[3:])))
    finally:
        sys.path.pop()

    return loaded, filename


class ConanFileTextLoader(object):
    """Parse a conanfile.txt file"""

    def __init__(self, input_text):
        # Prefer composition over inheritance, the __getattr__ was breaking things
        self._config_parser = ConfigParser(input_text,  ["requires", "generators", "options",
                                                         "imports"], parse_lines=True)

    @property
    def requirements(self):
        """returns a list of requires
        EX:  "OpenCV/2.4.10@phil/stable"
        """
        return [r.strip() for r in self._config_parser.requires.splitlines()]

    @property
    def options(self):
        return self._config_parser.options

    @property
    def _import_parameters(self):
        def _parse_args(param_string):
            root_package, ignore_case, folder, excludes = None, False, False, None
            params = param_string.split(",")
            params = [p.split("=") for p in params if p]
            for (var, value) in params:
                var = var.strip()
                value = value.strip()
                if var == "root_package":
                    root_package = value
                elif var == "ignore_case":
                    ignore_case = (value.lower() == "true")
                elif var == "folder":
                    folder = (value.lower() == "true")
                elif var == "excludes":
                    excludes = value.split()
                else:
                    raise Exception("Invalid imports. Unknown argument %s" % var)
            return root_package, ignore_case, folder, excludes

        def _parse_import(line):
            pair = line.split("->")
            source = pair[0].strip().split(',', 1)
            dest = pair[1].strip()
            src, pattern = source[0].strip(), source[1].strip()
            return pattern, dest, src

        ret = []
        local_install_text = self._config_parser.imports
        for line in local_install_text.splitlines():
            # discard blanks, comments, and discard trailing comments
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            line = line.split("#", 1)[0]

            invalid_line_msg = "Invalid imports line: %s\nEX: OpenCV/lib, * -> ./lib" % line
            if line.startswith("/") or line.startswith(".."):
                raise ConanException("%s\n%s" % (invalid_line_msg,
                                                 "Import's paths can't begin with '/' or '..'"))
            try:
                tokens = line.split("@", 1)
                if len(tokens) > 1:
                    line = tokens[0]
                    params = tokens[1]
                else:
                    params = ""
                root_package, ignore_case, folder, excludes = _parse_args(params)
                pattern, dest, src = _parse_import(line)
                ret.append((pattern, dest, src, root_package, folder, ignore_case, excludes))
            except Exception as e:
                raise ConanException("%s\n%s" % (invalid_line_msg, str(e)))
        return ret

    @property
    def generators(self):
        return self._config_parser.generators.splitlines()

    def imports_method(self, conan_file):
        parameters = self._import_parameters

        def imports():
            for import_params in parameters:
                conan_file.copy(*import_params)
        return imports
