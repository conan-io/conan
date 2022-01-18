import argparse
import inspect
import json
import os
import sys
from argparse import ArgumentError
from difflib import get_close_matches

from conans.cli.exit_codes import SUCCESS, ERROR_GENERAL, ERROR_INVALID_CONFIGURATION, \
    ERROR_INVALID_SYSTEM_REQUIREMENTS
from conans.cli.output import ConanOutput
from conans.client.cmd.uploader import UPLOAD_POLICY_FORCE, UPLOAD_POLICY_SKIP
from conans.client.conan_api import ConanAPIV1, ProfileData
from conans.client.conan_command_output import CommandOutputer
from conans.errors import ConanException, ConanInvalidConfiguration
from conans.errors import ConanInvalidSystemRequirements
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
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
            if "@" in args.path and RecipeReference.loads(args.path):
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
            if "@" in args.path and RecipeReference.loads(args.path):
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

    def upload(self, *args):
        """
        Uploads a recipe and binary packages to a remote.

        If no remote is specified, it fails.
        """
        parser = argparse.ArgumentParser(description=self.upload.__doc__,
                                         prog="conan upload",
                                         formatter_class=SmartFormatter)
        parser.add_argument('pattern_or_reference', help=_PATTERN_REF_OR_PREF_HELP)
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
        else:
            reference = repr(pref)
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
            info = self._conan_api.upload(pattern=reference,
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
