import argparse
import inspect
import json
import os
import sys
from argparse import ArgumentError
from difflib import get_close_matches

from six.moves import input as raw_input

from conans import __version__ as client_version
from conans.client.cmd.uploader import UPLOAD_POLICY_FORCE, \
    UPLOAD_POLICY_NO_OVERWRITE, UPLOAD_POLICY_NO_OVERWRITE_RECIPE, UPLOAD_POLICY_SKIP
from conans.client.conan_api import (Conan, default_manifest_folder, _make_abs_path)
from conans.client.conan_command_output import CommandOutputer
from conans.client.output import Color
from conans.client.printer import Printer
from conans.errors import ConanException, ConanInvalidConfiguration, NoRemoteAvailable, \
    ConanMigrationError
from conans.model.ref import ConanFileReference, PackageReference, get_reference_fields, \
    check_valid_ref
from conans.unicode import get_cwd
from conans.util.config_parser import get_bool_from_text
from conans.util.files import exception_message_safe
from conans.util.files import save
from conans.util.log import logger

# Exit codes for conan command:
SUCCESS = 0                         # 0: Success (done)
ERROR_GENERAL = 1                   # 1: General ConanException error (done)
ERROR_MIGRATION = 2                 # 2: Migration error
USER_CTRL_C = 3                     # 3: Ctrl+C
USER_CTRL_BREAK = 4                 # 4: Ctrl+Break
ERROR_SIGTERM = 5                   # 5: SIGTERM
ERROR_INVALID_CONFIGURATION = 6     # 6: Invalid configuration (done)


class Extender(argparse.Action):
    """Allows using the same flag several times in command and creates a list with the values.
    For example:
        conan install MyPackage/1.2@user/channel -o qt:value -o mode:2 -s cucumber:true
      It creates:
          options = ['qt:value', 'mode:2']
          settings = ['cucumber:true']
    """
    def __call__(self, parser, namespace, values, option_strings=None):  # @UnusedVariable
        # Need None here incase `argparse.SUPPRESS` was supplied for `dest`
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
_INSTALL_FOLDER_HELP = ("Directory containing the conaninfo.txt and conanbuildinfo.txt files "
                        "(from previous 'conan install'). Defaulted to --build-folder")
