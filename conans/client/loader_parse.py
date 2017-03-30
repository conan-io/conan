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
    """Parse a plain requirements file"""

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
    def import_parameters(self):
        ret = []
        local_install_text = self._config_parser.imports
        for local_install_line in local_install_text.splitlines():
            invalid_line_msg = "Invalid imports line: %s" \
                               "\nEX: OpenCV/lib, * -> ./lib" % local_install_line
            try:
                if local_install_line.startswith("/") or local_install_line.startswith(".."):
                    raise ConanException("Import's paths can't begin with '/' or '..'")
                pair = local_install_line.split("->")
                source = pair[0].strip().split(',', 1)
                dest = pair[1].strip()
                src, pattern = source[0].strip(), source[1].strip()
                ret.append((pattern, dest, src))
            except ConanException as excp:
                raise ConanException("%s\n%s" % (invalid_line_msg, excp.message))
            except:
                raise ConanException(invalid_line_msg)
        return ret

    @property
    def generators(self):
        return self._config_parser.generators.splitlines()

    @staticmethod
    def imports_method(conan_file, parameters):
        def imports():
            for import_params in parameters:
                conan_file.copy(*import_params)
        return imports
