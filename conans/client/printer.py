import fnmatch
from collections import OrderedDict

from conans.client.output import Color
from conans.model.options import OptionsValues
from conans.model.ref import ConanFileReference


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

    def print_inspect(self, inspect):
        for k, v in inspect.items():
            if k == "default_options":
                if isinstance(v, str):
                    v = OptionsValues.loads(v)
                elif isinstance(v, tuple):
                    v = OptionsValues(v)
                elif isinstance(v, list):
                    v = OptionsValues(tuple(v))
            if isinstance(v, (dict, OptionsValues)):
                self._out.writeln("%s:" % k)
                for ok, ov in sorted(v.items()):
                    self._out.writeln("    %s: %s" % (ok, ov))
            else:
                self._out.writeln("%s: %s" % (k, str(v)))

    def print_info(self, data, _info, package_filter=None, show_paths=False, show_revisions=False):
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
            if show_paths:
                _print("export_folder")
                _print("source_folder")
                _print("build_folder")
                _print("package_folder")

            if show("remote") and is_ref:
                if "remote" in it:
                    self._out.writeln("    Remote: %s=%s" % (it["remote"]["name"],
                                                             it["remote"]["url"]),
                                      Color.BRIGHT_GREEN)
                else:
                    self._out.writeln("    Remote: None", Color.BRIGHT_GREEN)

            _print("url", name="URL")
            _print("homepage", name="Homepage")

            if show("license") and "license" in it:
                licenses_str = ", ".join(it["license"])
                lead_str = "Licenses" if len(it["license"]) > 1 else "License"
                self._out.writeln("    %s: %s" % (lead_str, licenses_str), Color.BRIGHT_GREEN)

            _print("author", name="Author")

            if show("topics") and "topics" in it:
                self._out.writeln("    Topics: %s" % ", ".join(it["topics"]), Color.BRIGHT_GREEN)

            _print("recipe", name="Recipe", color=None)
            if show_revisions:
                _print("revision", name="Revision", color=None)
            _print("binary", name="Binary", color=None)

            if show("binary_remote") and is_ref:
                if "binary_remote" in it:
                    self._out.writeln("    Binary remote: %s" % it["binary_remote"])
                else:
                    self._out.writeln("    Binary remote: None")

            _print("creation_date", show_field="date", name="Creation date")

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

    def print_search_recipes(self, search_info, pattern, raw, all_remotes_search):
        """ Print all the exported conans information
        param pattern: wildcards, e.g., "opencv/*"
        """
        if not search_info and not raw:
            warn_msg = "There are no packages"
            pattern_msg = " matching the '%s' pattern" % pattern
            self._out.info(warn_msg + pattern_msg if pattern else warn_msg)
            return

        if not raw:
            self._out.info("Existing package recipes:\n")
            for remote_info in search_info:
                if all_remotes_search:
                    self._out.highlight("Remote '%s':" % str(remote_info["remote"]))
                for conan_item in remote_info["items"]:
                    self._print_colored_line(str(conan_item["recipe"]["id"]), indent=0)
        else:
            for remote_info in search_info:
                if all_remotes_search:
                    self._out.writeln("Remote '%s':" % str(remote_info["remote"]))
                for conan_item in remote_info["items"]:
                    self._out.writeln(str(conan_item["recipe"]["id"]))

    def print_search_packages(self, search_info, ref, packages_query,
                              outdated=False):
        assert(isinstance(ref, ConanFileReference))
        self._out.info("Existing packages for recipe %s:\n" % str(ref))
        for remote_info in search_info:
            if remote_info["remote"]:
                self._out.info("Existing recipe in remote '%s':\n" % remote_info["remote"])

            if not remote_info["items"][0]["packages"]:
                if packages_query:
                    warn_msg = "There are no %spackages for reference '%s' matching the query '%s'" \
                               % ("outdated " if outdated else "", str(ref), packages_query)
                elif remote_info["items"][0]["recipe"]:
                    warn_msg = "There are no %spackages for reference '%s', but package recipe " \
                               "found." % ("outdated " if outdated else "", str(ref))
                self._out.info(warn_msg)
                continue

            ref = remote_info["items"][0]["recipe"]["id"]
            packages = remote_info["items"][0]["packages"]

            # Each package
            for package in packages:
                package_id = package["id"]
                self._print_colored_line("Package_ID", package_id, 1)
                for section in ("options", "settings", "requires"):
                    attr = package[section]
                    if attr:
                        self._print_colored_line("[%s]" % section, indent=2)
                        if isinstance(attr, dict):  # options, settings
                            attr = OrderedDict(sorted(attr.items()))
                            for key, value in attr.items():
                                self._print_colored_line(key, value=value, indent=3)
                        elif isinstance(attr, list):  # full requires
                            for key in sorted(attr):
                                self._print_colored_line(key, indent=3)
                # Always compare outdated with local recipe, simplification,
                # if a remote check is needed install recipe first
                if "outdated" in package:
                    self._print_colored_line("Outdated from recipe: %s" % package["outdated"],
                                             indent=2)
                self._out.writeln("")

    def print_profile(self, name, profile):
        self._out.info("Configuration for profile %s:\n" % name)
        self._print_profile_section("settings", profile.settings.items(), separator="=")
        self._print_profile_section("options", profile.options.as_list(), separator="=")
        self._print_profile_section("build_requires", [(key, ", ".join(str(val) for val in values))
                                                       for key, values in
                                                       profile.build_requires.items()])

        envs = []
        for package, env_vars in profile.env_values.data.items():
            for name, value in env_vars.items():
                key = "%s:%s" % (package, name) if package else name
                envs.append((key, value))
        self._print_profile_section("env", envs, separator='=')

    def _print_profile_section(self, name, items, indent=0, separator=": "):
        self._print_colored_line("[%s]" % name, indent=indent, color=Color.BRIGHT_RED)
        for key, value in items:
            self._print_colored_line(key, value=str(value), indent=0, separator=separator)

    def _print_colored_line(self, text, value=None, indent=0, separator=": ", color=None):
        """ Print a colored line depending on its indentation level
            Attributes:
                text: string line
                split_symbol: if you want an output with different in-line colors
                indent_plus: integer to add a plus indentation
        """
        text = text.strip()
        if not text:
            return

        text_color = Printer.INDENT_COLOR.get(indent, Color.BRIGHT_WHITE) if not color else color
        indent_text = ' ' * Printer.INDENT_SPACES * indent
        if value is not None:
            value_color = Color.BRIGHT_WHITE
            self._out.write('%s%s%s' % (indent_text, text, separator), text_color)
            self._out.writeln(value, value_color)
        else:
            self._out.writeln('%s%s' % (indent_text, text), text_color)
