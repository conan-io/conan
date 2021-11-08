import fnmatch

from conans.cli.output import Color


class Printer(object):
    """ Print some specific information """

    INDENT_COLOR = {0: Color.BRIGHT_CYAN,
                    1: Color.BRIGHT_RED,
                    2: Color.BRIGHT_GREEN,
                    3: Color.BRIGHT_YELLOW,
                    4: Color.BRIGHT_MAGENTA}

    INDENT_SPACES = 4

    def __init__(self, out):
        self._out = out

    def print_inspect(self, inspect, raw=False):
        for k, v in inspect.items():
            if raw:
                self._out.write(str(v))
            else:
                if isinstance(v, dict):
                    self._out.writeln("%s:" % k)
                    for ok, ov in sorted(v.items()):
                        self._out.writeln("    %s: %s" % (ok, ov))
                else:
                    self._out.writeln("%s: %s" % (k, str(v)))

    def print_info(self, data, _info, package_filter=None, show_paths=False):
        """ Print in console the dependency information for a conan file
        """
        if _info is None:  # No filter
            def show(_):
                return True
        else:
            _info_lower = [s.lower() for s in _info]

            def show(field):
                return field in _info_lower

        # Handy function to perform a common print task
        def _print(it_field, show_field=None, name=None, color=Color.BRIGHT_GREEN):
            show_field = show_field or it_field
            name = name or it_field
            if show(show_field) and it_field in it:
                self._out.writeln("    %s: %s" % (name, it[it_field]), color)

        # Iteration and printing
        for it in data:
            if package_filter and not fnmatch.fnmatch(it["reference"], package_filter):
                continue

            is_ref = it["is_ref"]

            self._out.writeln(it["display_name"], Color.BRIGHT_CYAN)
            _print("id", name="ID")
            _print("build_id", name="BuildID")
            _print("context", name="Context")
            if show_paths:
                _print("export_folder")
                _print("source_folder")
                _print("build_folder")
                _print("package_folder")

            _print("url", name="URL")
            _print("homepage", name="Homepage")

            if show("license") and "license" in it:
                licenses_str = ", ".join(it["license"])
                lead_str = "Licenses" if len(it["license"]) > 1 else "License"
                self._out.writeln("    %s: %s" % (lead_str, licenses_str), Color.BRIGHT_GREEN)

            _print("author", name="Author")
            _print("description", name="Description")

            if show("topics") and "topics" in it:
                self._out.writeln("    Topics: %s" % ", ".join(it["topics"]), Color.BRIGHT_GREEN)

            if show("provides") and "provides" in it:
                self._out.writeln("    Provides: %s" % ", ".join(it["provides"]), Color.BRIGHT_GREEN)

            _print("deprecated", name="Deprecated")

            _print("recipe", name="Recipe", color=None)
            _print("revision", name="Revision", color=None)
            _print("package_revision", name="Package revision", color=None)
            _print("binary", name="Binary", color=None)

            _print("creation_date", show_field="date", name="Creation date")

            _print("scm", show_field="scm", name="scm")

            if show("python_requires") and "python_requires" in it:
                self._out.writeln("    Python-requires:", Color.BRIGHT_GREEN)
                for d in it["python_requires"]:
                    self._out.writeln("        %s" % d, Color.BRIGHT_YELLOW)

            if show("required") and "required_by" in it:
                self._out.writeln("    Required by:", Color.BRIGHT_GREEN)
                for d in it["required_by"]:
                    self._out.writeln("        %s" % d, Color.BRIGHT_YELLOW)

            if show("requires"):
                if "requires" in it:
                    self._out.writeln("    Requires:", Color.BRIGHT_GREEN)
                    for d in it["requires"]:
                        self._out.writeln("        %s" % d, Color.BRIGHT_YELLOW)

                if "build_requires" in it:
                    self._out.writeln("    Build Requires:", Color.BRIGHT_GREEN)
                    for d in it["build_requires"]:
                        self._out.writeln("        %s" % d, Color.BRIGHT_YELLOW)
