import argparse
import inspect
import json
import os
import sys
from argparse import ArgumentError
from difflib import get_close_matches

from conans.assets import templates
from conans.cli.exit_codes import SUCCESS, ERROR_GENERAL, ERROR_INVALID_CONFIGURATION, \
    ERROR_INVALID_SYSTEM_REQUIREMENTS
from conans.cli.output import Color, ConanOutput
from conans.client.cmd.frogarian import cmd_frogarian
from conans.client.cmd.uploader import UPLOAD_POLICY_FORCE, UPLOAD_POLICY_SKIP
from conans.client.conan_api import ConanAPIV1, _make_abs_path, ProfileData
from conans.client.conan_command_output import CommandOutputer
from conans.client.conf.config_installer import is_config_install_scheduled
from conans.client.graph.install_graph import InstallGraph
from conans.client.printer import Printer
from conans.errors import ConanException, ConanInvalidConfiguration
from conans.errors import ConanInvalidSystemRequirements
from conans.model.conf import DEFAULT_CONFIGURATION
from conans.model.package_ref import PkgReference
from conans.model.ref import ConanFileReference, get_reference_fields, \
    check_valid_ref
from conans.util.config_parser import get_bool_from_text
from conans.util.files import exception_message_safe
from conans.util.files import save
from conans.util.log import logger


class Extender(argparse.Action):
    """Allows using the same flag several times in command and creates a list with the values.
    For example:
        conan install MyPackage/1.2@user/channel -o qt:value -o mode:2 -s cucumber:true
      It creates:
          options = ['qt:value', 'mode:2']
          settings = ['cucumber:true']
    """
    def __call__(self, parser, namespace, values, option_strings=None):  # @UnusedVariable
        # Need None here in case `argparse.SUPPRESS` was supplied for `dest`
        dest = getattr(namespace, self.dest, None)
        if not hasattr(dest, 'extend') or dest == self.default:
            dest = []
            setattr(namespace, self.dest, dest)
            # if default isn't set to None, this method might be called
            # with the default as `values` for other arguments which
            # share this destination.
            parser.set_defaults(**{self.dest: None})

        if isinstance(values, str):
            dest.append(values)
        elif values:
            try:
                dest.extend(values)
            except ValueError:
                dest.append(values)


class OnceArgument(argparse.Action):
    """Allows declaring a parameter that can have only one value, by default argparse takes the
    latest declared and it's very confusing.
    """
    def __call__(self, parser, namespace, values, option_string=None):
        if getattr(namespace, self.dest) is not None and self.default is None:
            msg = '{o} can only be specified once'.format(o=option_string)
            raise argparse.ArgumentError(None, msg)
        setattr(namespace, self.dest, values)


class SmartFormatter(argparse.HelpFormatter):

    def _fill_text(self, text, width, indent):
        import textwrap
        text = textwrap.dedent(text)
        return ''.join(indent + line for line in text.splitlines(True))


_QUERY_EXAMPLE = "os=Windows AND (arch=x86 OR compiler=gcc)"
_PATTERN_EXAMPLE = "boost/*"
_REFERENCE_EXAMPLE = "MyPackage/1.2@user/channel"
_PREF_EXAMPLE = "MyPackage/1.2@user/channel:af7901d8bdfde621d086181aa1c495c25a17b137"

_BUILD_FOLDER_HELP = ("Directory for the build process. Defaulted to the current directory. A "
                      "relative path to the current directory can also be specified")
_PATTERN_OR_REFERENCE_HELP = ("Pattern or package recipe reference, e.g., '%s', "
                              "'%s'" % (_PATTERN_EXAMPLE, _REFERENCE_EXAMPLE))
_PATTERN_REF_OR_PREF_HELP = ("Pattern, recipe reference or package reference e.g., '%s', "
                             "'%s', '%s'" % (_PATTERN_EXAMPLE, _REFERENCE_EXAMPLE, _PREF_EXAMPLE))
_REF_OR_PREF_HELP = ("Recipe reference or package reference e.g., '%s', "
                     "'%s'" % (_REFERENCE_EXAMPLE, _PREF_EXAMPLE))
_PATH_HELP = ("Path to a folder containing a conanfile.py or to a recipe file "
              "e.g., my_folder/conanfile.py")
_QUERY_HELP = ("Packages query: '%s'. The 'pattern_or_reference' parameter has "
               "to be a reference: %s" % (_QUERY_EXAMPLE, _REFERENCE_EXAMPLE))
_SOURCE_FOLDER_HELP = ("Directory containing the sources. Defaulted to the conanfile's directory. A"
                       " relative path to the current directory can also be specified")


