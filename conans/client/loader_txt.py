from conans.errors import ConanException
from conans.util.config_parser import ConfigParser


class ConanFileTextLoader(object):
    """Parse a conanfile.txt file"""

    def __init__(self, input_text):
        # Prefer composition over inheritance, the __getattr__ was breaking things
        self._config_parser = ConfigParser(input_text,  ["requires", "generators", "options",
                                                         "imports", "build_requires"],
                                           parse_lines=True)

    @property
    def requirements(self):
        """returns a list of requires
        EX:  "OpenCV/2.4.10@phil/stable"
        """
        return [r.strip() for r in self._config_parser.requires.splitlines()]

    @property
    def build_requirements(self):
        """returns a list of build_requires
        EX:  "OpenCV/2.4.10@phil/stable"
        """
        return [r.strip() for r in self._config_parser.build_requires.splitlines()]

    @property
    def options(self):
        return self._config_parser.options

    @property
    def _import_parameters(self):
        def _parse_args(param_string):
            root_package, ignore_case, folder, excludes, keep_path = None, False, False, None, True
            params = param_string.split(",")
            params = [p.strip() for p in params if p.strip()]
            for param in params:
                try:
                    var, value = param.split("=")
                except ValueError:
                    raise ConanException("Wrong imports argument '%s'. "
                                         "Need a 'arg=value' pair." % param)
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
                elif var == "keep_path":
                    keep_path = (value.lower() == "true")
                else:
                    raise Exception("Invalid imports. Unknown argument %s" % var)
            return root_package, ignore_case, folder, excludes, keep_path

        def _parse_import(line):
            try:
                pair = line.split("->", 1)
                source = pair[0].strip().split(',', 1)
                dest = pair[1].strip()
                src, pattern = source[0].strip(), source[1].strip()
                return pattern, dest, src
            except Exception:
                raise ConanException("Wrong imports line: %s\n"
                                     "Use syntax: path, pattern -> local-folder" % line)

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
                tokens = line.rsplit("@", 1)
                if len(tokens) > 1:
                    line = tokens[0]
                    params = tokens[1]
                else:
                    params = ""
                root_package, ignore_case, folder, excludes, keep_path = _parse_args(params)
                pattern, dest, src = _parse_import(line)
                ret.append((pattern, dest, src, root_package, folder, ignore_case, excludes,
                            keep_path))
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