_KEEP_SOURCE_HELP = ("Do not remove the source folder in the local cache, even if the recipe changed. "
                     "Use this for testing purposes only")
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
    parsing of parameters and delegates functionality in collaborators. It can also show the help of the
    tool.
    """
    def __init__(self, conan_api):
        assert isinstance(conan_api, Conan)
        self._conan = conan_api
        self._out = conan_api.out

    @property
    def _outputer(self):
        # FIXME, this access to the cache for output is ugly, should be removed
        return CommandOutputer(self._out, self._conan.app.cache)

    def help(self, *args):
        """
        Shows help for a specific command.
        """
        parser = argparse.ArgumentParser(description=self.help.__doc__,
                                         prog="conan help",
                                         formatter_class=SmartFormatter)
        parser.add_argument("command", help='command', nargs="?")
        args = parser.parse_args(*args)
        if not args.command:
            self._show_help()
            return
        try:
            commands = self._commands()
            method = commands[args.command]
            self._warn_python_version()
            method(["--help"])
        except KeyError:
            raise ConanException("Unknown command '%s'" % args.command)

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
                            help='Use the given template from the local cache for conanfile.py')
        parser.add_argument("-cis", "--ci-shared", action='store_true',
                            default=False,
                            help='Package will have a "shared" option to be used in CI')
        parser.add_argument("-cilg", "--ci-travis-gcc", action='store_true',
                            default=False,
                            help='Generate travis-ci files for linux gcc')
        parser.add_argument("-cilc", "--ci-travis-clang", action='store_true',
                            default=False,
                            help='Generate travis-ci files for linux clang')
        parser.add_argument("-cio", "--ci-travis-osx", action='store_true',
                            default=False,
                            help='Generate travis-ci files for OSX apple-clang')
        parser.add_argument("-ciw", "--ci-appveyor-win", action='store_true',
                            default=False, help='Generate appveyor files for Appveyor '
                                                'Visual Studio')
        parser.add_argument("-ciglg", "--ci-gitlab-gcc", action='store_true',
                            default=False,
                            help='Generate GitLab files for linux gcc')
        parser.add_argument("-ciglc", "--ci-gitlab-clang", action='store_true',
                            default=False,
                            help='Generate GitLab files for linux clang')
        parser.add_argument("-ciccg", "--ci-circleci-gcc", action='store_true',
                            default=False,
                            help='Generate CircleCI files for linux gcc')
        parser.add_argument("-ciccc", "--ci-circleci-clang", action='store_true',
                            default=False,
                            help='Generate CircleCI files for linux clang')
        parser.add_argument("-cicco", "--ci-circleci-osx", action='store_true',
                            default=False,
                            help='Generate CircleCI files for OSX apple-clang')
        parser.add_argument("-gi", "--gitignore", action='store_true', default=False,
                            help='Generate a .gitignore with the known patterns to excluded')
        parser.add_argument("-ciu", "--ci-upload-url",
                            help='Define URL of the repository to upload')

        args = parser.parse_args(*args)
        self._warn_python_version()
        self._conan.new(args.name, header=args.header, pure_c=args.pure_c, test=args.test,
                        exports_sources=args.sources, bare=args.bare,
                        visual_versions=args.ci_appveyor_win,
                        linux_gcc_versions=args.ci_travis_gcc,
                        linux_clang_versions=args.ci_travis_clang,
                        gitignore=args.gitignore,
                        osx_clang_versions=args.ci_travis_osx, shared=args.ci_shared,
                        upload_url=args.ci_upload_url,
                        gitlab_gcc_versions=args.ci_gitlab_gcc,
                        gitlab_clang_versions=args.ci_gitlab_clang,
                        circleci_gcc_versions=args.ci_circleci_gcc,
                        circleci_clang_versions=args.ci_circleci_clang,
                        circleci_osx_versions=args.ci_circleci_osx,
                        template=args.template)

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

        result = self._conan.inspect(args.path_or_reference, attributes, args.remote, quiet=quiet)
        Printer(self._out).print_inspect(result, raw=args.raw)
        if args.json:
            json_output = json.dumps(result)
            if not os.path.isabs(args.json):
                json_output_file = os.path.join(get_cwd(), args.json)
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
                            'e.g. conan test_package/conanfile.py pkg/version@user/channel')
        parser.add_argument("reference",
                            help='pkg/version@user/channel of the package to be tested')
        parser.add_argument("-tbf", "--test-build-folder", action=OnceArgument,
                            help="Working directory of the build process.")

        _add_common_install_arguments(parser, build_help=_help_build_policies.format("never"))
        args = parser.parse_args(*args)
        self._warn_python_version()
        return self._conan.test(args.path, args.reference, args.profile, args.settings,
                                args.options, args.env, args.remote, args.update,
                                build_modes=args.build, test_build_folder=args.test_build_folder,
                                lockfile=args.lockfile)

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
        parser.add_argument('-k', '-ks', '--keep-source', default=False, action='store_true',
                            help=_KEEP_SOURCE_HELP)
        parser.add_argument('-kb', '--keep-build', default=False, action='store_true',
                            help='Do not remove the build folder in local cache. '
                                 'Implies --keep-source. '
                                 'Use this for testing purposes only')
        parser.add_argument("-ne", "--not-export", default=False, action='store_true',
                            help='Do not export the conanfile.py')
        parser.add_argument("-tbf", "--test-build-folder", action=OnceArgument,
                            help='Working directory for the build of the test project.')
        parser.add_argument("-tf", "--test-folder", action=OnceArgument,
                            help='Alternative test folder name. By default it is "test_package". '
                                 'Use "None" to skip the test stage')
        parser.add_argument("--ignore-dirty", default=False, action='store_true',
                            help='When using the "scm" feature with "auto" values, capture the'
                                 ' revision and url even if there are uncommitted changes')

        _add_manifests_arguments(parser)
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

        cwd = get_cwd()

        info = None
        try:
            info = self._conan.create(args.path, name, version, user, channel,
                                      args.profile, args.settings, args.options,
                                      args.env, args.test_folder, args.not_export,
                                      args.build, args.keep_source, args.keep_build, args.verify,
                                      args.manifests, args.manifests_interactive,
                                      args.remote, args.update,
                                      test_build_folder=args.test_build_folder,
                                      lockfile=args.lockfile, ignore_dirty=args.ignore_dirty)
        except ConanException as exc:
            info = exc.info
            raise
        finally:
            if args.json and info:
                self._outputer.json_output(info, args.json, cwd)

    def download(self, *args):
        """
        Downloads recipe and binaries to the local cache, without using settings.

        It works specifying the recipe reference and package ID to be
        installed. Not transitive, requirements of the specified reference will
        NOT be retrieved. Useful together with 'conan copy' to automate the
        promotion of packages to a different user/channel. Only if a reference
        is specified, it will download all packages from the specified remote.
        If no remote is specified, it will use the default remote.
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
            pref = PackageReference.loads(args.reference, validate=True)
        except ConanException:
            reference = args.reference
            packages_list = args.package

            if packages_list:
                self._out.warn("Usage of `--package` argument is deprecated."
                               " Use a full reference instead: "
                               "`conan download [...] {}:{}`".format(reference, packages_list[0]))
        else:
            reference = repr(pref.ref)
            if pref.ref.user is None:
                if pref.ref.revision:
                    reference = "%s/%s@#%s" % (pref.ref.name, pref.ref.version, pref.ref.revision)
                else:
                    reference += "@"
            pkgref = "{}#{}".format(pref.id, pref.revision) if pref.revision else pref.id
            packages_list = [pkgref]
            if args.package:
                raise ConanException("Use a full package reference (preferred) or the `--package`"
                                     " command argument, but not both.")

        self._warn_python_version()
        return self._conan.download(reference=reference, packages=packages_list,
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
                                 'files. e.g., conaninfo/conanbuildinfo.txt')
        _add_manifests_arguments(parser)

        parser.add_argument("--no-imports", action='store_true', default=False,
                            help='Install specified packages but avoid running imports')
        parser.add_argument("-j", "--json", default=None, action=OnceArgument,
                            help='Path to a json file where the install information will be '
                            'written')

        _add_common_install_arguments(parser, build_help=_help_build_policies.format("never"))

        args = parser.parse_args(*args)
        cwd = get_cwd()

        # We need @ otherwise it could be a path, so check strict
        path_is_reference = check_valid_ref(args.path_or_reference)

        info = None
        try:
            if not path_is_reference:
                name, version, user, channel, _ = get_reference_fields(args.reference,
                                                                       user_channel_input=True)
                info = self._conan.install(path=args.path_or_reference,
                                           name=name, version=version, user=user, channel=channel,
                                           settings=args.settings, options=args.options,
                                           env=args.env,
                                           remote_name=args.remote,
                                           verify=args.verify, manifests=args.manifests,
                                           manifests_interactive=args.manifests_interactive,
                                           build=args.build, profile_names=args.profile,
                                           update=args.update, generators=args.generator,
                                           no_imports=args.no_imports,
                                           install_folder=args.install_folder,
                                           lockfile=args.lockfile)
            else:
                if args.reference:
                    raise ConanException("A full reference was provided as first argument, second "
                                         "argument not allowed")

                ref = ConanFileReference.loads(args.path_or_reference, validate=False)
                manifest_interactive = args.manifests_interactive
                info = self._conan.install_reference(ref, settings=args.settings,
                                                     options=args.options,
                                                     env=args.env,
                                                     remote_name=args.remote,
                                                     verify=args.verify, manifests=args.manifests,
                                                     manifests_interactive=manifest_interactive,
                                                     build=args.build, profile_names=args.profile,
                                                     update=args.update,
                                                     generators=args.generator,
                                                     install_folder=args.install_folder,
                                                     lockfile=args.lockfile)

        except ConanException as exc:
            info = exc.info
            raise
        finally:
            if args.json and info:
                self._outputer.json_output(info, args.json, cwd)

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

        get_subparser = subparsers.add_parser('get', help='Get the value of configuration item')
        home_subparser = subparsers.add_parser('home', help='Retrieve the Conan home directory')
        install_subparser = subparsers.add_parser('install', help='Install a full configuration '
                                                                  'from a local or remote zip file')
        rm_subparser = subparsers.add_parser('rm', help='Remove an existing config element')
        set_subparser = subparsers.add_parser('set', help='Set a value for a configuration item')

        get_subparser.add_argument("item", nargs="?", help="Item to print")
        home_subparser.add_argument("-j", "--json", default=None, action=OnceArgument,
                                    help='json file path where the config home will be written to')
        install_subparser.add_argument("item", nargs="?",
                                       help="git repository, local folder or zip file (local or "
                                       "http) where the configuration is stored")

        install_subparser.add_argument("--verify-ssl", nargs="?", default="True",
                                       help='Verify SSL connection when downloading file')
        install_subparser.add_argument("--type", "-t", choices=["git"],
                                       help='Type of remote config')
        install_subparser.add_argument("--args", "-a",
                                       help='String with extra arguments for "git clone"')
        install_subparser.add_argument("-sf", "--source-folder",
                                       help='Install files only from a source subfolder from the '
                                       'specified origin')
        install_subparser.add_argument("-tf", "--target-folder",
                                       help='Install to that path in the conan cache')
        rm_subparser.add_argument("item", help="Item to remove")
        set_subparser.add_argument("item", help="'item=value' to set")

        args = parser.parse_args(*args)

        if args.subcommand == "set":
            try:
                key, value = args.item.split("=", 1)
            except ValueError:
                if "hooks." in args.item:
                    key, value = args.item.split("=", 1)[0], None
                else:
                    raise ConanException("Please specify 'key=value'")
            return self._conan.config_set(key, value)
        elif args.subcommand == "get":
            return self._conan.config_get(args.item)
        elif args.subcommand == "rm":
            return self._conan.config_rm(args.item)
        elif args.subcommand == "home":
            conan_home = self._conan.config_home()
            self._out.info(conan_home)
            if args.json:
                self._outputer.json_output({"home": conan_home}, args.json, os.getcwd())
            return conan_home
        elif args.subcommand == "install":
            verify_ssl = get_bool_from_text(args.verify_ssl)
            return self._conan.config_install(args.item, verify_ssl, args.type, args.args,
                                              source_folder=args.source_folder,
                                              target_folder=args.target_folder)

    def info(self, *args):
        """
        Gets information about the dependency graph of a recipe.

        It can be used with a recipe or a reference for any existing package in
        your local cache.
        """

        info_only_options = ["id", "build_id", "remote", "url", "license", "requires", "update",
                             "required", "date", "author", "None"]
        path_only_options = ["export_folder", "build_folder", "package_folder", "source_folder"]
        str_path_only_options = ", ".join(['"%s"' % field for field in path_only_options])
        str_only_options = ", ".join(['"%s"' % field for field in info_only_options])

        parser = argparse.ArgumentParser(description=self.info.__doc__,
                                         prog="conan info",
                                         formatter_class=SmartFormatter)
        parser.add_argument("path_or_reference", help="Path to a folder containing a recipe"
                            " (conanfile.py or conanfile.txt) or to a recipe file. e.g., "
                            "./my_project/conanfile.txt. It could also be a reference")
        parser.add_argument("--paths", action='store_true', default=False,
                            help='Show package paths in local cache')
        parser.add_argument("-bo", "--build-order",
                            help="given a modified reference, return an ordered list to build (CI)."
                                 " [DEPRECATED: use 'conan graph build-order ...' instead]",
                            nargs=1, action=Extender)
        parser.add_argument("-g", "--graph", action=OnceArgument,
                            help='Creates file with project dependencies graph. It will generate '
                            'a DOT or HTML file depending on the filename extension')
        parser.add_argument("-if", "--install-folder", action=OnceArgument,
                            help="local folder containing the conaninfo.txt and conanbuildinfo.txt "
                            "files (from a previous conan install execution). Defaulted to "
                            "current folder, unless --profile, -s or -o is specified. If you "
                            "specify both install-folder and any setting/option "
                            "it will raise an error.")
        parser.add_argument("-j", "--json", nargs='?', const="1", type=str,
                            help='Path to a json file where the information will be written')
        parser.add_argument("-n", "--only", nargs=1, action=Extender,
                            help="Show only the specified fields: %s. '--paths' information can "
                            "also be filtered with options %s. Use '--only None' to show only "
                            "references." % (str_only_options, str_path_only_options))
        parser.add_argument("--package-filter", nargs='?',
                            help='Print information only for packages that match the filter pattern'
                                 ' e.g., MyPackage/1.2@user/channel or MyPackage*')
        dry_build_help = ("Apply the --build argument to output the information, "
                          "as it would be done by the install command")
        parser.add_argument("-db", "--dry-build", action=Extender, nargs="?", help=dry_build_help)
        build_help = ("Given a build policy, return an ordered list of packages that would be built"
                      " from sources during the install command")

        _add_common_install_arguments(parser, build_help=build_help)
        args = parser.parse_args(*args)

        if args.build_order:
            self._out.warn("Usage of `--build-order` argument is deprecated and can return"
                           " wrong results. Use `conan graph build-order ...` instead.")

        if args.install_folder and (args.profile or args.settings or args.options or args.env):
            raise ArgumentError(None,
                                "--install-folder cannot be used together with -s, -o, -e or -pr")
        if args.build_order and args.graph:
            raise ArgumentError(None,
                                "--build-order cannot be used together with --graph")

        # BUILD ORDER ONLY
        if args.build_order:
            ret = self._conan.info_build_order(args.path_or_reference,
                                               settings=args.settings,
                                               options=args.options,
                                               env=args.env,
                                               profile_names=args.profile,
                                               remote_name=args.remote,
                                               build_order=args.build_order,
                                               check_updates=args.update,
                                               install_folder=args.install_folder)
            if args.json:
                json_arg = True if args.json == "1" else args.json
                self._outputer.json_build_order(ret, json_arg, get_cwd())
            else:
                self._outputer.build_order(ret)

        # INSTALL SIMULATION, NODES TO INSTALL
        elif args.build is not None:
            nodes, _ = self._conan.info_nodes_to_build(args.path_or_reference,
                                                       build_modes=args.build,
                                                       settings=args.settings,
                                                       options=args.options,
                                                       env=args.env,
                                                       profile_names=args.profile,
                                                       remote_name=args.remote,
                                                       check_updates=args.update,
                                                       install_folder=args.install_folder)
            if args.json:
                json_arg = True if args.json == "1" else args.json
                self._outputer.json_nodes_to_build(nodes, json_arg, get_cwd())
            else:
                self._outputer.nodes_to_build(nodes)

        # INFO ABOUT DEPS OF CURRENT PROJECT OR REFERENCE
        else:
            data = self._conan.info(args.path_or_reference,
                                    remote_name=args.remote,
                                    settings=args.settings,
                                    options=args.options,
                                    env=args.env,
                                    profile_names=args.profile,
                                    update=args.update,
                                    install_folder=args.install_folder,
                                    build=args.dry_build,
                                    lockfile=args.lockfile)
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
                self._outputer.info_graph(args.graph, deps_graph, get_cwd())
            if args.json:
                json_arg = True if args.json == "1" else args.json
                self._outputer.json_info(deps_graph, json_arg, get_cwd(), show_paths=args.paths)

            if not args.graph and not args.json:
                self._outputer.info(deps_graph, only, args.package_filter, args.paths)

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
        parser.add_argument("-if", "--install-folder", action=OnceArgument,
                            help=_INSTALL_FOLDER_HELP + " Optional, source method will run without "
                            "the information retrieved from the conaninfo.txt and "
                            "conanbuildinfo.txt, only required when using conditional source() "
                            "based on settings, options, env_info and user_info")
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
        return self._conan.source(args.path, args.source_folder, args.install_folder)

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
        parser.add_argument("-b", "--build", default=None, action="store_true",
                            help="Execute the build step (variable should_build=True). When "
                            "specified, configure/install/test won't run unless "
                            "--configure/--install/--test specified")
        parser.add_argument("-bf", "--build-folder", action=OnceArgument, help=_BUILD_FOLDER_HELP)
        parser.add_argument("-c", "--configure", default=None, action="store_true",
                            help="Execute the configuration step (variable should_configure=True). "
                            "When specified, build/install/test won't run unless "
                            "--build/--install/--test specified")
        parser.add_argument("-i", "--install", default=None, action="store_true",
                            help="Execute the install step (variable should_install=True). When "
                            "specified, configure/build/test won't run unless "
                            "--configure/--build/--test specified")
        parser.add_argument("-t", "--test", default=None, action="store_true",
                            help="Execute the test step (variable should_test=True). When "
                            "specified, configure/build/install won't run unless "
                            "--configure/--build/--install specified")
        parser.add_argument("-if", "--install-folder", action=OnceArgument,
                            help=_INSTALL_FOLDER_HELP)
        parser.add_argument("-pf", "--package-folder", action=OnceArgument,
                            help="Directory to install the package (when the build system or "
                            "build() method does it). Defaulted to the '{build_folder}/package' "
                            "folder. A relative path can be specified, relative to the current "
                            "folder. Also an absolute path is allowed.")
        parser.add_argument("-sf", "--source-folder", action=OnceArgument, help=_SOURCE_FOLDER_HELP)
        args = parser.parse_args(*args)

        self._warn_python_version()

        if args.build or args.configure or args.install or args.test:
            build, config, install, test = (bool(args.build), bool(args.configure),
                                            bool(args.install), bool(args.test))
        else:
            build = config = install = test = True
        return self._conan.build(conanfile_path=args.path,
                                 source_folder=args.source_folder,
                                 package_folder=args.package_folder,
                                 build_folder=args.build_folder,
                                 install_folder=args.install_folder,
                                 should_configure=config,
                                 should_build=build,
                                 should_install=install,
                                 should_test=test)

    def package(self, *args):
        """
        Calls your local conanfile.py 'package()' method.

        This command works in the user space and it will copy artifacts from
        the --build-folder and --source-folder folder to the --package-folder
        one.  It won't create a new package in the local cache, if you want to
        do it, use 'conan create' or 'conan export-pkg' after a 'conan build'
        command.
        """
        parser = argparse.ArgumentParser(description=self.package.__doc__,
                                         prog="conan package",
                                         formatter_class=SmartFormatter)
        parser.add_argument("path", help=_PATH_HELP)
        parser.add_argument("-bf", "--build-folder", action=OnceArgument, help=_BUILD_FOLDER_HELP)
        parser.add_argument("-if", "--install-folder", action=OnceArgument,
                            help=_INSTALL_FOLDER_HELP)
        parser.add_argument("-pf", "--package-folder", action=OnceArgument,
                            help="folder to install the package. Defaulted to the "
                                 "'{build_folder}/package' folder. A relative path can be specified"
                                 " (relative to the current directory). Also an absolute path"
                                 " is allowed.")
        parser.add_argument("-sf", "--source-folder", action=OnceArgument, help=_SOURCE_FOLDER_HELP)
        args = parser.parse_args(*args)
        try:
            if "@" in args.path and ConanFileReference.loads(args.path):
                raise ArgumentError(None,
                                    "'conan package' doesn't accept a reference anymore. "
                                    "The path parameter should be a conanfile.py or a folder "
                                    "containing one. If you were using the 'conan package' "
                                    "command for development purposes we recommend to use "
                                    "the local development commands: 'conan build' + "
                                    "'conan package' and finally 'conan create' to regenerate the "
                                    "package, or 'conan export_package' to store the already built "
                                    "binaries in the local cache without rebuilding them.")
        except ConanException:
            pass

        self._warn_python_version()
        return self._conan.package(path=args.path,
                                   build_folder=args.build_folder,
                                   package_folder=args.package_folder,
                                   source_folder=args.source_folder,
                                   install_folder=args.install_folder)

    def imports(self, *args):
        """
        Calls your local conanfile.py or conanfile.txt 'imports' method.

        It requires to have been previously installed and have a
        conanbuildinfo.txt generated file in the --install-folder (defaulted to
        the current directory).
        """
        parser = argparse.ArgumentParser(description=self.imports.__doc__,
                                         prog="conan imports",
                                         formatter_class=SmartFormatter)
        parser.add_argument("path",
                            help=_PATH_HELP + " With --undo option, this parameter is the folder "
                            "containing the conan_imports_manifest.txt file generated in a previous"
                            " execution. e.g.: conan imports ./imported_files --undo ")
        parser.add_argument("-if", "--install-folder", action=OnceArgument,
                            help=_INSTALL_FOLDER_HELP)
        parser.add_argument("-imf", "--import-folder", action=OnceArgument,
                            help="Directory to copy the artifacts to. By default it will be the"
                                 " current directory")
        parser.add_argument("-u", "--undo", default=False, action="store_true",
                            help="Undo imports. Remove imported files")
        args = parser.parse_args(*args)

        if args.undo:
            return self._conan.imports_undo(args.path)

        try:
            if "@" in args.path and ConanFileReference.loads(args.path):
                raise ArgumentError(None, "Parameter 'path' cannot be a reference. Use a folder "
                                          "containing a conanfile.py or conanfile.txt file.")
        except ConanException:
            pass
        self._warn_python_version()
        return self._conan.imports(args.path, args.import_folder, args.install_folder)

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
        parser.add_argument("-e", "--env", nargs=1, action=Extender,
                            help='Environment variables that will be set during the package build, '
                                 '-e CXX=/usr/bin/clang++')
        parser.add_argument('-f', '--force', default=False, action='store_true',
                            help='Overwrite existing package if existing')
        parser.add_argument("-if", "--install-folder", action=OnceArgument,
                            help=_INSTALL_FOLDER_HELP + " If these files are found in the specified"
                            " folder and any of '-e', '-o', '-pr' or '-s' arguments are used, it "
                            "will raise an error.")
        parser.add_argument("-o", "--options", nargs=1, action=Extender,
                            help='Define options values, e.g., -o pkg:with_qt=True')
        parser.add_argument("-pr", "--profile", action=Extender,
                            help='Profile for this package')
        parser.add_argument("-pf", "--package-folder", action=OnceArgument,
                            help="folder containing a locally created package. If a value is given,"
                                 " it won't call the recipe 'package()' method, and will run a copy"
                                 " of the provided folder.")
        parser.add_argument("-s", "--settings", nargs=1, action=Extender,
                            help='Define settings values, e.g., -s compiler=gcc')
        parser.add_argument("-sf", "--source-folder", action=OnceArgument, help=_SOURCE_FOLDER_HELP)
        parser.add_argument("-j", "--json", default=None, action=OnceArgument,
                            help='Path to a json file where the install information will be '
                            'written')
        parser.add_argument("-l", "--lockfile", action=OnceArgument, nargs='?', const=".",
                            help="Path to a lockfile or folder containing 'conan.lock' file. "
                            "Lockfile will be updated with the exported package")
        parser.add_argument("--ignore-dirty", default=False, action='store_true',
                            help='When using the "scm" feature with "auto" values, capture the'
                                 ' revision and url even if there are uncommitted changes')

        args = parser.parse_args(*args)

        self._warn_python_version()
        name, version, user, channel, _ = get_reference_fields(args.reference,
                                                               user_channel_input=True)
        cwd = os.getcwd()
        info = None

        try:
            info = self._conan.export_pkg(conanfile_path=args.path,
                                          name=name,
                                          version=version,
                                          source_folder=args.source_folder,
                                          build_folder=args.build_folder,
                                          package_folder=args.package_folder,
                                          install_folder=args.install_folder,
                                          profile_names=args.profile,
                                          env=args.env,
                                          settings=args.settings,
                                          options=args.options,
                                          force=args.force,
                                          user=user,
                                          channel=channel,
                                          lockfile=args.lockfile,
                                          ignore_dirty=args.ignore_dirty)
        except ConanException as exc:
            info = exc.info
            raise
        finally:
            if args.json and info:
                self._outputer.json_output(info, args.json, cwd)

    def export(self, *args):
        """
        Copies the recipe (conanfile.py & associated files) to your local cache.

        Use the 'reference' param to specify a user and channel where to export
        it. Once the recipe is in the local cache it can be shared, reused and
        to any remote with the 'conan upload' command.
        """
        parser = argparse.ArgumentParser(description=self.export.__doc__,
                                         prog="conan export",
                                         formatter_class=SmartFormatter)
        parser.add_argument("path", help=_PATH_HELP)
        parser.add_argument("reference", nargs='?', default=None,
                            help="user/channel, or Pkg/version@user/channel (if name "
                                 "and version are not declared in the conanfile.py")
        parser.add_argument('-k', '-ks', '--keep-source', default=False, action='store_true',
                            help=_KEEP_SOURCE_HELP)
        parser.add_argument("-l", "--lockfile", action=OnceArgument, nargs='?', const=".",
                            help="Path to a lockfile or folder containing 'conan.lock' file. "
                            "Lockfile will be updated with the exported package")
        parser.add_argument("--ignore-dirty", default=False, action='store_true',
                            help='When using the "scm" feature with "auto" values, capture the'
                                 ' revision and url even if there are uncommitted changes')

        args = parser.parse_args(*args)
        self._warn_python_version()
        name, version, user, channel, _ = get_reference_fields(args.reference,
                                                               user_channel_input=True)

        if any([user, channel]) and not all([user, channel]):
            # Or user/channel or nothing, but not partial
            raise ConanException("Invalid parameter '%s', "
                                 "specify the full reference or user/channel" % args.reference)

        return self._conan.export(path=args.path,
                                  name=name, version=version, user=user, channel=channel,
                                  keep_source=args.keep_source, lockfile=args.lockfile,
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
        parser.add_argument("-o", "--outdated", default=False, action="store_true",
                            help="Remove only outdated from recipe packages. "
                                 "This flag can only be used with a reference")
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

        if args.outdated and not args.pattern_or_reference:
            raise ConanException("'--outdated' argument can only be used with a reference")

        if args.locks:
            if args.pattern_or_reference:
                raise ConanException("Specifying a pattern is not supported when removing locks")
            self._conan.remove_locks()
            self._out.info("Cache locks removed")
            return
        elif args.system_reqs:
            if args.packages:
                raise ConanException("'-t' and '-p' parameters can't be used at the same time")
            if not args.pattern_or_reference:
                raise ConanException("Please specify a valid pattern or reference to be cleaned")

            if check_valid_ref(args.pattern_or_reference):
                return self._conan.remove_system_reqs(args.pattern_or_reference)

            return self._conan.remove_system_reqs_by_pattern(args.pattern_or_reference)
        else:
            if not args.pattern_or_reference:
                raise ConanException('Please specify a pattern to be removed ("*" for all)')

        return self._conan.remove(pattern=args.pattern_or_reference, query=args.query,
                                  packages=args.packages, builds=args.builds, src=args.src,
                                  force=args.force, remote_name=args.remote, outdated=args.outdated)

    def copy(self, *args):
        """
        Copies conan recipes and packages to another user/channel.

        Useful to promote packages (e.g. from "beta" to "stable") or transfer
        them from one user to another.
        """
        parser = argparse.ArgumentParser(description=self.copy.__doc__,
                                         prog="conan copy",
                                         formatter_class=SmartFormatter)
        parser.add_argument("reference", default="",
                            help='package reference. e.g., MyPackage/1.2@user/channel')
        parser.add_argument("user_channel", default="",
                            help='Destination user/channel. e.g., lasote/testing')
        parser.add_argument("-p", "--package", nargs=1, action=Extender,
                            help='copy specified package ID '
                            '[DEPRECATED: use full reference instead]')
        parser.add_argument("--all", action='store_true', default=False,
                            help='Copy all packages from the specified package recipe')
        parser.add_argument("--force", action='store_true', default=False,
                            help='Override destination packages and the package recipe')
        args = parser.parse_args(*args)

        try:
            pref = PackageReference.loads(args.reference, validate=True)
        except ConanException:
            reference = args.reference
            packages_list = args.package

            if packages_list:
                self._out.warn("Usage of `--package` argument is deprecated."
                               " Use a full reference instead: "
                               "`conan copy [...] {}:{}`".format(reference, packages_list[0]))

            if args.all and packages_list:
                raise ConanException("Cannot specify both --all and --package")
        else:
            reference = repr(pref.ref)
            packages_list = [pref.id]
            if args.package:
                raise ConanException("Use a full package reference (preferred) or the `--package`"
                                     " command argument, but not both.")

            if args.all:
                raise ConanException("'--all' argument cannot be used together with full reference")

        self._warn_python_version()

        return self._conan.copy(reference=reference, user_channel=args.user_channel,
                                force=args.force, packages=packages_list or args.all)

    def user(self, *args):
        """
        Authenticates against a remote with user/pass, caching the auth token.

        Useful to avoid the user and password being requested later. e.g. while
        you're uploading a package.  You can have one user for each remote.
        Changing the user, or introducing the password is only necessary to
        perform changes in remote packages.
        """
        # FIXME: Difficult and confusing CLI. Better with:
        # - conan user clean -> clean users
        # - conan user list ('remote') -> list users (of a remote)
        # - conan user auth 'remote' ('user') ('password') -> login a remote (w/o user or pass)
        # - conan user set 'user' 'remote' -> set user for a remote (not login) necessary??
        parser = argparse.ArgumentParser(description=self.user.__doc__,
                                         prog="conan user",
                                         formatter_class=SmartFormatter)
        parser.add_argument("name", nargs='?', default=None,
                            help='Username you want to use. If no name is provided it will show the'
                            ' current user')
        parser.add_argument('-c', '--clean', default=False, action='store_true',
                            help='Remove user and tokens for all remotes')
        parser.add_argument("-p", "--password", nargs='?', const="", type=str, action=OnceArgument,
                            help='User password. Use double quotes if password with spacing, '
                                 'and escape quotes if existing. If empty, the password is '
                                 'requested interactively (not exposed)')
        parser.add_argument("-r", "--remote", help='Use the specified remote server',
                            action=OnceArgument)
        parser.add_argument("-j", "--json", default=None, action=OnceArgument,
                            help='json file path where the user list will be written to')
        parser.add_argument("-s", "--skip-auth", default=False, action='store_true',
                            help='Skips the authentication with the server if there are local '
                                 'stored credentials. It doesn\'t check if the '
                                 'current credentials are valid or not')
        args = parser.parse_args(*args)

        if args.clean and any((args.name, args.remote, args.password, args.json, args.skip_auth)):
            raise ConanException("'--clean' argument cannot be used together with 'name', "
                                 "'--password', '--remote', '--json' or '--skip.auth'")
        elif args.json and any((args.name, args.password)):
            raise ConanException("'--json' cannot be used together with 'name' or '--password'")

        cwd = os.getcwd()
        info = None

        try:
            if args.clean:  # clean users
                self._conan.users_clean()
            elif not args.name and args.password is None:  # list users
                info = self._conan.users_list(args.remote)
                self._outputer.print_user_list(info)
            elif args.password is None:  # set user for remote (no password indicated)
                remote_name, prev_user, user = self._conan.user_set(args.name, args.remote)
                self._outputer.print_user_set(remote_name, prev_user, user)
            else:  # login a remote
                remote_name = args.remote or self._conan.get_default_remote().name
                name = args.name
                password = args.password
                remote_name, prev_user, user = self._conan.authenticate(name,
                                                                        remote_name=remote_name,
                                                                        password=password,
                                                                        skip_auth=args.skip_auth)

                self._outputer.print_user_set(remote_name, prev_user, user)
        except ConanException as exc:
            info = exc.info
            raise
        finally:
            if args.json and info:
                self._outputer.json_output(info, args.json, cwd)

    def search(self, *args):
        """
        Searches package recipes and binaries in the local cache or a remote.

        If you provide a pattern, then it will search for existing package
        recipes matching it.  If a full reference is provided
        (pkg/0.1@user/channel) then the existing binary packages for that
        reference will be displayed. The default remote is ignored, if no
        remote is specified, the search will be done in the local cache.
        Search is case sensitive, the exact case has to be used. For case
        insensitive file systems, like Windows, case sensitive search
        can be forced with '--case-sensitive'.
        """
        parser = argparse.ArgumentParser(description=self.search.__doc__,
                                         prog="conan search",
                                         formatter_class=SmartFormatter)
        parser.add_argument('pattern_or_reference', nargs='?', help=_PATTERN_OR_REFERENCE_HELP)
        parser.add_argument('-o', '--outdated', default=False, action='store_true',
                            help="Show only outdated from recipe packages. "
                                 "This flag can only be used with a reference")
        parser.add_argument('-q', '--query', default=None, action=OnceArgument, help=_QUERY_HELP)
        parser.add_argument('-r', '--remote', action=OnceArgument,
                            help="Remote to search in. '-r all' searches all remotes")
        parser.add_argument('--case-sensitive', default=False, action='store_true',
                            help='Make a case-sensitive search. Use it to guarantee '
                                 'case-sensitive '
                            'search in Windows or other case-insensitive file systems')
        parser.add_argument('--raw', default=False, action='store_true',
                            help='Print just the list of recipes')
        parser.add_argument('--table', action=OnceArgument,
                            help="Outputs html file with a table of binaries. Only valid for a "
                            "reference search")
        parser.add_argument("-j", "--json", default=None, action=OnceArgument,
                            help='json file path where the search information will be written to')
        parser.add_argument("-rev", "--revisions", default=False, action='store_true',
                            help='Get a list of revisions for a reference or a '
                                 'package reference.')

        args = parser.parse_args(*args)

        if args.table and args.json:
            raise ConanException("'--table' argument cannot be used together with '--json'")

        # Searching foo/bar is considered a pattern (FIXME: 2.0) so use strict mode to disambiguate
        is_reference = check_valid_ref(args.pattern_or_reference)

        if is_reference:
            ref = ConanFileReference.loads(args.pattern_or_reference)
        else:
            ref = None
            if args.query:
                raise ConanException("-q parameter only allowed with a valid recipe reference, "
                                     "not with a pattern")
        cwd = os.getcwd()
        info = None

        try:
            if args.revisions:
                # Show revisions of a ref
                if ref:
                    info = self._conan.get_recipe_revisions(repr(ref), remote_name=args.remote)
                    self._outputer.print_revisions(ref, info, args.raw, remote_name=args.remote)
                    return

                # Show revisions of pref
                try:
                    pref = PackageReference.loads(args.pattern_or_reference)
                except (TypeError, ConanException, AttributeError):
                    pass
                else:
                    info = self._conan.get_package_revisions(repr(pref), remote_name=args.remote)
                    self._outputer.print_revisions(ref, info, args.raw, remote_name=args.remote)
                    return

                # A pattern: Listing references by pattern but showing revisions
                if args.remote:
                    exc_msg = "With --revision, specify a reference (e.g {ref}) " \
                              "a valid pattern " \
                              "or a package reference with " \
                              "recipe revision (e.g {ref}#3453453453:" \
                              "d50a0d523d98c15bb147b18f" \
                              "a7d203887c38be8b)".format(ref=_REFERENCE_EXAMPLE)
                    raise ConanException(exc_msg)

                info = self._conan.search_recipes(args.pattern_or_reference, remote_name=None,
                                                  case_sensitive=args.case_sensitive,
                                                  fill_revisions=True)
                self._outputer.print_search_references(info["results"],
                                                       args.pattern_or_reference,
                                                       args.raw, all_remotes_search=None)
                return

            if ref:
                info = self._conan.search_packages(repr(ref), query=args.query,
                                                   remote_name=args.remote,
                                                   outdated=args.outdated)
                # search is done for one reference
                self._outputer.print_search_packages(info["results"], ref, args.query,
                                                     args.table, args.raw, outdated=args.outdated)
            else:
                if args.table:
                    raise ConanException("'--table' argument can only be used with a reference")
                elif args.outdated:
                    raise ConanException("'--outdated' argument can only be used with a reference")

                info = self._conan.search_recipes(args.pattern_or_reference,
                                                  remote_name=args.remote,
                                                  case_sensitive=args.case_sensitive)
                # Deprecate 2.0: Dirty check if search is done for all remotes or for remote "all"
                try:
                    remote_all = self._conan.get_remote_by_name("all")
                except NoRemoteAvailable:
                    remote_all = None
                all_remotes_search = (remote_all is None and args.remote == "all")
                self._outputer.print_search_references(info["results"], args.pattern_or_reference,
                                                       args.raw, all_remotes_search)
        except ConanException as exc:
            info = exc.info
            raise
        finally:
            if args.json and info:
                self._outputer.json_output(info, args.json, cwd)

    def upload(self, *args):
        """
        Uploads a recipe and binary packages to a remote.

        If no remote is specified, the first configured remote (by default conan-center, use
        'conan remote list' to list the remotes) will be used.
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
        parser.add_argument("-r", "--remote", action=OnceArgument,
                            help='upload to this specific remote')
        parser.add_argument("--all", action='store_true', default=False,
                            help='Upload both package recipe and packages')
        parser.add_argument("--skip-upload", action='store_true', default=False,
                            help='Do not upload anything, just run the checks and the compression')
        parser.add_argument("--force", action='store_true', default=False,
                            help='Do not check conan recipe date, override remote with local')
        parser.add_argument("--check", action='store_true', default=False,
                            help='Perform an integrity check, using the manifests, before upload')
        parser.add_argument('-c', '--confirm', default=False, action='store_true',
                            help='Upload all matching recipes without confirmation')
        parser.add_argument('--retry', default=None, type=int, action=OnceArgument,
                            help="In case of fail retries to upload again the specified times.")
        parser.add_argument('--retry-wait', default=None, type=int, action=OnceArgument,
                            help='Waits specified seconds before retry again')
        parser.add_argument("-no", "--no-overwrite", nargs="?", type=str, choices=["all", "recipe"],
                            action=OnceArgument, const="all",
                            help="Uploads package only if recipe is the same as the remote one")
        parser.add_argument("-j", "--json", default=None, action=OnceArgument,
                            help='json file path where the upload information will be written to')
        parser.add_argument("--parallel", action='store_true', default=False,
                            help='Upload files in parallel using multiple threads '
                                 'The default number of launched threads is 8')

        args = parser.parse_args(*args)

        try:
            pref = PackageReference.loads(args.pattern_or_reference, validate=True)
        except ConanException:
            reference = args.pattern_or_reference
            package_id = args.package

            if package_id:
                self._out.warn("Usage of `--package` argument is deprecated."
                               " Use a full reference instead: "
                               "`conan upload [...] {}:{}`".format(reference, package_id))

            if args.query and package_id:
                raise ConanException("'--query' argument cannot be used together with '--package'")
        else:
            reference = repr(pref.ref)
            package_id = "{}#{}".format(pref.id, pref.revision) if pref.revision else pref.id

            if args.package:
                raise ConanException("Use a full package reference (preferred) or the `--package`"
                                     " command argument, but not both.")
            if args.query:
                raise ConanException("'--query' argument cannot be used together with "
                                     "full reference")

        if args.force and args.no_overwrite:
            raise ConanException("'--no-overwrite' argument cannot be used together with '--force'")
        if args.force and args.skip_upload:
            raise ConanException("'--skip-upload' argument cannot be used together with '--force'")
        if args.no_overwrite and args.skip_upload:
            raise ConanException("'--skip-upload' argument cannot be used together "
                                 "with '--no-overwrite'")

        self._warn_python_version()

        if args.force:
            policy = UPLOAD_POLICY_FORCE
        elif args.no_overwrite == "all":
            policy = UPLOAD_POLICY_NO_OVERWRITE
        elif args.no_overwrite == "recipe":
            policy = UPLOAD_POLICY_NO_OVERWRITE_RECIPE
        elif args.skip_upload:
            policy = UPLOAD_POLICY_SKIP
        else:
            policy = None

        info = None
        try:
            info = self._conan.upload(pattern=reference, package=package_id,
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
                self._outputer.json_output(info, args.json, os.getcwd())

    def remote(self, *args):
        """
        Manages the remote list and the package recipes associated with a remote.
        """
        parser = argparse.ArgumentParser(description=self.remote.__doc__,
                                         prog="conan remote",
                                         formatter_class=SmartFormatter)
        subparsers = parser.add_subparsers(dest='subcommand', help='sub-command help')
        subparsers.required = True

        # create the parser for the "a" command
        parser_list = subparsers.add_parser('list', help='List current remotes')
        parser_list.add_argument("-raw", "--raw", action='store_true', default=False,
                                 help='Raw format. Valid for "remotes.txt" file for '
                                 '"conan config install"')
        parser_add = subparsers.add_parser('add', help='Add a remote')
        parser_add.add_argument('remote', help='Name of the remote')
        parser_add.add_argument('url', help='URL of the remote')
        parser_add.add_argument('verify_ssl', nargs="?", default="True",
                                help='Verify SSL certificated. Default True')
        parser_add.add_argument("-i", "--insert", nargs="?", const=0, type=int, action=OnceArgument,
                                help="insert remote at specific index")
        parser_add.add_argument("-f", "--force", default=False, action='store_true',
                                help="Force addition, will update if existing")
        parser_rm = subparsers.add_parser('remove', help='Remove a remote')
        parser_rm.add_argument('remote', help='Name of the remote')
        parser_upd = subparsers.add_parser('update', help='Update the remote url')
        parser_upd.add_argument('remote', help='Name of the remote')

        parser_upd.add_argument('url', help='URL')
        parser_upd.add_argument('verify_ssl', nargs="?", default="True",
                                help='Verify SSL certificated. Default True')
        parser_upd.add_argument("-i", "--insert", nargs="?", const=0, type=int, action=OnceArgument,
                                help="Insert remote at specific index")
        parser_rename = subparsers.add_parser('rename', help='Update the remote name')
        parser_rename.add_argument('remote', help='The old remote name')
        parser_rename.add_argument('new_remote', help='The new remote name')

        subparsers.add_parser('list_ref',
                              help='List the package recipes and its associated remotes')
        parser_padd = subparsers.add_parser('add_ref',
                                            help="Associate a recipe's reference to a remote")
        parser_padd.add_argument('reference', help='Package recipe reference')
        parser_padd.add_argument('remote', help='Name of the remote')
        parser_prm = subparsers.add_parser('remove_ref',
                                           help="Dissociate a recipe's reference and its remote")
        parser_prm.add_argument('reference', help='Package recipe reference')
        parser_pupd = subparsers.add_parser('update_ref', help="Update the remote associated with "
                                            "a package recipe")
        parser_pupd.add_argument('reference', help='Package recipe reference')
        parser_pupd.add_argument('remote', help='Name of the remote')

        list_pref = subparsers.add_parser('list_pref', help='List the package binaries and '
                                                            'its associated remotes')
        list_pref.add_argument('reference', help='Package recipe reference')

        add_pref = subparsers.add_parser('add_pref',
                                         help="Associate a package reference to a remote")
        add_pref.add_argument('package_reference', help='Binary package reference')
        add_pref.add_argument('remote', help='Name of the remote')

        remove_pref = subparsers.add_parser('remove_pref', help="Dissociate a package's reference "
                                                                "and its remote")
        remove_pref.add_argument('package_reference', help='Binary package reference')

        update_pref = subparsers.add_parser('update_pref', help="Update the remote associated with "
                                            "a binary package")
        update_pref.add_argument('package_reference', help='Bianary package reference')
        update_pref.add_argument('remote', help='Name of the remote')

        subparsers.add_parser('clean', help="Clean the list of remotes and all "
                                            "recipe-remote associations")

        parser_enable = subparsers.add_parser('enable', help='Enable a remote')
        parser_enable.add_argument('remote', help='Name of the remote')
        parser_disable = subparsers.add_parser('disable', help='Disable a remote')
        parser_disable.add_argument('remote', help='Name of the remote')

        args = parser.parse_args(*args)

        reference = args.reference if hasattr(args, 'reference') else None
        package_reference = args.package_reference if hasattr(args, 'package_reference') else None

        verify_ssl = get_bool_from_text(args.verify_ssl) if hasattr(args, 'verify_ssl') else False

        remote_name = args.remote if hasattr(args, 'remote') else None
        new_remote = args.new_remote if hasattr(args, 'new_remote') else None
        url = args.url if hasattr(args, 'url') else None

        if args.subcommand == "list":
            remotes = self._conan.remote_list()
            self._outputer.remote_list(remotes, args.raw)
        elif args.subcommand == "add":
            return self._conan.remote_add(remote_name, url, verify_ssl, args.insert, args.force)
        elif args.subcommand == "remove":
            return self._conan.remote_remove(remote_name)
        elif args.subcommand == "rename":
            return self._conan.remote_rename(remote_name, new_remote)
        elif args.subcommand == "update":
            return self._conan.remote_update(remote_name, url, verify_ssl, args.insert)
        elif args.subcommand == "list_ref":
            refs = self._conan.remote_list_ref()
            self._outputer.remote_ref_list(refs)
        elif args.subcommand == "add_ref":
            return self._conan.remote_add_ref(reference, remote_name)
        elif args.subcommand == "remove_ref":
            return self._conan.remote_remove_ref(reference)
        elif args.subcommand == "update_ref":
            return self._conan.remote_update_ref(reference, remote_name)
        elif args.subcommand == "list_pref":
            refs = self._conan.remote_list_pref(reference)
            self._outputer.remote_pref_list(refs)
        elif args.subcommand == "add_pref":
            return self._conan.remote_add_pref(package_reference, remote_name)
        elif args.subcommand == "remove_pref":
            return self._conan.remote_remove_pref(package_reference)
        elif args.subcommand == "update_pref":
            return self._conan.remote_update_pref(package_reference, remote_name)
        elif args.subcommand == "clean":
            return self._conan.remote_clean()
        elif args.subcommand == "enable":
            return self._conan.remote_set_disabled_state(remote_name, False)
        elif args.subcommand == "disable":
            return self._conan.remote_set_disabled_state(remote_name, True)

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
        subparsers = parser.add_subparsers(dest='subcommand')
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
            profiles = self._conan.profile_list()
            self._outputer.profile_list(profiles)
            if args.json:
                self._outputer.json_output(profiles, args.json, os.getcwd())
        elif args.subcommand == "show":
            profile_text = self._conan.read_profile(profile)
            self._outputer.print_profile(profile, profile_text)
        elif args.subcommand == "new":
            self._conan.create_profile(profile, args.detect, args.force)
        elif args.subcommand == "update":
            try:
                key, value = args.item.split("=", 1)
            except ValueError:
                raise ConanException("Please specify key=value")
            self._conan.update_profile(profile, key, value)
        elif args.subcommand == "get":
            key = args.item
            self._out.writeln(self._conan.get_profile_key(profile, key))
        elif args.subcommand == "remove":
            self._conan.delete_profile_key(profile, args.item)

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
            pref = PackageReference.loads(args.reference, validate=True)
        except ConanException:
            reference = args.reference
            package_id = args.package

            if package_id:
                self._out.warn("Usage of `--package` argument is deprecated."
                               " Use a full reference instead: "
                               "`conan get [...] {}:{}`".format(reference, package_id))
        else:
            reference = repr(pref.ref)
            package_id = pref.id
            if args.package:
                raise ConanException("Use a full package reference (preferred) or the `--package`"
                                     " command argument, but not both.")

        ret, path = self._conan.get_path(reference, package_id, args.path, args.remote)
        if isinstance(ret, list):
            self._outputer.print_dir_list(ret, path, args.raw)
        else:
            self._outputer.print_file_contents(ret, path, args.raw)

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

        self._conan.export_alias(args.reference, args.target)

    def workspace(self, *args):
        """
        Manages a workspace (a set of packages consumed from the user workspace that
        belongs to the same project).

        Use this command to manage a Conan workspace, use the subcommand 'install' to
        create the workspace from a file.
        """
        parser = argparse.ArgumentParser(description=self.workspace.__doc__,
                                         prog="conan workspace",
                                         formatter_class=SmartFormatter)
        subparsers = parser.add_subparsers(dest='subcommand', help='sub-command help')
        subparsers.required = True

        install_parser = subparsers.add_parser('install',
                                               help='same as a "conan install" command'
                                                    ' but using the workspace data from the file. '
                                                    'If no file is provided, it will look for a '
                                                    'file named "conanws.yml"')
        install_parser.add_argument('path', help='path to workspace definition file (it will look'
                                                 ' for a "conanws.yml" inside if a directory is'
                                                 ' given)')
        _add_common_install_arguments(install_parser, build_help=_help_build_policies.format("never"))
        install_parser.add_argument("-if", "--install-folder", action=OnceArgument,
                                    help="Folder where the workspace files will be created"
                                         " (default to current working directory)")

        args = parser.parse_args(*args)

        if args.subcommand == "install":
            self._conan.workspace_install(args.path, args.settings, args.options, args.env,
                                          args.remote, args.build,
                                          args.profile, args.update,
                                          install_folder=args.install_folder)

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
        add_parser.add_argument("-l", "--layout",
                                help='Relative or absolute path to a file containing the layout.'
                                ' Relative paths will be resolved first relative to current dir, '
                                'then to local cache "layouts" folder')

        remove_parser = subparsers.add_parser('remove', help='Disable editable mode for a package')
        remove_parser.add_argument('reference',
                                   help='Package reference e.g.: mylib/1.X@user/channel')

        subparsers.add_parser('list', help='List packages in editable mode')

        args = parser.parse_args(*args)
        self._warn_python_version()

        if args.subcommand == "add":
            self._conan.editable_add(args.path, args.reference, args.layout, cwd=os.getcwd())
            self._out.success("Reference '{}' in editable mode".format(args.reference))
        elif args.subcommand == "remove":
            ret = self._conan.editable_remove(args.reference)
            if ret:
                self._out.success("Removed editable mode for reference '{}'".format(args.reference))
            else:
                self._out.warn("Reference '{}' was not installed "
                               "as editable".format(args.reference))
        elif args.subcommand == "list":
            for k, v in self._conan.editable_list().items():
                self._out.info("%s" % k)
                self._out.writeln("    Path: %s" % v["path"])
                self._out.writeln("    Layout: %s" % v["layout"])

    def graph(self, *args):
        """
        Generates and manipulates lock files.
        """
        parser = argparse.ArgumentParser(description=self.graph.__doc__,
                                         prog="conan graph",
                                         formatter_class=SmartFormatter)
        subparsers = parser.add_subparsers(dest='subcommand', help='sub-command help')
        subparsers.required = True

        # create the parser for the "a" command
        merge_cmd = subparsers.add_parser('update-lock', help='merge two lockfiles')
        merge_cmd.add_argument('old_lockfile', help='path to previous lockfile')
        merge_cmd.add_argument('new_lockfile', help='path to modified lockfile')

        build_order_cmd = subparsers.add_parser('build-order', help='Returns build-order')
        build_order_cmd.add_argument('lockfile', help='lockfile folder')
        build_order_cmd.add_argument("-b", "--build", action=Extender, nargs="?",
                                     help="nodes to build")
        build_order_cmd.add_argument("--json", action=OnceArgument,
                                     help="generate output file in json format")

        lock_cmd = subparsers.add_parser('lock', help='create a lockfile')
        lock_cmd.add_argument("path_or_reference", help="Path to a folder containing a recipe"
                              " (conanfile.py or conanfile.txt) or to a recipe file. e.g., "
                              "./my_project/conanfile.txt. It could also be a reference")
        lock_cmd.add_argument("-l", "--lockfile", action=OnceArgument,
                              help="Path to lockfile to be created. If not specified 'conan.lock'"
                              " will be created in current folder")
        _add_common_install_arguments(lock_cmd, build_help="Packages to build from source",
                                      lockfile=False)

        args = parser.parse_args(*args)
        self._warn_python_version()

        if args.subcommand == "update-lock":
            self._conan.update_lock(args.old_lockfile, args.new_lockfile)
        elif args.subcommand == "build-order":
            build_order = self._conan.build_order(args.lockfile, args.build)
            self._out.writeln(build_order)
            if args.json:
                json_file = _make_abs_path(args.json)
                save(json_file, json.dumps(build_order, indent=True))
        elif args.subcommand == "lock":
            self._conan.create_lock(args.path_or_reference,
                                    remote_name=args.remote,
                                    settings=args.settings,
                                    options=args.options,
                                    env=args.env,
                                    profile_names=args.profile,
                                    update=args.update,
                                    lockfile=args.lockfile,
                                    build=args.build)

    def _show_help(self):
        """
        Prints a summary of all commands.
        """
        grps = [("Consumer commands", ("install", "config", "get", "info", "search")),
                ("Creator commands", ("new", "create", "upload", "export", "export-pkg", "test")),
                ("Package development commands", ("source", "build", "package", "editable",
                                                  "workspace")),
                ("Misc commands", ("profile", "remote", "user", "imports", "copy", "remove",
                                   "alias", "download", "inspect", "help", "graph"))]

        def check_all_commands_listed():
            """Keep updated the main directory, raise if don't"""
            all_commands = self._commands()
            all_in_grps = [command for _, command_list in grps for command in command_list]
            if set(all_in_grps) != set(all_commands):
                diff = set(all_commands) - set(all_in_grps)
                raise Exception("Some command is missing in the main help: %s" % ",".join(diff))
            return all_commands

        commands = check_all_commands_listed()
        max_len = max((len(c) for c in commands)) + 1
        fmt = '  %-{}s'.format(max_len)

        for group_name, comm_names in grps:
            self._out.writeln(group_name, Color.BRIGHT_MAGENTA)
            for name in comm_names:
                # future-proof way to ensure tabular formatting
                self._out.write(fmt % name, Color.GREEN)

                # Help will be all the lines up to the first empty one
                docstring_lines = commands[name].__doc__.split('\n')
                start = False
                data = []
                for line in docstring_lines:
                    line = line.strip()
                    if not line:
                        if start:
                            break
                        start = True
                        continue
                    data.append(line)

                import textwrap
                txt = textwrap.fill(' '.join(data), 80, subsequent_indent=" "*(max_len+2))
                self._out.writeln(txt)

        self._out.writeln("")
        self._out.writeln('Conan commands. Type "conan <command> -h" for help', Color.BRIGHT_YELLOW)

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
            self._out.writeln("The most similar commands are")
        else:
            self._out.writeln("The most similar command is")

        for match in matches:
            self._out.writeln("    %s" % match)

        self._out.writeln("")

    def _warn_python_version(self):
        import textwrap

        width = 70
        version = sys.version_info
        if version.major == 2:
            self._out.writeln("*"*width, front=Color.BRIGHT_RED)

            self._out.writeln(textwrap.fill("Python 2 is deprecated as of 01/01/2020 and Conan has"
                                            " stopped supporting it officially. We strongly recommend"
                                            " you to use Python >= 3.5. Conan will completely stop"
                                            " working with Python 2 in the following releases", width),
                              front=Color.BRIGHT_RED)
            self._out.writeln("*"*width, front=Color.BRIGHT_RED)
            if os.environ.get('USE_UNSUPPORTED_CONAN_WITH_PYTHON_2', 0):
                # IMPORTANT: This environment variable is not a silver buller. Python 2 is currently deprecated
                # and some libraries we use as dependencies have stopped supporting it. Conan might fail to run
                # and we are no longer fixing errors related to Python 2.
                self._out.writeln(textwrap.fill("Python 2 deprecation notice has been bypassed"
                                                " by envvar 'USE_UNSUPPORTED_CONAN_WITH_PYTHON_2'", width))
            else:
                self._out.writeln(textwrap.fill("If you really need to run Conan with Python 2 in your"
                                                " CI without this interactive input, please contact us"
                                                " at info@conan.io", width), front=Color.BRIGHT_RED)
                self._out.writeln("*" * width, front=Color.BRIGHT_RED)
                self._out.write(textwrap.fill("Understood the risk, keep going [y/N]: ", width,
                                              drop_whitespace=False), front=Color.BRIGHT_RED)
                ret = raw_input().lower()
                if ret not in ["yes", "ye", "y"]:
                    self._out.writeln(textwrap.fill("Wise choice. Stopping here!", width))
                    sys.exit(0)
        elif version.minor == 4:
            self._out.writeln("*"*width, front=Color.BRIGHT_RED)
            self._out.writeln(textwrap.fill("Python 3.4 support has been dropped. It is strongly "
                                            "recommended to use Python >= 3.5 with Conan", width),
                              front=Color.BRIGHT_RED)
            self._out.writeln("*"*width, front=Color.BRIGHT_RED)

    def run(self, *args):
        """HIDDEN: entry point for executing commands, dispatcher to class
        methods
        """
        ret_code = SUCCESS
        try:
            try:
                command = args[0][0]
            except IndexError:  # No parameters
                self._show_help()
                return False
            try:
                commands = self._commands()
                method = commands[command]
            except KeyError as exc:
                if command in ["-v", "--version"]:
                    self._out.success("Conan version %s" % client_version)
                    return False

                self._warn_python_version()

                if command in ["-h", "--help"]:
                    self._show_help()
                    return False

                self._out.writeln(
                    "'%s' is not a Conan command. See 'conan --help'." % command)
                self._out.writeln("")
                self._print_similar(command)
                raise ConanException("Unknown command %s" % str(exc))

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


def _add_manifests_arguments(parser):
    parser.add_argument("-m", "--manifests", const=default_manifest_folder, nargs="?",
                        help='Install dependencies manifests in folder for later verify.'
                             ' Default folder is .conan_manifests, but can be changed',
                        action=OnceArgument)
    parser.add_argument("-mi", "--manifests-interactive", const=default_manifest_folder,
                        nargs="?",
                        help='Install dependencies manifests in folder for later verify, '
                             'asking user for confirmation. '
                             'Default folder is .conan_manifests, but can be changed',
                        action=OnceArgument)
    parser.add_argument("-v", "--verify", const=default_manifest_folder, nargs="?",
                        help='Verify dependencies manifests against stored ones',
                        action=OnceArgument)


def _add_common_install_arguments(parser, build_help, lockfile=True):
    if build_help:
        parser.add_argument("-b", "--build", action=Extender, nargs="?", help=build_help)

    parser.add_argument("-e", "--env", nargs=1, action=Extender,
                        help='Environment variables that will be set during the package build, '
                             '-e CXX=/usr/bin/clang++')
    parser.add_argument("-o", "--options", nargs=1, action=Extender,
                        help='Define options values, e.g., -o Pkg:with_qt=True')
    parser.add_argument("-pr", "--profile", default=None, action=Extender,
                        help='Apply the specified profile to the install command')
    parser.add_argument("-r", "--remote", action=OnceArgument,
                        help='Look in the specified remote server')
    parser.add_argument("-s", "--settings", nargs=1, action=Extender,
                        help='Settings to build the package, overwriting the defaults. e.g., '
                             '-s compiler=gcc')
    parser.add_argument("-u", "--update", action='store_true', default=False,
                        help="Check updates exist from upstream remotes")
    if lockfile:
        parser.add_argument("-l", "--lockfile", action=OnceArgument, nargs='?', const=".",
                            help="Path to a lockfile or folder containing 'conan.lock' file. "
                            "Lockfile can be updated if packages change")


_help_build_policies = '''Optional, use it to choose if you want to build from sources:

    --build            Build all from sources, do not use binary packages.
    --build=never      Never build, use binary packages or fail if a binary package is not found.
    --build=missing    Build from code if a binary package is not found.
    --build=cascade    Will build from code all the nodes with some dependency being built
                       (for any reason). Can be used together with any other build policy.
                       Useful to make sure that any new change introduced in a dependency is
                       incorporated by building again the package.
    --build=outdated   Build from code if the binary is not built with the current recipe or
                       when missing a binary package.
    --build=[pattern]  Build always these packages from source, but never build the others.
                       Allows multiple --build parameters. 'pattern' is a fnmatch file pattern
                       of a package reference.

    Default behavior: If you don't specify anything, it will be similar to '--build={}', but
    package recipes can override it with their 'build_policy' attribute in the conanfile.py.
'''


def main(args):
    """ main entry point of the conan application, using a Command to
    parse parameters

    Exit codes for conan command:

        0: Success (done)
        1: General ConanException error (done)
        2: Migration error
        3: Ctrl+C
        4: Ctrl+Break
        5: SIGTERM
        6: Invalid configuration (done)
    """
    try:
        conan_api, _, _ = Conan.factory()
    except ConanMigrationError:  # Error migrating
        sys.exit(ERROR_MIGRATION)
    except ConanException as e:
        sys.stderr.write("Error in Conan initialization: {}".format(e))
        sys.exit(ERROR_GENERAL)

    command = Command(conan_api)
    current_dir = get_cwd()
    try:
        import signal

        def ctrl_c_handler(_, __):
            print('You pressed Ctrl+C!')
            sys.exit(USER_CTRL_C)

        def sigterm_handler(_, __):
            print('Received SIGTERM!')
            sys.exit(ERROR_SIGTERM)

        def ctrl_break_handler(_, __):
            print('You pressed Ctrl+Break!')
            sys.exit(USER_CTRL_BREAK)

        signal.signal(signal.SIGINT, ctrl_c_handler)
        signal.signal(signal.SIGTERM, sigterm_handler)

        if sys.platform == 'win32':
            signal.signal(signal.SIGBREAK, ctrl_break_handler)
        error = command.run(args)
    finally:
        os.chdir(current_dir)
    sys.exit(error)