class Command(object):
    """A single command of the conan application, with all the first level commands. Manages the
    parsing of parameters and delegates functionality in collaborators. It can also show the
    help of the tool.
    """
    def __init__(self, conan_api):
        assert isinstance(conan_api, ConanAPIV1)
        self._conan_api = conan_api
        self._out = ConanOutput()

    def new(self, *args):
        """
        Creates a new package recipe template with a 'conanfile.py' and optionally,
        'test_package' testing files.
        """
        parser = argparse.ArgumentParser(description=self.new.__doc__,
                                         prog="conan new",
                                         formatter_class=SmartFormatter)
        parser.add_argument("name", help='Package name, e.g.: "poco/1.9.4" or complete reference'
                                         ' for CI scripts: "poco/1.9.4@user/channel"')
        parser.add_argument("-t", "--test", action='store_true', default=False,
                            help='Create test_package skeleton to test package')
        parser.add_argument("-i", "--header", action='store_true', default=False,
                            help='Create a headers only package template')
        parser.add_argument("-c", "--pure-c", action='store_true', default=False,
                            help='Create a C language package only package, '
                                 'deleting "self.settings.compiler.libcxx" setting '
                                 'in the configure method')
        parser.add_argument("-s", "--sources", action='store_true', default=False,
                            help='Create a package with embedded sources in "src" folder, '
                                 'using "exports_sources" instead of retrieving external code with '
                                 'the "source()" method')
        parser.add_argument("-b", "--bare", action='store_true', default=False,
                            help='Create the minimum package recipe, without build() method. '
                            'Useful in combination with "export-pkg" command')
        parser.add_argument("-m", "--template",
                            help='Use the given template to generate a conan project')
        parser.add_argument("-gi", "--gitignore", action='store_true', default=False,
                            help='Generate a .gitignore with the known patterns to excluded')
        parser.add_argument('-d', '--define', action='append')

        args = parser.parse_args(*args)

        defines = args.define or []
        defines = dict((n, v) for n, v in (d.split('=') for d in defines))

        self._warn_python_version()
        self._conan_api.new(args.name, header=args.header, pure_c=args.pure_c, test=args.test,
                            exports_sources=args.sources, bare=args.bare,
                            gitignore=args.gitignore, template=args.template,
                            defines=defines)

    def inspect(self, *args):
        """
        Displays conanfile attributes, like name, version, and options. Works locally,
        in local cache and remote.
        """
        parser = argparse.ArgumentParser(description=self.inspect.__doc__,
                                         prog="conan inspect",
                                         formatter_class=SmartFormatter)
        parser.add_argument("path_or_reference", help="Path to a folder containing a recipe"
                            " (conanfile.py) or to a recipe file. e.g., "
                            "./my_project/conanfile.py. It could also be a reference")
        parser.add_argument("-a", "--attribute", help='The attribute to be displayed, e.g "name"',
                            nargs="?", action=Extender)
        parser.add_argument("-r", "--remote", help='look in the specified remote server',
                            action=OnceArgument)
        parser.add_argument("-j", "--json", default=None, action=OnceArgument,
                            help='json output file')
        parser.add_argument('--raw', default=None, action=OnceArgument,
                            help='Print just the value of the requested attribute')

        args = parser.parse_args(*args)

        if args.raw and args.attribute:
            raise ConanException("Argument '--raw' is incompatible with '-a'")

        if args.raw and args.json:
            raise ConanException("Argument '--raw' is incompatible with '--json'")

        attributes = [args.raw, ] if args.raw else args.attribute
        quiet = bool(args.raw)

        result = self._conan_api.inspect(args.path_or_reference, attributes, args.remote, quiet=quiet)
        Printer(self._out).print_inspect(result, raw=args.raw)
        if args.json:

            def dump_custom_types(obj):
                if isinstance(obj, set):
                    return sorted(list(obj))
                raise TypeError

            json_output = json.dumps(result, default=dump_custom_types)
            if not os.path.isabs(args.json):
                json_output_file = os.path.join(os.getcwd(), args.json)
            else:
                json_output_file = args.json
            save(json_output_file, json_output)

    def test(self, *args):
        """
        Tests a package consuming it from a conanfile.py with a test() method.

        This command installs the conanfile dependencies (including the tested
        package), calls a 'conan build' to build test apps and finally executes
        the test() method. The testing recipe does not require name or version,
        neither definition of package() or package_info() methods. The package
        to be tested must exist in the local cache or any configured remote.
        """
        parser = argparse.ArgumentParser(description=self.test.__doc__,
                                         prog="conan test",
                                         formatter_class=SmartFormatter)
        parser.add_argument("path", help='Path to the "testing" folder containing a conanfile.py or'
                            ' to a recipe file with test() method'
                            ' e.g. conan test_package/conanfile.py pkg/version@user/channel')
        parser.add_argument("reference",
                            help='pkg/version@user/channel of the package to be tested')
        parser.add_argument("-tbf", "--test-build-folder", action=OnceArgument,
                            help="Working directory of the build process.")

        _add_common_install_arguments(parser, build_help=_help_build_policies.format("never"))
        args = parser.parse_args(*args)

        self._warn_python_version()

        profile_build = ProfileData(profiles=args.profile_build, settings=args.settings_build,
                                    options=args.options_build, env=args.env_build,
                                    conf=args.conf_build)
        # TODO: 2.0 create profile_host object here to avoid passing a lot of arguments to the API

        return self._conan_api.test(args.path, args.reference,
                                args.profile_host, args.settings_host, args.options_host,
                                args.env_host, conf=args.conf_host, remote_name=args.remote,
                                update=args.update, build_modes=args.build,
                                test_build_folder=args.test_build_folder,
                                lockfile=args.lockfile, profile_build=profile_build)

    def create(self, *args):
        """
        Builds a binary package for a recipe (conanfile.py).

        Uses the specified configuration in a profile or in -s settings, -o
        options, etc. If a 'test_package' folder (the name can be configured
        with -tf) is found, the command will run the consumer project to ensure
        that the package has been created correctly. Check 'conan test' command
        to know more about 'test_folder' project.
        """
        parser = argparse.ArgumentParser(description=self.create.__doc__,
                                         prog="conan create",
                                         formatter_class=SmartFormatter)
        parser.add_argument("path", help=_PATH_HELP)
        parser.add_argument("reference", nargs='?', default=None,
                            help='user/channel, version@user/channel or pkg/version@user/channel '
                            '(if name or version declared in conanfile.py, they should match)')
        parser.add_argument("-j", "--json", default=None, action=OnceArgument,
                            help='json file path where the install information will be written to')
        parser.add_argument("-tbf", "--test-build-folder", action=OnceArgument,
                            help='Working directory for the build of the test project.')
        parser.add_argument("-tf", "--test-folder", action=OnceArgument,
                            help='Alternative test folder name. By default it is "test_package". '
                                 'Use "None" to skip the test stage')
        parser.add_argument("--ignore-dirty", default=False, action='store_true',
                            help='When using the "scm" feature with "auto" values, capture the'
                                 ' revision and url even if there are uncommitted changes')
        parser.add_argument("--build-require", action='store_true', default=False,
                            help='The provided reference is a build-require')
        parser.add_argument("--require-override", action="append",
                            help="Define a requirement override")

        _add_common_install_arguments(parser, build_help=_help_build_policies.format("package name"))

        args = parser.parse_args(*args)
        self._warn_python_version()

        name, version, user, channel, _ = get_reference_fields(args.reference,
                                                               user_channel_input=True)

        if any([user, channel]) and not all([user, channel]):
            # Or user/channel or nothing, but not partial
            raise ConanException("Invalid parameter '%s', "
                                 "specify the full reference or user/channel" % args.reference)

        if args.test_folder == "None":
            # Now if parameter --test-folder=None (string None) we have to skip tests
            args.test_folder = False

        cwd = os.getcwd()

        info = None
        try:
            profile_build = ProfileData(profiles=args.profile_build, settings=args.settings_build,
                                        options=args.options_build, env=args.env_build,
                                        conf=args.conf_build)
            # TODO: 2.0 create profile_host object here to avoid passing a lot of arguments
            #       to the API

            info = self._conan_api.create(args.path, name=name, version=version, user=user,
                                          channel=channel, profile_names=args.profile_host,
                                          settings=args.settings_host, conf=args.conf_host,
                                          options=args.options_host, env=args.env_host,
                                          test_folder=args.test_folder,
                                          build_modes=args.build,
                                          remote_name=args.remote, update=args.update,
                                          test_build_folder=args.test_build_folder,
                                          lockfile=args.lockfile,
                                          lockfile_out=args.lockfile_out,
                                          ignore_dirty=args.ignore_dirty,
                                          profile_build=profile_build,
                                          is_build_require=args.build_require,
                                          require_overrides=args.require_override)
        except ConanException as exc:
            raise
        finally:
            if args.json and info:
                CommandOutputer().json_output(info, args.json, cwd)

    def download(self, *args):
        """
        Downloads recipe and binaries to the local cache, without using settings.

        It works specifying the recipe reference and package ID to be
        installed. Not transitive, requirements of the specified reference will
        NOT be retrieved. Only if a reference is specified, it will download all
        packages from the specified remote. If no remote is specified, it will use the default remote.
        """

        parser = argparse.ArgumentParser(description=self.download.__doc__,
                                         prog="conan download",
                                         formatter_class=SmartFormatter)
        parser.add_argument("reference",
                            help='pkg/version@user/channel')
        parser.add_argument("-p", "--package", nargs=1, action=Extender,
                            help='Force install specified package ID (ignore settings/options)'
                                 ' [DEPRECATED: use full reference instead]')
        parser.add_argument("-r", "--remote", help='look in the specified remote server',
                            action=OnceArgument)
        parser.add_argument("-re", "--recipe", help='Downloads only the recipe', default=False,
                            action="store_true")

        args = parser.parse_args(*args)

        try:
            pref = PkgReference.loads(args.reference)
        except ConanException:
            reference = args.reference
            packages_list = args.package

            if packages_list:
                self._out.warning("Usage of `--package` argument is deprecated."
                                  " Use a full reference instead: "
                                  "`conan download [...] {}:{}`".format(reference, packages_list[0]))
        else:
            reference = repr(pref.ref)
            if pref.ref.user is None:
                if pref.ref.revision:
                    reference = "%s/%s@#%s" % (pref.ref.name, pref.ref.version, pref.ref.revision)
                else:
                    reference += "@"
            pkgref = "{}#{}".format(pref.package_id, pref.revision) \
                if pref.revision else pref.package_id
            packages_list = [pkgref]
            if args.package:
                raise ConanException("Use a full package reference (preferred) or the `--package`"
                                     " command argument, but not both.")

        self._warn_python_version()
        return self._conan_api.download(reference=reference, packages=packages_list,
                                        remote_name=args.remote, recipe=args.recipe)

    def install(self, *args):
        """
        Installs the requirements specified in a recipe (conanfile.py or conanfile.txt).

        It can also be used to install a concrete package specifying a
        reference. If any requirement is not found in the local cache, it will
        retrieve the recipe from a remote, looking for it sequentially in the
        configured remotes. When the recipes have been downloaded it will try
        to download a binary package matching the specified settings, only from
        the remote from which the recipe was retrieved. If no binary package is
        found, it can be built from sources using the '--build' option. When
        the package is installed, Conan will write the files for the specified
        generators.
        """
        parser = argparse.ArgumentParser(description=self.install.__doc__,
                                         prog="conan install",
                                         formatter_class=SmartFormatter)
        parser.add_argument("path_or_reference", help="Path to a folder containing a recipe"
                            " (conanfile.py or conanfile.txt) or to a recipe file. e.g., "
                            "./my_project/conanfile.txt. It could also be a reference")
        parser.add_argument("reference", nargs="?",
                            help='Reference for the conanfile path of the first argument: '
                            'user/channel, version@user/channel or pkg/version@user/channel'
                            '(if name or version declared in conanfile.py, they should match)')
        parser.add_argument("-g", "--generator", nargs=1, action=Extender,
                            help='Generators to use')
        parser.add_argument("-if", "--install-folder", action=OnceArgument,
                            help='Use this directory as the directory where to put the generator'
                                 'files.')

        parser.add_argument("--no-imports", action='store_true', default=False,
                            help='Install specified packages but avoid running imports')
        parser.add_argument("--build-require", action='store_true', default=False,
                            help='The provided reference is a build-require')
        parser.add_argument("-j", "--json", default=None, action=OnceArgument,
                            help='Path to a json file where the install information will be '
                            'written')

        _add_common_install_arguments(parser, build_help=_help_build_policies.format("never"))
        parser.add_argument("--require-override", action="append",
                            help="Define a requirement override")

        args = parser.parse_args(*args)

        profile_build = ProfileData(profiles=args.profile_build, settings=args.settings_build,
                                    options=args.options_build, env=args.env_build,
                                    conf=args.conf_build)
        # TODO: 2.0 create profile_host object here to avoid passing a lot of arguments to the API

        cwd = os.getcwd()

        # We need @ otherwise it could be a path, so check strict
        path_is_reference = check_valid_ref(args.path_or_reference)

        info = None
        try:
            if not path_is_reference:
                name, version, user, channel, _ = get_reference_fields(args.reference,
                                                                       user_channel_input=True)
                info = self._conan_api.install(path=args.path_or_reference,
                                               name=name, version=version, user=user, channel=channel,
                                               settings=args.settings_host, options=args.options_host,
                                               env=args.env_host, profile_names=args.profile_host,
                                               conf=args.conf_host,
                                               profile_build=profile_build,
                                               remote_name=args.remote,
                                               build=args.build,
                                               update=args.update, generators=args.generator,
                                               no_imports=args.no_imports,
                                               install_folder=args.install_folder,
                                               lockfile=args.lockfile,
                                               lockfile_out=args.lockfile_out,
                                               require_overrides=args.require_override)
            else:
                if args.reference:
                    raise ConanException("A full reference was provided as first argument, second "
                                         "argument not allowed")

                ref = ConanFileReference.loads(args.path_or_reference, validate=False)
                info = self._conan_api.install_reference(ref,
                                                         settings=args.settings_host,
                                                         options=args.options_host,
                                                         env=args.env_host,
                                                         conf=args.conf_host,
                                                         profile_names=args.profile_host,
                                                         profile_build=profile_build,
                                                         remote_name=args.remote,
                                                         build=args.build,
                                                         update=args.update,
                                                         generators=args.generator,
                                                         install_folder=args.install_folder,
                                                         lockfile=args.lockfile,
                                                         lockfile_out=args.lockfile_out,
                                                         is_build_require=args.build_require,
                                                         require_overrides=args.require_override)

        except ConanException as exc:
            raise
        finally:
            if args.json and info:
                CommandOutputer().json_output(info, args.json, cwd)

    def config(self, *args):
        """
        Manages Conan configuration.

        Used to edit conan.conf, or install config files.
        """
        parser = argparse.ArgumentParser(description=self.config.__doc__,
                                         prog="conan config",
                                         formatter_class=SmartFormatter)

        subparsers = parser.add_subparsers(dest='subcommand', help='sub-command help')
        subparsers.required = True

        home_subparser = subparsers.add_parser('home', help='Retrieve the Conan home directory')
        install_subparser = subparsers.add_parser('install', help='Install a full configuration '
                                                                  'from a local or remote zip file')
        init_subparser = subparsers.add_parser('init', help='Initializes Conan configuration files')
        subparsers.add_parser('list', help='List Conan configuration properties')

        home_subparser.add_argument("-j", "--json", default=None, action=OnceArgument,
                                    help='json file path where the config home will be written to')
        install_subparser.add_argument("item", nargs="?",
                                       help="git repository, local file or folder or zip file (local or "
                                       "http) where the configuration is stored")

        install_subparser.add_argument("--verify-ssl", nargs="?", default="True",
                                       help='Verify SSL connection when downloading file')
        install_subparser.add_argument("-t", "--type", choices=["git", "dir", "file", "url"],
                                       help='Type of remote config')
        install_subparser.add_argument("-a", "--args",
                                       help='String with extra arguments for "git clone"')
        install_subparser.add_argument("-sf", "--source-folder",
                                       help='Install files only from a source subfolder from the '
                                       'specified origin')
        install_subparser.add_argument("-tf", "--target-folder",
                                       help='Install to that path in the conan cache')
        install_subparser.add_argument("-l", "--list", default=False, action='store_true',
                                       help='List stored configuration origins')
        install_subparser.add_argument("-r", "--remove", type=int,
                                       help='Remove configuration origin by index in list (index '
                                            'provided by --list argument)')
        init_subparser.add_argument('-f', '--force', default=False, action='store_true',
                                    help='Overwrite existing Conan configuration files')

        args = parser.parse_args(*args)

        if args.subcommand == "home":
            conan_home = self._conan_api.config_home()
            self._out.info(conan_home)
            if args.json:
                CommandOutputer().json_output({"home": conan_home}, args.json, os.getcwd())
            return conan_home
        elif args.subcommand == "install":
            if args.list:
                configs = self._conan_api.config_install_list()
                for index, config in enumerate(configs):
                    self._out.info("%s: %s" % (index, config))
                return
            elif args.remove is not None:
                self._conan_api.config_install_remove(index=args.remove)
                return
            verify_ssl = get_bool_from_text(args.verify_ssl)
            return self._conan_api.config_install(args.item, verify_ssl, args.type, args.args,
                                              source_folder=args.source_folder,
                                              target_folder=args.target_folder)
        elif args.subcommand == 'init':
            return self._conan_api.config_init(force=args.force)
        elif args.subcommand == "list":
            self._out.info("Supported Conan *experimental* global.conf and [conf] properties:")
            for key, value in DEFAULT_CONFIGURATION.items():
                self._out.info("{}: {}".format(key, value))

    def graph(self, *args):
        """
        Graph related commands: build-order
        """
        parser = argparse.ArgumentParser(description=self.graph.__doc__,
                                         prog="conan graph",
                                         formatter_class=SmartFormatter)
        subparsers = parser.add_subparsers(dest='subcommand', help='sub-command help')
        subparsers.required = True

        parser_build_order = subparsers.add_parser('build-order', help='Compute the build-order')
        parser_build_order.add_argument("path", nargs="?", help="Path to a conanfile")
        parser_build_order.add_argument("--reference", action=OnceArgument,
                                        help='Provide a package reference instead of a conanfile')
        parser_build_order.add_argument("--json", action=OnceArgument,
                                        help='Save the build-order, in json file')
        _add_common_install_arguments(parser_build_order, build_help="Build policy")

        parser_build_order_merge = subparsers.add_parser('build-order-merge',
                                                         help='Merge several build-order')
        parser_build_order_merge.add_argument("--file", nargs="?", action=Extender,
                                              help="Files to be merged")
        parser_build_order_merge.add_argument("--json", action=OnceArgument,
                                              help='Save the build-order, in json file')
        args = parser.parse_args(*args)

        if args.subcommand == "build-order":
            profile_build = ProfileData(profiles=args.profile_build, settings=args.settings_build,
                                        options=args.options_build, env=args.env_build,
                                        conf=args.conf_build)
            path_or_reference = args.path if args.path is not None else args.reference
            if path_or_reference is None:
                raise ConanException("Please define either the path to a conanfile or a reference")
            # TODO: Change API
            data = self._conan_api.info(path_or_reference,
                                        remote_name=args.remote,
                                        settings=args.settings_host,
                                        options=args.options_host,
                                        env=args.env_host,
                                        profile_names=args.profile_host,
                                        conf=args.conf_host,
                                        profile_build=profile_build,
                                        update=args.update,
                                        build=args.build,
                                        lockfile=args.lockfile)
            deps_graph, _ = data
            install_graph = InstallGraph(deps_graph)
            install_order_serialized = install_graph.install_build_order()
            json_result = json.dumps(install_order_serialized, indent=4)
            self._out.writeln(json_result)
            if args.json:
                save(_make_abs_path(args.json), json_result)
        elif args.subcommand == "build-order-merge":
            result = InstallGraph()
            for f in args.file:
                f = _make_abs_path(f)
                install_graph = InstallGraph.load(f)
                result.merge(install_graph)

            install_order_serialized = result.install_build_order()
            json_result = json.dumps(install_order_serialized, indent=4)
            self._out.writeln(json_result)
            if args.json:
                save(_make_abs_path(args.json), json_result)

    def info(self, *args):
        """
        Gets information about the dependency graph of a recipe.

        It can be used with a recipe or a reference for any existing package in
        your local cache.
        """

        info_only_options = ["id", "build_id", "remote", "url", "license", "requires", "update",
                             "required", "date", "author", "description", "provides", "deprecated",
                             "None"]
        path_only_options = ["export_folder", "build_folder", "package_folder", "source_folder"]
        str_path_only_options = ", ".join(['"%s"' % field for field in path_only_options])
        str_only_options = ", ".join(['"%s"' % field for field in info_only_options])

        parser = argparse.ArgumentParser(description=self.info.__doc__,
                                         prog="conan info",
                                         formatter_class=SmartFormatter)
        parser.add_argument("path_or_reference", help="Path to a folder containing a recipe"
                            " (conanfile.py or conanfile.txt) or to a recipe file. e.g., "
                            "./my_project/conanfile.txt. It could also be a reference")
        parser.add_argument("--name", action=OnceArgument, help='Provide a package name '
                                                                'if not specified in conanfile')
        parser.add_argument("--version", action=OnceArgument, help='Provide a package version '
                                                                   'if not specified in conanfile')
        parser.add_argument("--user", action=OnceArgument, help='Provide a user')
        parser.add_argument("--channel", action=OnceArgument, help='Provide a channel')
        parser.add_argument("--paths", action='store_true', default=False,
                            help='Show package paths in local cache')
        parser.add_argument("-g", "--graph", action=OnceArgument,
                            help='Creates file with project dependencies graph. It will generate '
                            'a DOT or HTML file depending on the filename extension')
        parser.add_argument("-j", "--json", nargs='?', const="1", type=str,
                            help='Path to a json file where the information will be written')
        parser.add_argument("-n", "--only", nargs=1, action=Extender,
                            help="Show only the specified fields: %s. '--paths' information can "
                            "also be filtered with options %s. Use '--only None' to show only "
                            "references." % (str_only_options, str_path_only_options))
        parser.add_argument("--package-filter", nargs='?',
                            help='Print information only for packages that match the filter pattern'
                                 ' e.g., MyPackage/1.2@user/channel or MyPackage*')
        build_help = ("Given a build policy, return an ordered list of packages that would be built"
                      " from sources during the install command")
        update_help = "Will check if updates of the dependencies exist in the remotes " \
                      "(a new version that satisfies a version range, a new revision or a newer " \
                      "recipe if not using revisions)."
        _add_common_install_arguments(parser, update_help=update_help, build_help=build_help)
        args = parser.parse_args(*args)

        profile_build = ProfileData(profiles=args.profile_build, settings=args.settings_build,
                                    options=args.options_build, env=args.env_build,
                                    conf=args.conf_build)
        # TODO: 2.0 create profile_host object here to avoid passing a lot of arguments to the API

        # INFO ABOUT DEPS OF CURRENT PROJECT OR REFERENCE
        data = self._conan_api.info(args.path_or_reference,
                                remote_name=args.remote,
                                settings=args.settings_host,
                                options=args.options_host,
                                env=args.env_host,
                                profile_names=args.profile_host,
                                conf=args.conf_host,
                                profile_build=profile_build,
                                update=args.update,
                                build=args.build,
                                lockfile=args.lockfile,
                                name=args.name,
                                version=args.version,
                                user=args.user,
                                channel=args.channel)
        deps_graph, _ = data
        only = args.only
        if args.only == ["None"]:
            only = []
        if only and args.paths and (set(only) - set(path_only_options)):
            raise ConanException("Invalid --only value '%s' with --path specified, allowed "
                                 "values: [%s]." % (only, str_path_only_options))
        elif only and not args.paths and (set(only) - set(info_only_options)):
            raise ConanException("Invalid --only value '%s', allowed values: [%s].\n"
                                 "Use --only=None to show only the references."
                                 % (only, str_only_options))

        if args.graph:
            if args.graph.endswith(".html"):
                template = self._conan_api.get_template_path(templates.INFO_GRAPH_HTML,
                                                             user_overrides=True)
            else:
                template = self._conan_api.get_template_path(templates.INFO_GRAPH_DOT,
                                                             user_overrides=True)
            CommandOutputer().info_graph(args.graph, deps_graph, os.getcwd(), template=template,
                                         cache_folder=self._conan_api.cache_folder)
        if args.json:
            json_arg = True if args.json == "1" else args.json
            CommandOutputer().json_info(deps_graph, json_arg, os.getcwd(), show_paths=args.paths)

        if not args.graph and not args.json:
            CommandOutputer().info(deps_graph, only, args.package_filter, args.paths)

        # TODO: Check this UX or flow
        if deps_graph.error:
            raise deps_graph.error

    def source(self, *args):
        """
        Calls your local conanfile.py 'source()' method.

        Usually downloads and uncompresses the package sources.
        """
        parser = argparse.ArgumentParser(description=self.source.__doc__,
                                         prog="conan source",
                                         formatter_class=SmartFormatter)
        parser.add_argument("path", help=_PATH_HELP)
        parser.add_argument("-sf", "--source-folder", action=OnceArgument,
                            help='Destination directory. Defaulted to current directory')
        args = parser.parse_args(*args)

        try:
            if "@" in args.path and ConanFileReference.loads(args.path):
                raise ArgumentError(None,
                                    "'conan source' doesn't accept a reference anymore. "
                                    "If you were using it as a concurrency workaround, "
                                    "you can call 'conan install' simultaneously from several "
                                    "different processes, the concurrency is now natively supported"
                                    ". The path parameter should be a folder containing a "
                                    "conanfile.py file.")
        except ConanException:
            pass

        self._warn_python_version()
        return self._conan_api.source(args.path, args.source_folder)

    def build(self, *args):
        """
        Calls your local conanfile.py 'build()' method.

        The recipe will be built in the local directory specified by
        --build-folder, reading the sources from --source-folder. If you are
        using a build helper, like CMake(), the --package-folder will be
        configured as the destination folder for the install step.
        """

        parser = argparse.ArgumentParser(description=self.build.__doc__,
                                         prog="conan build",
                                         formatter_class=SmartFormatter)
        parser.add_argument("path", help=_PATH_HELP)
        parser.add_argument("--name", action=OnceArgument, help='Provide a package name '
                                                                'if not specified in conanfile')
        parser.add_argument("--version", action=OnceArgument, help='Provide a package version '
                                                                   'if not specified in conanfile')
        parser.add_argument("--user", action=OnceArgument, help='Provide a user')
        parser.add_argument("--channel", action=OnceArgument, help='Provide a channel')
        parser.add_argument("-bf", "--build-folder", action=OnceArgument, help=_BUILD_FOLDER_HELP)
        parser.add_argument("-pf", "--package-folder", action=OnceArgument,
                            help="Directory to install the package (when the build system or "
                                 "build() method does it). Defaulted to the '{build_folder}/package' "
                                 "folder. A relative path can be specified, relative to the current "
                                 "folder. Also an absolute path is allowed.")
        parser.add_argument("-sf", "--source-folder", action=OnceArgument, help=_SOURCE_FOLDER_HELP)

        parser.add_argument("-g", "--generator", nargs=1, action=Extender,
                            help='Generators to use')

        parser.add_argument("-if", "--install-folder", action=OnceArgument,
                            help='Use this directory as the directory where to put the generator'
                                 'files.')

        parser.add_argument("--no-imports", action='store_true', default=False,
                            help='Install specified packages but avoid running imports')
        parser.add_argument("-j", "--json", default=None, action=OnceArgument,
                            help='Path to a json file where the install information will be '
                                 'written')

        _add_common_install_arguments(parser, build_help=_help_build_policies.format("never"))
        parser.add_argument("--lockfile-node-id", action=OnceArgument,
                            help="NodeID of the referenced package in the lockfile")

        args = parser.parse_args(*args)

        profile_build = ProfileData(profiles=args.profile_build, settings=args.settings_build,
                                    options=args.options_build, env=args.env_build,
                                    conf=args.conf_build)

        self._warn_python_version()

        info = None
        try:
            info = self._conan_api.build(conanfile_path=args.path,
                                     name=args.name,
                                     version=args.version,
                                     user=args.user,
                                     channel=args.channel,
                                     source_folder=args.source_folder,
                                     package_folder=args.package_folder,
                                     build_folder=args.build_folder,
                                     install_folder=args.install_folder,
                                     settings=args.settings_host, options=args.options_host,
                                     env=args.env_host, profile_names=args.profile_host,
                                     profile_build=profile_build,
                                     remote_name=args.remote,
                                     build=args.build,
                                     update=args.update, generators=args.generator,
                                     no_imports=args.no_imports,
                                     lockfile=args.lockfile,
                                     lockfile_out=args.lockfile_out, conf=args.conf_host)
        except ConanException as exc:
            info = exc.info
            raise
        finally:
            if args.json and info:
                CommandOutputer().json_output(info, args.json, os.getcwd())

    def imports(self, *args):
        """
        Calls your local conanfile.py or conanfile.txt 'imports' method.
        """

        parser = argparse.ArgumentParser(description=self.imports.__doc__,
                                         prog="conan imports",
                                         formatter_class=SmartFormatter)
        parser.add_argument("path",
                            help=_PATH_HELP + " With --undo option, this parameter is the folder "
                            "containing the conan_imports_manifest.txt file generated in a previous"
                            " execution. e.g.: conan imports ./imported_files --undo ")
        parser.add_argument("-imf", "--import-folder", action=OnceArgument,
                            help="Directory to copy the artifacts to. By default it will be the"
                                 " current directory")
        parser.add_argument("-u", "--undo", default=False, action="store_true",
                            help="Undo imports. Remove imported files")
        parser.add_argument("-l", "--lockfile", action=OnceArgument,
                            help="Path to a lockfile")
        _add_profile_arguments(parser)

        args = parser.parse_args(*args)

        if args.undo:
            return self._conan_api.imports_undo(args.path)

        try:
            if "@" in args.path and ConanFileReference.loads(args.path):
                raise ArgumentError(None, "Parameter 'path' cannot be a reference. Use a folder "
                                          "containing a conanfile.py or conanfile.txt file.")
        except ConanException:
            pass
        self._warn_python_version()

        profile_build = ProfileData(profiles=args.profile_build, settings=args.settings_build,
                                    options=args.options_build, env=args.env_build,
                                    conf=args.conf_build)

        self._warn_python_version()

        self._conan_api.imports(args.path,
                            args.import_folder, settings=args.settings_host,
                            options=args.options_host, env=args.env_host,
                            profile_names=args.profile_host, profile_build=profile_build,
                            lockfile=args.lockfile)

    def export_pkg(self, *args):
        """
        Exports a recipe, then creates a package from local source and build folders.

        If '--package-folder' is provided it will copy the files from there, otherwise, it
        will execute package() method over '--source-folder' and '--build-folder' to create
        the binary package.
        """

        parser = argparse.ArgumentParser(description=self.export_pkg.__doc__,
                                         prog="conan export-pkg",
                                         formatter_class=SmartFormatter)
        parser.add_argument("path", help=_PATH_HELP)
        parser.add_argument("reference", nargs='?', default=None,
                            help="user/channel or pkg/version@user/channel "
                                 "(if name and version are not declared in the "
                                 "conanfile.py)")

        parser.add_argument("-bf", "--build-folder", action=OnceArgument, help=_BUILD_FOLDER_HELP)
        parser.add_argument('-f', '--force', default=False, action='store_true',
                            help='Overwrite existing package if existing')
        parser.add_argument("-pf", "--package-folder", action=OnceArgument,
                            help="folder containing a locally created package. If a value is given,"
                                 " it won't call the recipe 'package()' method, and will run a copy"
                                 " of the provided folder.")
        parser.add_argument("-sf", "--source-folder", action=OnceArgument, help=_SOURCE_FOLDER_HELP)
        parser.add_argument("-j", "--json", default=None, action=OnceArgument,
                            help='Path to a json file where the install information will be '
                            'written')
        parser.add_argument("-l", "--lockfile", action=OnceArgument,
                            help="Path to a lockfile.")
        parser.add_argument("--lockfile-out", action=OnceArgument,
                            help="Filename of the updated lockfile")
        parser.add_argument("--ignore-dirty", default=False, action='store_true',
                            help='When using the "scm" feature with "auto" values, capture the'
                                 ' revision and url even if there are uncommitted changes')
        _add_profile_arguments(parser)

        args = parser.parse_args(*args)
        self._warn_python_version()

        name, version, user, channel, _ = get_reference_fields(args.reference,
                                                               user_channel_input=True)
        cwd = os.getcwd()
        info = None

        try:
            profile_build = ProfileData(profiles=args.profile_build, settings=args.settings_build,
                                        options=args.options_build, env=args.env_build,
                                        conf=args.conf_build)
            # TODO: 2.0 create profile_host object here to avoid passing a lot of arguments
            #       to the API

            info = self._conan_api.export_pkg(conanfile_path=args.path,
                                          name=name,
                                          version=version,
                                          source_folder=args.source_folder,
                                          build_folder=args.build_folder,
                                          package_folder=args.package_folder,
                                          profile_names=args.profile_host,
                                          env=args.env_host,
                                          settings=args.settings_host,
                                          options=args.options_host,
                                          conf=args.conf_host,
                                          profile_build=profile_build,
                                          force=args.force,
                                          user=user,
                                          channel=channel,
                                          lockfile=args.lockfile,
                                          lockfile_out=args.lockfile_out,
                                          ignore_dirty=args.ignore_dirty)
        except ConanException as exc:
            info = exc.info
            raise
        finally:
            if args.json and info:
                CommandOutputer().json_output(info, args.json, cwd)

    def export(self, *args):
        """
        Copies the recipe (conanfile.py & associated files) to your local cache.

        Use the 'reference' param to specify a user and channel where to export
        it. Once the recipe is in the local cache it can be shared and reused
        with any remote with the 'conan upload' command.
        """
        parser = argparse.ArgumentParser(description=self.export.__doc__,
                                         prog="conan export",
                                         formatter_class=SmartFormatter)
        parser.add_argument("path", help=_PATH_HELP)
        parser.add_argument("reference", nargs='?', default=None,
                            help="user/channel, Pkg/version@user/channel (if name "
                                 "and version are not declared in the conanfile.py) "
                                 "Pkg/version@ if user/channel is not relevant.")
        parser.add_argument("-l", "--lockfile", action=OnceArgument,
                            help="Path to a lockfile file.")
        parser.add_argument("--lockfile-out", action=OnceArgument,
                            help="Filename of the updated lockfile")
        parser.add_argument("--ignore-dirty", default=False, action='store_true',
                            help='When using the "scm" feature with "auto" values, capture the'
                                 ' revision and url even if there are uncommitted changes')

        args = parser.parse_args(*args)
        self._warn_python_version()
        if args.lockfile_out and not args.lockfile:
            raise ConanException("lockfile_out cannot be specified if lockfile is not defined")

        name, version, user, channel, _ = get_reference_fields(args.reference,
                                                               user_channel_input=True)

        if any([user, channel]) and not all([user, channel]):
            # Or user/channel or nothing, but not partial
            raise ConanException("Invalid parameter '%s', "
                                 "specify the full reference or user/channel" % args.reference)

        return self._conan_api.export(path=args.path,
                                  name=name, version=version, user=user, channel=channel,
                                  lockfile=args.lockfile,
                                  lockfile_out=args.lockfile_out,
                                  ignore_dirty=args.ignore_dirty)

    def remove(self, *args):
        """
        Removes packages or binaries matching pattern from local cache or remote.

        It can also be used to remove the temporary source or build folders in the
        local conan cache. If no remote is specified, the removal will be done
        by default in the local conan cache.
        """
        parser = argparse.ArgumentParser(description=self.remove.__doc__,
                                         prog="conan remove",
                                         formatter_class=SmartFormatter)
        parser.add_argument('pattern_or_reference', nargs="?", help=_PATTERN_OR_REFERENCE_HELP)
        parser.add_argument('-b', '--builds', nargs="*", action=Extender,
                            help=("By default, remove all the build folders or select one, "
                                  "specifying the package ID"))
        parser.add_argument('-f', '--force', default=False, action='store_true',
                            help='Remove without requesting a confirmation')
        parser.add_argument("-l", "--locks", default=False, action="store_true",
                            help="Remove locks")
        parser.add_argument('-p', '--packages', nargs="*", action=Extender,
                            help="Remove all packages of the specified reference if "
                                 "no specific package ID is provided")
        parser.add_argument('-q', '--query', default=None, action=OnceArgument, help=_QUERY_HELP)
        parser.add_argument('-r', '--remote', action=OnceArgument,
                            help='Will remove from the specified remote')
        parser.add_argument('-s', '--src', default=False, action="store_true",
                            help='Remove source folders')
        parser.add_argument('-t', '--system-reqs', default=False, action="store_true",
                            help='Remove system_reqs folders')
        args = parser.parse_args(*args)

        self._warn_python_version()

        if args.packages is not None and args.query:
            raise ConanException("'-q' and '-p' parameters can't be used at the same time")

        if args.builds is not None and args.query:
            raise ConanException("'-q' and '-b' parameters can't be used at the same time")

        if args.locks:
            if args.pattern_or_reference:
                raise ConanException("Specifying a pattern is not supported when removing locks")
            self._conan_api.remove_locks()
            self._out.info("Cache locks removed")
            return
        elif args.system_reqs:
            if args.packages:
                raise ConanException("'-t' and '-p' parameters can't be used at the same time")
            if not args.pattern_or_reference:
                raise ConanException("Please specify a valid pattern or reference to be cleaned")

            if check_valid_ref(args.pattern_or_reference):
                return self._conan_api.remove_system_reqs(args.pattern_or_reference)

            return self._conan_api.remove_system_reqs_by_pattern(args.pattern_or_reference)
        else:
            if not args.pattern_or_reference:
                raise ConanException('Please specify a pattern to be removed ("*" for all)')

        try:
            pref = PkgReference.loads(args.pattern_or_reference)
            packages = [pref.package_id]
            pattern_or_reference = repr(pref.ref)
        except ConanException:
            pref = None
            pattern_or_reference = args.pattern_or_reference
            packages = args.packages

        if pref and args.packages:
            raise ConanException("Use package ID only as -p argument or reference, not both")

        return self._conan_api.remove(pattern=pattern_or_reference, query=args.query,
                                  packages=packages, builds=args.builds, src=args.src,
                                  force=args.force, remote_name=args.remote)

    def upload(self, *args):
        """
        Uploads a recipe and binary packages to a remote.

        If no remote is specified, it fails.
        """
        parser = argparse.ArgumentParser(description=self.upload.__doc__,
                                         prog="conan upload",
                                         formatter_class=SmartFormatter)
        parser.add_argument('pattern_or_reference', help=_PATTERN_REF_OR_PREF_HELP)
        parser.add_argument("-p", "--package", default=None,
                            help="Package ID [DEPRECATED: use full reference instead]",
                            action=OnceArgument)
        parser.add_argument('-q', '--query', default=None, action=OnceArgument,
                            help="Only upload packages matching a specific query. " + _QUERY_HELP)
        # using required, we may want to pass this as a positional argument?
        parser.add_argument("-r", "--remote", action=OnceArgument, required=True,
                            help='upload to this specific remote')
        parser.add_argument("--all", action='store_true', default=False,
                            help='Upload both package recipe and packages')
        parser.add_argument("--skip-upload", action='store_true', default=False,
                            help='Do not upload anything, just run the checks and the compression')
        parser.add_argument("--force", action='store_true', default=False,
                            help='Ignore checks before uploading the recipe: it will bypass missing'
                                 ' fields in the scm attribute and it will override remote recipe'
                                 ' with local regardless of recipe date')
        parser.add_argument("--check", action='store_true', default=False,
                            help='Perform an integrity check, using the manifests, before upload')
        parser.add_argument('-c', '--confirm', default=False, action='store_true',
                            help='Upload all matching recipes without confirmation')
        parser.add_argument('--retry', default=None, type=int, action=OnceArgument,
                            help="In case of fail retries to upload again the specified times.")
        parser.add_argument('--retry-wait', default=None, type=int, action=OnceArgument,
                            help='Waits specified seconds before retry again')
        parser.add_argument("-j", "--json", default=None, action=OnceArgument,
                            help='json file path where the upload information will be written to')
        parser.add_argument("--parallel", action='store_true', default=False,
                            help='Upload files in parallel using multiple threads. '
                                 'The default number of launched threads is set to the value of '
                                 'cpu_count and can be configured using the CONAN_CPU_COUNT '
                                 'environment variable or defining cpu_count in conan.conf')

        args = parser.parse_args(*args)

        try:
            pref = PkgReference.loads(args.pattern_or_reference)
        except ConanException:
            reference = args.pattern_or_reference
            package_id = args.package

            if package_id:
                self._out.warning("Usage of `--package` argument is deprecated."
                               " Use a full reference instead: "
                               "`conan upload [...] {}:{}`".format(reference, package_id))

            if args.query and package_id:
                raise ConanException("'--query' argument cannot be used together with '--package'")
        else:
            reference = repr(pref.ref)
            package_id = "{}#{}".format(pref.package_id, pref.revision) \
                if pref.revision else pref.package_id

            if args.package:
                raise ConanException("Use a full package reference (preferred) or the `--package`"
                                     " command argument, but not both.")
            if args.query:
                raise ConanException("'--query' argument cannot be used together with "
                                     "full reference")

        if args.force and args.skip_upload:
            raise ConanException("'--skip-upload' argument cannot be used together with '--force'")

        self._warn_python_version()

        if args.force:
            policy = UPLOAD_POLICY_FORCE
        elif args.skip_upload:
            policy = UPLOAD_POLICY_SKIP
        else:
            policy = None

        info = None
        try:
            info = self._conan_api.upload(pattern=reference, package=package_id,
                                      query=args.query, remote_name=args.remote,
                                      all_packages=args.all, policy=policy,
                                      confirm=args.confirm, retry=args.retry,
                                      retry_wait=args.retry_wait, integrity_check=args.check,
                                      parallel_upload=args.parallel)

        except ConanException as exc:
            info = exc.info
            raise
        finally:
            if args.json and info:
                CommandOutputer().json_output(info, args.json, os.getcwd())

    def profile(self, *args):
        """
        Lists profiles in the '.conan/profiles' folder, or shows profile details.

        The 'list' subcommand will always use the default user 'conan/profiles' folder. But the
        'show' subcommand can resolve absolute and relative paths, as well as to map names to
        '.conan/profiles' folder, in the same way as the '--profile' install argument.
        """
        parser = argparse.ArgumentParser(description=self.profile.__doc__,
                                         prog="conan profile",
                                         formatter_class=SmartFormatter)
        subparsers = parser.add_subparsers(dest='subcommand', help='sub-command help')
        subparsers.required = True

        # create the parser for the "profile" command
        parser_list = subparsers.add_parser('list', help='List current profiles')
        parser_list.add_argument("-j", "--json", default=None, action=OnceArgument,
                                 help='json file path where the profile list will be written to')
        parser_show = subparsers.add_parser('show', help='Show the values defined for a profile')
        parser_show.add_argument('profile', help="name of the profile in the '.conan/profiles' "
                                                 "folder or path to a profile file")

        parser_new = subparsers.add_parser('new', help='Creates a new empty profile')
        parser_new.add_argument('profile', help="Name for the profile in the '.conan/profiles' "
                                                "folder or path and name for a profile file")
        parser_new.add_argument("--detect", action='store_true', default=False,
                                help='Autodetect settings and fill [settings] section')
        parser_new.add_argument("--force", action='store_true', default=False,
                                help='Overwrite existing profile if existing')

        parser_update = subparsers.add_parser('update', help='Update a profile with desired value')
        parser_update.add_argument('item',
                                   help="'item=value' to update. e.g., settings.compiler=gcc")
        parser_update.add_argument('profile', help="Name of the profile in the '.conan/profiles' "
                                                   "folder or path to a profile file")

        parser_get = subparsers.add_parser('get', help='Get a profile key')
        parser_get.add_argument('item', help='Key of the value to get, e.g.: settings.compiler')
        parser_get.add_argument('profile', help="Name of the profile in the '.conan/profiles' "
                                                "folder or path to a profile file")

        parser_remove = subparsers.add_parser('remove', help='Remove a profile key')
        parser_remove.add_argument('item', help='key, e.g.: settings.compiler')
        parser_remove.add_argument('profile', help="Name of the profile in the '.conan/profiles' "
                                                   "folder or path to a profile file")

        args = parser.parse_args(*args)

        profile = args.profile if hasattr(args, 'profile') else None

        if args.subcommand == "list":
            profiles = self._conan_api.profile_list()
            CommandOutputer().profile_list(profiles)
            if args.json:
                CommandOutputer().json_output(profiles, args.json, os.getcwd())
        elif args.subcommand == "show":
            profile_text = self._conan_api.read_profile(profile)
            CommandOutputer().print_profile(profile, profile_text)
        elif args.subcommand == "new":
            self._conan_api.create_profile(profile, args.detect, args.force)
        elif args.subcommand == "update":
            try:
                key, value = args.item.split("=", 1)
            except ValueError:
                raise ConanException("Please specify key=value")
            self._conan_api.update_profile(profile, key, value)
        elif args.subcommand == "get":
            key = args.item
            self._out.info(self._conan_api.get_profile_key(profile, key))
        elif args.subcommand == "remove":
            self._conan_api.delete_profile_key(profile, args.item)

    def get(self, *args):
        """
        Gets a file or list a directory of a given reference or package.
        """
        parser = argparse.ArgumentParser(description=self.get.__doc__,
                                         prog="conan get",
                                         formatter_class=SmartFormatter)
        parser.add_argument('reference', help=_REF_OR_PREF_HELP)
        parser.add_argument('path',
                            help='Path to the file or directory. If not specified will get the '
                                 'conanfile if only a reference is specified and a conaninfo.txt '
                                 'file contents if the package is also specified',
                            default=None, nargs="?")
        parser.add_argument("-p", "--package", default=None,
                            help="Package ID [DEPRECATED: use full reference instead]",
                            action=OnceArgument)
        parser.add_argument("-r", "--remote", action=OnceArgument,
                            help='Get from this specific remote')
        parser.add_argument("-raw", "--raw", action='store_true', default=False,
                            help='Do not decorate the text')
        args = parser.parse_args(*args)

        try:
            pref = PkgReference.loads(args.reference)
        except ConanException:
            reference = args.reference
            package_id = args.package

            if package_id:
                self._out.warning("Usage of `--package` argument is deprecated."
                               " Use a full reference instead: "
                               "`conan get [...] {}:{}`".format(reference, package_id))
        else:
            reference = repr(pref.ref)
            package_id = pref.package_id
            if args.package:
                raise ConanException("Use a full package reference (preferred) or the `--package`"
                                     " command argument, but not both.")

        ret, path = self._conan_api.get_path(reference, package_id, args.path, args.remote)
        if isinstance(ret, list):
            CommandOutputer().print_dir_list(ret, path, args.raw)
        else:
            CommandOutputer().print_file_contents(ret, path, args.raw)

    def alias(self, *args):
        """
        Creates and exports an 'alias package recipe'.

        An "alias" package is a symbolic name (reference) for another package
        (target). When some package depends on an alias, the target one will be
        retrieved and used instead, so the alias reference, the symbolic name,
        does not appear in the final dependency graph.
        """
        parser = argparse.ArgumentParser(description=self.alias.__doc__,
                                         prog="conan alias",
                                         formatter_class=SmartFormatter)
        parser.add_argument('reference', help='Alias reference. e.g.: mylib/1.X@user/channel')
        parser.add_argument('target', help='Target reference. e.g.: mylib/1.12@user/channel')
        args = parser.parse_args(*args)

        self._warn_python_version()

        self._conan_api.export_alias(args.reference, args.target)

    def editable(self, *args):
        """
        Manages editable packages (packages that reside in the user workspace, but
        are consumed as if they were in the cache).

        Use the subcommands 'add', 'remove' and 'list' to create, remove or list
        packages currently installed in this mode.
        """
        parser = argparse.ArgumentParser(description=self.editable.__doc__,
                                         prog="conan editable",
                                         formatter_class=SmartFormatter)
        subparsers = parser.add_subparsers(dest='subcommand', help='sub-command help')
        subparsers.required = True

        add_parser = subparsers.add_parser('add', help='Put a package in editable mode')
        add_parser.add_argument('path', help='Path to the package folder in the user workspace')
        add_parser.add_argument('reference', help='Package reference e.g.: mylib/1.X@user/channel')

        remove_parser = subparsers.add_parser('remove', help='Disable editable mode for a package')
        remove_parser.add_argument('reference',
                                   help='Package reference e.g.: mylib/1.X@user/channel')

        subparsers.add_parser('list', help='List packages in editable mode')

        args = parser.parse_args(*args)
        self._warn_python_version()

        if args.subcommand == "add":
            self._conan_api.editable_add(args.path, args.reference, cwd=os.getcwd())
            self._out.success("Reference '{}' in editable mode".format(args.reference))
        elif args.subcommand == "remove":
            ret = self._conan_api.editable_remove(args.reference)
            if ret:
                self._out.success("Removed editable mode for reference '{}'".format(args.reference))
            else:
                self._out.warning("Reference '{}' was not installed "
                               "as editable".format(args.reference))
        elif args.subcommand == "list":
            for k, v in self._conan_api.editable_list().items():
                self._out.info("%s" % k)
                self._out.info("    Path: %s" % v["path"])

    def frogarian(self, *args):
        """
        Conan The Frogarian
        """
        cmd_frogarian(self._out)

    def lock(self, *args):
        """
        Generates and manipulates lock files.
        """
        parser = argparse.ArgumentParser(description=self.lock.__doc__,
                                         prog="conan lock",
                                         formatter_class=SmartFormatter)
        subparsers = parser.add_subparsers(dest='subcommand', help='sub-command help')
        subparsers.required = True

        merge_cmd = subparsers.add_parser('merge', help="merge 2 or more lockfiles")
        merge_cmd.add_argument('--lockfile', action="append", help='Path to lockfile to be merged')
        merge_cmd.add_argument("--lockfile-out", action=OnceArgument, default="conan.lock",
                               help="Filename of the created lockfile")

        create_cmd = subparsers.add_parser('create',
                                           help='Create a lockfile from a conanfile or a reference')
        create_cmd.add_argument("path", nargs="?", help="Path to a conanfile, including filename, "
                                                        "like 'path/conanfile.py'")
        create_cmd.add_argument("--name", action=OnceArgument,
                                help='Provide a package name if not specified in conanfile')
        create_cmd.add_argument("--version", action=OnceArgument,
                                help='Provide a package version if not specified in conanfile')
        create_cmd.add_argument("--user", action=OnceArgument,
                                help='Provide a user')
        create_cmd.add_argument("--channel", action=OnceArgument,
                                help='Provide a channel')
        create_cmd.add_argument("--reference", action=OnceArgument,
                                help='Provide a package reference instead of a conanfile')
        create_cmd.add_argument("-l", "--lockfile", action=OnceArgument,
                                help="Path to lockfile to be used as a base")
        create_cmd.add_argument("--lockfile-out", action=OnceArgument, default="conan.lock",
                                help="Filename of the created lockfile")
        create_cmd.add_argument("--clean", action="store_true", help="remove unused")
        _add_common_install_arguments(create_cmd, build_help="Packages to build from source",
                                      lockfile=False)

        args = parser.parse_args(*args)
        self._warn_python_version()

        if args.subcommand == "merge":
            self._conan_api.lock_merge(args.lockfile, args.lockfile_out)
        elif args.subcommand == "create":
            profile_build = ProfileData(profiles=args.profile_build, settings=args.settings_build,
                                        options=args.options_build, env=args.env_build,
                                        conf=args.conf_build)
            profile_host = ProfileData(profiles=args.profile_host, settings=args.settings_host,
                                       options=args.options_host, env=args.env_host,
                                       conf=args.conf_host)

            self._conan_api.lock_create(path=args.path,
                                    reference=args.reference,
                                    name=args.name,
                                    version=args.version,
                                    user=args.user,
                                    channel=args.channel,
                                    profile_host=profile_host,
                                    profile_build=profile_build,
                                    remote_name=args.remote,
                                    update=args.update,
                                    build=args.build,
                                    lockfile=args.lockfile,
                                    lockfile_out=args.lockfile_out,
                                    clean=args.clean)

    def _commands(self):
        """ Returns a list of available commands.
        """
        result = {}
        for m in inspect.getmembers(self, predicate=inspect.ismethod):
            method_name = m[0]
            if not method_name.startswith('_'):
                if "export_pkg" == method_name:
                    method_name = "export-pkg"
                method = m[1]
                if method.__doc__ and not method.__doc__.startswith('HIDDEN'):
                    result[method_name] = method
        return result

    def _print_similar(self, command):
        """ Looks for similar commands and prints them if found.
        """
        matches = get_close_matches(
            word=command, possibilities=self._commands().keys(), n=5, cutoff=0.75)

        if len(matches) == 0:
            return

        if len(matches) > 1:
            self._out.info("The most similar commands are")
        else:
            self._out.info("The most similar command is")

        for match in matches:
            self._out.info("    %s" % match)

        self._out.info("")

    def _warn_python_version(self):
        version = sys.version_info
        if version.major == 2 or  version.minor < 6:
            raise ConanException("Conan needs Python >= 3.6")

    def run(self, *args):
        """HIDDEN: entry point for executing commands, dispatcher to class
        methods
        """
        ret_code = SUCCESS
        try:
            command = args[0][0]
            commands = self._commands()
            method = commands[command]

            if (command != "config" or
               (command == "config" and len(args[0]) > 1 and args[0][1] != "install")) and \
               is_config_install_scheduled(self._conan_api):
                self._conan_api.config_install(None, None)

            method(args[0][1:])
        except KeyboardInterrupt as exc:
            logger.error(exc)
            ret_code = SUCCESS
        except SystemExit as exc:
            if exc.code != 0:
                logger.error(exc)
                self._out.error("Exiting with code: %d" % exc.code)
            ret_code = exc.code
        except ConanInvalidConfiguration as exc:
            ret_code = ERROR_INVALID_CONFIGURATION
            self._out.error(exc)
        except ConanInvalidSystemRequirements as exc:
            ret_code = ERROR_INVALID_SYSTEM_REQUIREMENTS
            self._out.error(exc)
        except ConanException as exc:
            ret_code = ERROR_GENERAL
            self._out.error(exc)
        except Exception as exc:
            import traceback
            print(traceback.format_exc())
            ret_code = ERROR_GENERAL
            msg = exception_message_safe(exc)
            self._out.error(msg)

        return ret_code


def _add_common_install_arguments(parser, build_help, update_help=None, lockfile=True):
    if build_help:
        parser.add_argument("-b", "--build", action=Extender, nargs="?", help=build_help)

    parser.add_argument("-r", "--remote", action=OnceArgument,
                        help='Look in the specified remote server')

    if not update_help:
        update_help = ("Will check the remote and in case a newer version and/or revision of "
                       "the dependencies exists there, it will install those in the local cache. "
                       "When using version ranges, it will install the latest version that "
                       "satisfies the range. Also, if using revisions, it will update to the "
                       "latest revision for the resolved version range.")

    parser.add_argument("-u", "--update", action='store_true', default=False,
                        help=update_help)
    if lockfile:
        parser.add_argument("-l", "--lockfile", action=OnceArgument,
                            help="Path to a lockfile")
        parser.add_argument("--lockfile-out", action=OnceArgument,
                            help="Filename of the updated lockfile")
    _add_profile_arguments(parser)


def _add_profile_arguments(parser):
    # Arguments that can apply to the build or host machines (easily extend to target machine)
    def environment_args(machine, short_suffix="", long_suffix=""):
        parser.add_argument("-e{}".format(short_suffix),
                            "--env{}".format(long_suffix),
                            nargs=1, action=Extender,
                            dest="env_{}".format(machine),
                            help='Environment variables that will be set during the'
                                 ' package build ({} machine).'
                                 ' e.g.: -e{} CXX=/usr/bin/clang++'.format(machine, short_suffix))

    def options_args(machine, short_suffix="", long_suffix=""):
        parser.add_argument("-o{}".format(short_suffix),
                            "--options{}".format(long_suffix),
                            nargs=1, action=Extender,
                            dest="options_{}".format(machine),
                            help='Define options values ({} machine), e.g.:'
                                 ' -o{} Pkg:with_qt=true'.format(machine, short_suffix))

    def profile_args(machine, short_suffix="", long_suffix=""):
        parser.add_argument("-pr{}".format(short_suffix),
                            "--profile{}".format(long_suffix),
                            default=None, action=Extender,
                            dest='profile_{}'.format(machine),
                            help='Apply the specified profile to the {} machine'.format(machine))

    def settings_args(machine, short_suffix="", long_suffix=""):
        parser.add_argument("-s{}".format(short_suffix),
                            "--settings{}".format(long_suffix),
                            nargs=1, action=Extender,
                            dest='settings_{}'.format(machine),
                            help='Settings to build the package, overwriting the defaults'
                                 ' ({} machine). e.g.: -s{} compiler=gcc'.format(machine,
                                                                                 short_suffix))

    def conf_args(machine, short_suffix="", long_suffix=""):
        parser.add_argument("-c{}".format(short_suffix),
                            "--conf{}".format(long_suffix),
                            nargs=1, action=Extender,
                            dest='conf_{}'.format(machine),
                            help='Configuration to build the package, overwriting the defaults'
                                 ' ({} machine). e.g.: -c{} '
                                 'tools.cmake.cmaketoolchain:generator=Xcode'.format(machine,
                                                                                     short_suffix))

    for item_fn in [environment_args, options_args, profile_args, settings_args, conf_args]:
        item_fn("host", "", "")  # By default it is the HOST, the one we are building binaries for
        item_fn("build", ":b", ":build")
        item_fn("host", ":h", ":host")


_help_build_policies = '''Optional, specify which packages to build from source. Combining multiple
    '--build' options on one command line is allowed. For dependencies, the optional 'build_policy'
    attribute in their conanfile.py takes precedence over the command line parameter.
    Possible parameters:

    --build            Force build for all packages, do not use binary packages.
    --build=never      Disallow build for all packages, use binary packages or fail if a binary
                       package is not found. Cannot be combined with other '--build' options.
    --build=missing    Build packages from source whose binary package is not found.
    --build=cascade    Build packages from source that have at least one dependency being built from
                       source.
    --build=[pattern]  Build packages from source whose package reference matches the pattern. The
                       pattern uses 'fnmatch' style wildcards.
    --build=![pattern] Excluded packages, which will not be built from the source, whose package
                       reference matches the pattern. The pattern uses 'fnmatch' style wildcards.

    Default behavior: If you omit the '--build' option, the 'build_policy' attribute in conanfile.py
    will be used if it exists, otherwise the behavior is like '--build={}'.
'''
