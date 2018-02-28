import argparse
import inspect
import os
import sys
from argparse import ArgumentError

from conans import __version__ as client_version
from conans.client.conan_api import (Conan, default_manifest_folder)
from conans.client.conan_command_output import CommandOutputer
from conans.client.output import Color

from conans.errors import ConanException
from conans.model.ref import ConanFileReference
from conans.util.config_parser import get_bool_from_text
from conans.util.log import logger
from conans.util.files import exception_message_safe


class Extender(argparse.Action):
    """Allows to use the same flag several times in a command and creates a list with the values.
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

        try:
            dest.extend(values)
        except ValueError:
            dest.append(values)


class OnceArgument(argparse.Action):
    """Allows to declare a parameter that can have only one value, by default argparse takes the
    latest declared and it's very confusing"""
    def __call__(self, parser, namespace, values, option_string=None):
        if getattr(namespace, self.dest) is not None and self.default is None:
            msg = '{o} can only be specified once'.format(o=option_string)
            raise argparse.ArgumentError(None, msg)
        setattr(namespace, self.dest, values)


_PATH_HELP = ("path to a folder containing a recipe (conanfile.py) "
              "or to a recipe file, e.g., conan package folder/conanfile.py")


class Command(object):
    """ A single command of the conan application, with all the first level commands.
    Manages the parsing of parameters and delegates functionality in
    collaborators.
    It can also show help of the tool
    """
    def __init__(self, conan_api, client_cache, user_io, outputer):
        assert isinstance(conan_api, Conan)
        self._conan = conan_api
        self._client_cache = client_cache
        self._user_io = user_io
        self._outputer = outputer

    def help(self, *args):
        """Show help of a specific commmand.
        """
        parser = argparse.ArgumentParser(description=self.help.__doc__, prog="conan help")
        parser.add_argument("command", help='command', nargs="?")
        args = parser.parse_args(*args)
        if not args.command:
            self._show_help()
            return
        try:
            commands = self._commands()
            method = commands[args.command]
            method(["--help"])
        except KeyError:
            raise ConanException("Unknown command '%s'" % args.command)

    def new(self, *args):
        """Creates a new package recipe template with a 'conanfile.py'.
        And optionally, 'test_package' package testing files.
        """
        parser = argparse.ArgumentParser(description=self.new.__doc__, prog="conan new")
        parser.add_argument("name", help='Package name, e.g.: "Poco/1.7.3" or complete reference'
                                         ' for CI scripts: "Poco/1.7.3@conan/stable"')
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
                            help='Create the minimum package recipe, without build() method'
                            'Useful in combination with "export-pkg" command')
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
        parser.add_argument("-gi", "--gitignore", action='store_true', default=False,
                            help='Generate a .gitignore with the known patterns to excluded')
        parser.add_argument("-ciu", "--ci-upload-url",
                            help='Define URL of the repository to upload')

        args = parser.parse_args(*args)
        self._conan.new(args.name, header=args.header, pure_c=args.pure_c, test=args.test,
                        exports_sources=args.sources, bare=args.bare,
                        visual_versions=args.ci_appveyor_win,
                        linux_gcc_versions=args.ci_travis_gcc,
                        linux_clang_versions=args.ci_travis_clang,
                        gitignore=args.gitignore,
                        osx_clang_versions=args.ci_travis_osx, shared=args.ci_shared,
                        upload_url=args.ci_upload_url,
                        gitlab_gcc_versions=args.ci_gitlab_gcc,
                        gitlab_clang_versions=args.ci_gitlab_clang)

    def test(self, *args):
        """ Test a package, consuming it with a conanfile recipe with a test() method.
        This command installs the conanfile dependencies (including the tested
        package), calls a "conan build" to build test apps, and finally executes
        the test() method.
        The testing recipe is not a package, does not require name/version,
        neither define package() or package_info() methods.
        The package to be tested must exist in the local cache or any configured remote.
        To create and test a binary package use the 'conan create' command.
        """
        parser = argparse.ArgumentParser(description=self.test.__doc__, prog="conan test")
        parser.add_argument("-tbf", "--test-build-folder", action=OnceArgument,
                            help="Optional. Working directory of the build process.")
        parser.add_argument("path", help='path to the "testing" folder containing a recipe '
                            '(conanfile.py) with a test() method or to a recipe file, '
                            'e.g. conan test_package/conanfile.py pkg/version@user/channel')
        parser.add_argument("reference",
                            help='a full package reference pkg/version@user/channel, of the '
                            'package to be tested')

        _add_common_install_arguments(parser, build_help=_help_build_policies)
        args = parser.parse_args(*args)
        return self._conan.test(args.path, args.reference, args.profile, args.settings,
                                args.options, args.env, args.remote, args.update,
                                build_modes=args.build, test_build_folder=args.test_build_folder)

    def create(self, *args):
        """ Builds a binary package for recipe (conanfile.py) located in current dir.
        Uses the specified configuration in a profile or in -s settings, -o options etc.
        If a 'test_package' folder (the name can be configured with -tf) is found, the command will
        run the consumer project to ensure that the package has been created correctly. Check the
        'conan test' command to know more about the 'test_folder' project.
        """
        parser = argparse.ArgumentParser(description=self.create.__doc__,
                                         prog="conan create")
        parser.add_argument("path", help=_PATH_HELP)
        parser.add_argument("reference", help='user/channel, or a full package reference'
                                              ' (Pkg/version@user/channel), if name and version '
                                              ' are not declared in the recipe (conanfile.py)')
        parser.add_argument("-ne", "--not-export", default=False, action='store_true',
                            help='Do not export the conanfile')
        parser.add_argument("-tf", "--test-folder", action=OnceArgument,
                            help='alternative test folder name, by default is "test_package". '
                                 '"None" if test stage needs to be disabled')
        parser.add_argument("-tbf", "--test-build-folder", action=OnceArgument,
                            help='Optional. Working directory for the build of the test project.')
        parser.add_argument('-k', '--keep-source', default=False, action='store_true',
                            help='Optional. Do not remove the source folder in local cache. '
                                 'Use for testing purposes only')
        parser.add_argument('-kb', '--keep-build', default=False, action='store_true',
                            help='Optional. Do not remove the build folder in local cache. '
                                 'Use for testing purposes only')

        _add_manifests_arguments(parser)
        _add_common_install_arguments(parser, build_help=_help_build_policies)

        args = parser.parse_args(*args)

        name, version, user, channel = get_reference_fields(args.reference)

        if args.test_folder == "None":
            # Now if parameter --test-folder=None (string None) we have to skip tests
            args.test_folder = False

        return self._conan.create(args.path, name, version, user, channel,
                                  args.profile, args.settings, args.options,
                                  args.env, args.test_folder, args.not_export,
                                  args.build, args.keep_source, args.keep_build, args.verify,
                                  args.manifests, args.manifests_interactive,
                                  args.remote, args.update,
                                  test_build_folder=args.test_build_folder)

    def download(self, *args):
        """Downloads recipe and binaries to the local cache, without using settings.
         It works specifying the recipe reference and package ID to be installed.
         Not transitive, requirements of the specified reference will be retrieved.
         Useful together with 'conan copy' to automate the promotion of
         packages to a different user/channel. If only a reference is specified, it will download
         all packages in the specified remote.
         If no remote is specified will search sequentially in the available configured remotes."""

        parser = argparse.ArgumentParser(description=self.download.__doc__, prog="conan download")
        parser.add_argument("reference",
                            help='package recipe reference e.g., MyPackage/1.2@user/channel')
        parser.add_argument("-p", "--package", nargs=1, action=Extender,
                            help='Force install specified package ID (ignore settings/options)')
        parser.add_argument("-r", "--remote", help='look in the specified remote server',
                            action=OnceArgument)

        args = parser.parse_args(*args)

        return self._conan.download(reference=args.reference, package=args.package, remote=args.remote)

    def install(self, *args):
        """Installs the requirements specified in a conanfile (.py or .txt).
           If any requirement is not found in the local cache it will retrieve the recipe from a
           remote, looking for it sequentially in the available configured remotes.
           When the recipes have been downloaded it will try to download a binary package matching
           the specified settings, only from the remote from which the recipe was retrieved.
           If no binary package is found you can build the package from sources using the '--build'
           option.
           When the package is installed, Conan will write the files for the specified generators.
           It can also be used to install a concrete recipe/package specifying a reference in the
           "path" parameter.

        """
        parser = argparse.ArgumentParser(description=self.install.__doc__, prog="conan install")
        parser.add_argument("path", help="path to a folder containing a recipe"
                            " (conanfile.py or conanfile.txt) or to a recipe file. e.g., "
                            "./my_project/conanfile.txt. It could also be a reference")
        parser.add_argument("-g", "--generator", nargs=1, action=Extender,
                            help='Generators to use')
        parser.add_argument("-if", "--install-folder", action=OnceArgument,
                            help='Use this directory as the directory where to put the generator'
                                 'files, conaninfo/conanbuildinfo.txt etc.')

        _add_manifests_arguments(parser)

        parser.add_argument("--no-imports", action='store_true', default=False,
                            help='Install specified packages but avoid running imports')

        _add_common_install_arguments(parser, build_help=_help_build_policies)

        args = parser.parse_args(*args)

        try:
            reference = ConanFileReference.loads(args.path)
        except ConanException:
            return self._conan.install(path=args.path,
                                       settings=args.settings, options=args.options,
                                       env=args.env,
                                       remote=args.remote,
                                       verify=args.verify, manifests=args.manifests,
                                       manifests_interactive=args.manifests_interactive,
                                       build=args.build, profile_name=args.profile,
                                       update=args.update, generators=args.generator,
                                       no_imports=args.no_imports,
                                       install_folder=args.install_folder)
        else:
            return self._conan.install_reference(reference, settings=args.settings,
                                                 options=args.options,
                                                 env=args.env,
                                                 remote=args.remote,
                                                 verify=args.verify, manifests=args.manifests,
                                                 manifests_interactive=args.manifests_interactive,
                                                 build=args.build, profile_name=args.profile,
                                                 update=args.update,
                                                 generators=args.generator,
                                                 install_folder=args.install_folder)

    def config(self, *args):
        """Manages configuration. Edits the conan.conf or installs config files.
        """
        parser = argparse.ArgumentParser(description=self.config.__doc__, prog="conan config")

        subparsers = parser.add_subparsers(dest='subcommand', help='sub-command help')
        rm_subparser = subparsers.add_parser('rm', help='rm an existing config element')
        set_subparser = subparsers.add_parser('set', help='set/add value')
        get_subparser = subparsers.add_parser('get', help='get the value of existing element')
        install_subparser = subparsers.add_parser('install',
                                                  help='install a full configuration from a zip '
                                                       'file, local or remote')

        rm_subparser.add_argument("item", help="item to remove")
        get_subparser.add_argument("item", nargs="?", help="item to print")
        set_subparser.add_argument("item", help="key=value to set")
        install_subparser.add_argument("item", nargs="?", help="configuration file to use")

        install_subparser.add_argument("--verify-ssl", nargs="?", default="True",
                                       help='Verify SSL connection when downloading file')

        args = parser.parse_args(*args)

        if args.subcommand == "set":
            try:
                key, value = args.item.split("=", 1)
            except ValueError:
                raise ConanException("Please specify key=value")
            return self._conan.config_set(key, value)
        elif args.subcommand == "get":
            return self._conan.config_get(args.item)
        elif args.subcommand == "rm":
            return self._conan.config_rm(args.item)
        elif args.subcommand == "install":
            verify_ssl = get_bool_from_text(args.verify_ssl)
            return self._conan.config_install(args.item, verify_ssl)

    def info(self, *args):
        """Gets information about the dependency graph of a recipe.
        You can use it for your current project, by passing a path to a conanfile.py as the
        reference, or for any existing package in your local cache.
        """

        info_only_options = ["id", "build_id", "remote", "url", "license", "requires", "update",
                             "required", "date", "author", "None"]
        path_only_options = ["export_folder", "build_folder", "package_folder", "source_folder"]
        str_path_only_options = ", ".join(['"%s"' % field for field in path_only_options])
        str_only_options = ", ".join(['"%s"' % field for field in info_only_options])

        parser = argparse.ArgumentParser(description=self.info.__doc__, prog="conan info")
        parser.add_argument("reference", help="path to a folder containing a recipe"
                            " (conanfile.py or conanfile.txt) or to a recipe file. e.g., "
                            "./my_project/conanfile.txt. It could also be a reference")
        parser.add_argument("-n", "--only", nargs=1, action=Extender,
                            help='show the specified fields only from: '
                                 '%s or use --paths with options %s. Use --only None to show only '
                                 'references.'
                                 % (str_only_options, str_path_only_options))
        parser.add_argument("--paths", action='store_true', default=False,
                            help='Show package paths in local cache')
        parser.add_argument("--package-filter", nargs='?',
                            help='print information only for packages that match the filter'
                                 'e.g., MyPackage/1.2@user/channel or MyPackage*')
        parser.add_argument("-bo", "--build-order",
                            help='given a modified reference, return an ordered list to build (CI)',
                            nargs=1, action=Extender)
        parser.add_argument("-j", "--json", nargs='?', const="1", type=str,
                            help='Only with --build_order option, return the information in a json.'
                                 ' e.j --json=/path/to/filename.json or --json to output the json')
        parser.add_argument("-g", "--graph", action=OnceArgument,
                            help='Creates file with project dependencies graph. It will generate '
                            'a DOT or HTML file depending on the filename extension')
        parser.add_argument("-if", "--install-folder", action=OnceArgument,
                            help="local folder containing the conaninfo.txt and conanbuildinfo.txt "
                            "files (from a previous conan install execution). Defaulted to "
                            "current folder, unless --profile, -s or -o is specified. If you "
                            "specify both install-folder and any setting/option "
                            "it will raise an error.")
        build_help = 'given a build policy (same install command "build" parameter), return an ' \
                     'ordered list of  ' \
                     'packages that would be built from sources in install command (simulation)'

        _add_common_install_arguments(parser, build_help=build_help)
        args = parser.parse_args(*args)

        if args.install_folder and (args.profile or args.settings or args.options or args.env):
            raise ArgumentError(None,
                                "--install-folder cannot be used together with -s, -o, -e or -pr")

        # BUILD ORDER ONLY
        if args.build_order:
            ret = self._conan.info_build_order(args.reference,
                                               settings=args.settings,
                                               options=args.options,
                                               env=args.env,
                                               profile_name=args.profile,
                                               remote=args.remote,
                                               build_order=args.build_order,
                                               check_updates=args.update,
                                               install_folder=args.install_folder)
            if args.json:
                json_arg = True if args.json == "1" else args.json
                self._outputer.json_build_order(ret, json_arg, os.getcwd())
            else:
                self._outputer.build_order(ret)

        # INSTALL SIMULATION, NODES TO INSTALL
        elif args.build is not None:
            nodes, _ = self._conan.info_nodes_to_build(args.reference,
                                                       build_modes=args.build,
                                                       settings=args.settings,
                                                       options=args.options,
                                                       env=args.env,
                                                       profile_name=args.profile,
                                                       remote=args.remote,
                                                       check_updates=args.update,
                                                       install_folder=args.install_folder)
            self._outputer.nodes_to_build(nodes)

        # INFO ABOUT DEPS OF CURRENT PROJECT OR REFERENCE
        else:
            data = self._conan.info_get_graph(args.reference,
                                              remote=args.remote,
                                              settings=args.settings,
                                              options=args.options,
                                              env=args.env,
                                              profile_name=args.profile,
                                              update=args.update,
                                              install_folder=args.install_folder)
            deps_graph, graph_updates_info, project_reference = data
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
                self._outputer.info_graph(args.graph, deps_graph, project_reference, os.getcwd())
            else:
                self._outputer.info(deps_graph, graph_updates_info, only, args.remote,
                                    args.package_filter, args.paths, project_reference)

    def source(self, *args):
        """ Calls your local conanfile.py 'source()' method.
            I.e., downloads and unzip the package source.
        """
        parser = argparse.ArgumentParser(description=self.source.__doc__, prog="conan source")
        parser.add_argument("path", help=_PATH_HELP)
        parser.add_argument("-sf", "--source-folder", action=OnceArgument,
                            help='Destination directory. Defaulted to current directory')
        parser.add_argument("-if", "--install-folder", action=OnceArgument,
                            help="Optional. Local folder containing the conaninfo.txt and "
                            "conanbuildinfo.txt "
                            "files (from a previous conan install execution). Defaulted to the "
                            "current directory. Optional, source method will run without the "
                            "information retrieved from the conaninfo.txt and conanbuildinfo.txt, "
                            "only required when using conditional source() based on settings, "
                            "options, env_info and user_info ")
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

        return self._conan.source(args.path, args.source_folder, args.install_folder)

    def build(self, *args):
        """ Calls your local conanfile.py 'build()' method.
        The recipe will be built in the local directory specified by --build-folder,
        reading the sources from --source-folder. If you are using a build helper, like CMake(), the
        --package-folder will be configured as destination folder for the install step.
        """

        parser = argparse.ArgumentParser(description=self.build.__doc__, prog="conan build")
        parser.add_argument("path", help=_PATH_HELP)
        parser.add_argument("-sf", "--source-folder", action=OnceArgument,
                            help="local folder containing the sources. Defaulted to the directory "
                                 "of the conanfile. A relative path can also be specified "
                                 "(relative to the current directory)")
        parser.add_argument("-bf", "--build-folder", action=OnceArgument,
                            help="build folder, working directory of the build process. Defaulted "
                                 "to the current directory. A relative path can also be specified "
                                 "(relative to the current directory)")
        parser.add_argument("-pf", "--package-folder", action=OnceArgument,
                            help="folder to install the package (when the build system or build() "
                                 "method does it). Defaulted to the '{build_folder}/package' folder"
                                 ". A relative path can be specified, relative to the current "
                                 " folder. Also an absolute path is allowed.")
        parser.add_argument("-if", "--install-folder", action=OnceArgument,
                            help="Optional. Local folder containing the conaninfo.txt and "
                                 "conanbuildinfo.txt files (from a previous conan install "
                                 "execution). Defaulted to --build-folder")
        args = parser.parse_args(*args)
        return self._conan.build(conanfile_path=args.path,
                                 source_folder=args.source_folder,
                                 package_folder=args.package_folder,
                                 build_folder=args.build_folder,
                                 install_folder=args.install_folder)

    def package(self, *args):
        """ Calls your local conanfile.py 'package()' method.

        This command works locally, in the user space, and it will copy artifacts from the
        --build-folder and --source-folder folder to the --package-folder one.

        It won't create a new package in the local cache, if you want to do it, use 'create' or use
        'export-pkg' after a 'build' command.
        """
        parser = argparse.ArgumentParser(description=self.package.__doc__, prog="conan package")
        parser.add_argument("path", help=_PATH_HELP)
        parser.add_argument("-sf", "--source-folder", action=OnceArgument,
                            help="local folder containing the sources. Defaulted to the directory "
                                 "of the conanfile. A relative path can also be specified "
                                 "(relative to the current directory)")
        parser.add_argument("-bf", "--build-folder", action=OnceArgument,
                            help="build folder, working directory of the build process. Defaulted "
                                 "to the current directory. A relative path can also be specified "
                                 "(relative to the current directory)")
        parser.add_argument("-pf", "--package-folder", action=OnceArgument,
                            help="folder to install the package. Defaulted to the "
                                 "'{build_folder}/package' folder. A relative path can be specified"
                                 " (relative to the current directory). Also an absolute path"
                                 " is allowed.")
        parser.add_argument("-if", "--install-folder", action=OnceArgument,
                            help="Optional. Local folder containing the conaninfo.txt and "
                                 "conanbuildinfo.txt files (from a previous conan install "
                                 "execution). Defaulted to --build-folder ")
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

        return self._conan.package(path=args.path,
                                   build_folder=args.build_folder,
                                   package_folder=args.package_folder,
                                   source_folder=args.source_folder,
                                   install_folder=args.install_folder)

    def imports(self, *args):
        """ Calls your local conanfile.py or conanfile.txt 'imports' method.
        It requires to have been previously installed and have a conanbuildinfo.txt generated file
        in the --install-folder (defaulted to current directory).
        """
        parser = argparse.ArgumentParser(description=self.imports.__doc__, prog="conan imports")
        parser.add_argument("path",
                            help="path to a recipe (conanfile.py). e.g., ./my_project/"
                            "With --undo option, this parameter is the folder "
                            "containing the conan_imports_manifest.txt file generated in a previous"
                            "execution. e.j: conan imports ./imported_files --undo ")
        parser.add_argument("-imf", "--import-folder", action=OnceArgument,
                            help="Directory to copy the artifacts to. By default it will be the"
                                 " current directory")
        parser.add_argument("-if", "--install-folder", action=OnceArgument,
                            help="local folder containing the conaninfo.txt and conanbuildinfo.txt "
                                 "files (from a previous conan install execution)")
        parser.add_argument("-u", "--undo", default=False, action="store_true",
                            help="Undo imports. Remove imported files")
        args = parser.parse_args(*args)

        if args.undo:
            return self._conan.imports_undo(args.path)

        try:
            if "@" in args.path and ConanFileReference.loads(args.path):
                raise ArgumentError(None, "Parameter 'path' cannot be a reference,"
                                          " but a folder containing a conanfile.py or conanfile.txt"
                                          " file.")
        except ConanException:
            pass

        return self._conan.imports(args.path, args.import_folder, args.install_folder)

    def export_pkg(self, *args):
        """Exports a recipe & creates a package with given files calling 'package'.
           It executes the package() method applied to the local folders '--source-folder' and
           '--build-folder' and creates a new package in the local cache for the specified
           'reference' and for the specified '--settings', '--options' and or '--profile'.
        """
        parser = argparse.ArgumentParser(description=self.export_pkg.__doc__,
                                         prog="conan export-pkg .")
        parser.add_argument("path", help=_PATH_HELP)
        parser.add_argument("reference", help='user/channel, or a full package reference'
                                              ' (Pkg/version@user/channel), if name and version '
                                              ' are not declared in the recipe (conanfile.py)')
        parser.add_argument("-sf", "--source-folder", action=OnceArgument,
                            help="local folder containing the sources. Defaulted to the directory "
                                 "of the conanfile. A relative path can also be specified "
                                 "(relative to the current directory)")
        parser.add_argument("-bf", "--build-folder", action=OnceArgument,
                            help="build folder, working directory of the build process. Defaulted "
                                 "to the current directory. A relative path can also be specified "
                                 "(relative to the current directory)")
        parser.add_argument("-if", "--install-folder", action=OnceArgument,
                            help="local folder containing the conaninfo.txt and conanbuildinfo.txt "
                            "files (from a previous conan install execution). Defaulted to "
                            "--build-folder. If these files are found in the specified folder, "
                            "they will be used, then if you specify --profile, -s, -o, --env, "
                            "it will raise an error.")
        parser.add_argument("-pr", "--profile", action=OnceArgument,
                            help='Profile for this package')
        parser.add_argument("-o", "--options",
                            help='Define options values, e.g., -o Pkg:with_qt=true',
                            nargs=1, action=Extender)
        parser.add_argument("-s", "--settings",
                            help='Define settings values, e.g., -s compiler=gcc',
                            nargs=1, action=Extender)
        parser.add_argument("-e", "--env",
                            help='Environment variables that will be set during the package build, '
                                 '-e CXX=/usr/bin/clang++',
                            nargs=1, action=Extender)
        parser.add_argument('-f', '--force', default=False,
                            action='store_true', help='Overwrite existing package if existing')

        args = parser.parse_args(*args)
        name, version, user, channel = get_reference_fields(args.reference)

        return self._conan.export_pkg(conanfile_path=args.path,
                                      name=name,
                                      version=version,
                                      source_folder=args.source_folder,
                                      build_folder=args.build_folder,
                                      install_folder=args.install_folder,
                                      profile_name=args.profile,
                                      env=args.env,
                                      settings=args.settings,
                                      options=args.options,
                                      force=args.force,
                                      user=user,
                                      channel=channel)

    def export(self, *args):
        """ Copies the recipe (conanfile.py & associated files) to your local cache.
        Use the 'reference' param to specify a user and channel where to export.
        Once the recipe is in the local cache it can be shared and reused. It can be uploaded
        to any remote with the "conan upload" command.
        """
        parser = argparse.ArgumentParser(description=self.export.__doc__, prog="conan export")
        parser.add_argument("path", help=_PATH_HELP)
        parser.add_argument("reference", help='user/channel, or a full package reference'
                                              ' (Pkg/version@user/channel), if name and version '
                                              ' are not declared in the recipe (conanfile.py)')
        parser.add_argument('-k', '--keep-source', default=False, action='store_true',
                            help='Optional. Do not remove the source folder in the local cache. '
                                 'Use for testing purposes only')
        args = parser.parse_args(*args)
        name, version, user, channel = get_reference_fields(args.reference)

        return self._conan.export(path=args.path,
                                  name=name, version=version, user=user, channel=channel,
                                  keep_source=args.keep_source)

    def remove(self, *args):
        """Removes packages or binaries matching pattern from local cache or remote.
        It can also be used to remove temporary source or build folders in the local conan cache.
        If no remote is specified, the removal will be done by default in the local conan cache.
        """
        parser = argparse.ArgumentParser(description=self.remove.__doc__, prog="conan remove")
        parser.add_argument('pattern', help='Pattern name, e.g., openssl/*')
        parser.add_argument('-p', '--packages',
                            help='By default, remove all the packages or select one, '
                                 'specifying the package ID',
                            nargs="*", action=Extender)
        parser.add_argument('-b', '--builds',
                            help='By default, remove all the build folders or select one, '
                                 'specifying the package ID',
                            nargs="*", action=Extender)

        parser.add_argument('-s', '--src', default=False, action="store_true",
                            help='Remove source folders')
        parser.add_argument('-f', '--force', default=False,
                            action='store_true', help='Remove without requesting a confirmation')
        parser.add_argument('-r', '--remote', help='Will remove from the specified remote',
                            action=OnceArgument)
        parser.add_argument('-q', '--query', default=None, action=OnceArgument,
                            help='Packages query: "os=Windows AND '
                                 '(arch=x86 OR compiler=gcc)".'
                                 ' The "pattern" parameter '
                                 'has to be a package recipe '
                                 'reference: MyPackage/1.2'
                                 '@user/channel')
        parser.add_argument("-o", "--outdated", help="Remove only outdated from recipe packages",
                            default=False, action="store_true")
        args = parser.parse_args(*args)
        reference = self._check_query_parameter_and_get_reference(args.pattern, args.query)

        if args.packages is not None and args.query:
            raise ConanException("'-q' and '-p' parameters can't be used at the same time")

        if args.builds is not None and args.query:
            raise ConanException("'-q' and '-b' parameters can't be used at the same time")

        return self._conan.remove(pattern=reference or args.pattern, query=args.query,
                                  packages=args.packages, builds=args.builds, src=args.src,
                                  force=args.force, remote=args.remote, outdated=args.outdated)

    def copy(self, *args):
        """ Copies conan recipes and packages to another user/channel.
        Useful to promote packages (e.g. from "beta" to "stable").
        Also for moving packages from one user to another.
        """
        parser = argparse.ArgumentParser(description=self.copy.__doc__, prog="conan copy")
        parser.add_argument("reference", default="",
                            help='package reference. e.g., MyPackage/1.2@user/channel')
        parser.add_argument("user_channel", default="",
                            help='Destination user/channel. '
                            'e.g., lasote/testing')
        parser.add_argument("-p", "--package", nargs=1, action=Extender,
                            help='copy specified package ID')
        parser.add_argument("--all", action='store_true',
                            default=False,
                            help='Copy all packages from the specified package recipe')
        parser.add_argument("--force", action='store_true',
                            default=False,
                            help='Override destination packages and the package recipe')
        args = parser.parse_args(*args)
        if args.all and args.package:
            raise ConanException("Cannot specify both --all and --package")

        return self._conan.copy(reference=args.reference, user_channel=args.user_channel,
                                force=args.force,
                                packages=args.package or args.all)

    def user(self, *parameters):
        """ Authenticates against a remote with user/pass, caching the auth token.
        Useful to avoid the user and password being requested later.
        e.g. while you're uploading a package.
        You can have more than one user (one per remote). Changing the user, or introducing the
        password is only necessary to upload packages to a remote.
        """
        parser = argparse.ArgumentParser(description=self.user.__doc__, prog="conan user")
        parser.add_argument("name", nargs='?', default=None,
                            help='Username you want to use. '
                                 'If no name is provided it will show the current user.')
        parser.add_argument("-r", "--remote", help='look in the specified remote server',
                            action=OnceArgument)
        parser.add_argument('-c', '--clean', default=False,
                            action='store_true', help='Remove user and tokens for all remotes')
        parser.add_argument("-p", "--password", nargs='?', const="", type=str,
                            action=OnceArgument,
                            help='User password. Use double quotes if password with spacing, '
                                 'and escape quotes if existing. If empty, the password is '
                                 'requested interactively (not exposed)')
        args = parser.parse_args(*parameters)  # To enable -h
        return self._conan.user(name=args.name, clean=args.clean, remote=args.remote,
                                password=args.password)

    def search(self, *args):
        """ Searches package recipes and binaries in the local cache or in a remote.

        If you provide a pattern, then it will search for existing package recipes matching that pattern.
        If a full and complete package reference is provided, like Pkg/0.1@user/channel, then the existing
        binary packages for that reference will be displayed.
        You can search in a remote or in the local cache, if nothing is specified, the local conan cache is
        assumed.
        Search is case sensitive, exact case has to be used. For case insensitive file systems, like Windows,
        case sensitive search can be forced with the --case-sensitive argument
        """
        parser = argparse.ArgumentParser(description=self.search.__doc__, prog="conan search")
        parser.add_argument('pattern', nargs='?', help='Pattern name, e.g. openssl/* or package'
                                                       ' recipe reference if "-q" is used. e.g. '
                                                       'MyPackage/1.2@user/channel')
        parser.add_argument('--case-sensitive', default=False,
                            action='store_true', help='Make a case-sensitive search. '
                                                      'Use it to guarantee case-sensitive '
                            'search in Windows or other case-insensitive filesystems')
        parser.add_argument('-r', '--remote', help='Remote origin. `all` searches all remotes', action=OnceArgument)
        parser.add_argument('--raw', default=False, action='store_true',
                            help='Print just the list of recipes')
        parser.add_argument('--table', action=OnceArgument,
                            help='Outputs html file with a table of binaries. Only valid if '
                                 '"pattern" is a package recipe reference')
        parser.add_argument('-q', '--query', default=None, action=OnceArgument,
                            help='Packages query: "os=Windows AND '
                                 '(arch=x86 OR compiler=gcc)".'
                                 ' The "pattern" parameter '
                                 'has to be a package recipe '
                                 'reference: MyPackage/1.2'
                                 '@user/channel'),

        parser.add_argument('-o', '--outdated', default=False, action='store_true',
                            help='Show only outdated from recipe packages')
        args = parser.parse_args(*args)

        try:
            reference = ConanFileReference.loads(args.pattern)
            if "*" in reference:
                # Fixes a version with only a wilcard (valid reference) but not real reference
                # e.j: conan search lib/*@lasote/stable
                reference = None
        except (TypeError, ConanException):
            reference = None

        if reference:
            ret = self._conan.search_packages(reference, query=args.query, remote=args.remote,
                                              outdated=args.outdated)
            ordered_packages, reference, recipe_hash, packages_query = ret
            self._outputer.print_search_packages(ordered_packages, reference, recipe_hash,
                                                 packages_query, args.table)
        else:
            if args.table:
                raise ConanException("'--table' argument can only be used with a "
                                     "reference in the 'pattern' argument")

            refs = self._conan.search_recipes(args.pattern, remote=args.remote,
                                              case_sensitive=args.case_sensitive)
            self._check_query_parameter_and_get_reference(args.pattern, args.query)
            self._outputer.print_search_references(refs, args.pattern, args.raw)

    def upload(self, *args):
        """ Uploads a recipe and binary packages to a remote.

            If you use the --force variable, it won't check the package date. It will override
            the remote with the local package.
            If you use a pattern instead of a conan recipe reference you can use the -c or
            --confirm option to upload all the matching recipes.
            If you use the --retry option you can specify how many times should conan try to upload
            the packages in case of failure. The default is 2.
            With --retry_wait you can specify the seconds to wait between upload attempts.
            If no remote is specified, the first configured remote (by default conan-center, use
            'conan remote list' to list the remotes) will be used.
        """
        parser = argparse.ArgumentParser(description=self.upload.__doc__,
                                         prog="conan upload")
        parser.add_argument('pattern', help='Pattern or package recipe reference, '
                                            'e.g., "openssl/*", "MyPackage/1.2@user/channel"')
        parser.add_argument("-p", "--package", default=None, help='package ID to upload',
                            action=OnceArgument)
        parser.add_argument("-r", "--remote", help='upload to this specific remote',
                            action=OnceArgument)
        parser.add_argument("--all", action='store_true',
                            default=False, help='Upload both package recipe and packages')
        parser.add_argument("--skip-upload", action='store_true',
                            default=False, help='Do not upload anything, just run '
                                                'the checks and the compression.')
        parser.add_argument("--force", action='store_true',
                            default=False,
                            help='Do not check conan recipe date, override remote with local')
        parser.add_argument("--check", action='store_true',
                            default=False,
                            help='Perform an integrity check, using the manifests, before upload')
        parser.add_argument('-c', '--confirm', default=False,
                            action='store_true',
                            help='If pattern is given upload all matching recipes without '
                                 'confirmation')
        parser.add_argument('--retry', default=2, type=int,
                            help='In case of fail retries to upload again the specified times',
                            action=OnceArgument)
        parser.add_argument('--retry-wait', default=5, type=int,
                            help='Waits specified seconds before retry again',
                            action=OnceArgument)

        args = parser.parse_args(*args)
        return self._conan.upload(pattern=args.pattern, package=args.package, remote=args.remote,
                                  all_packages=args.all,
                                  force=args.force, confirm=args.confirm, retry=args.retry,
                                  retry_wait=args.retry_wait,
                                  skip_upload=args.skip_upload, integrity_check=args.check)

    def remote(self, *args):
        """ Manages the remote list and the package recipes associated to a remote.
        """
        parser = argparse.ArgumentParser(description=self.remote.__doc__, prog="conan remote")
        subparsers = parser.add_subparsers(dest='subcommand', help='sub-command help')

        # create the parser for the "a" command
        subparsers.add_parser('list', help='list current remotes')
        parser_add = subparsers.add_parser('add', help='add a remote')
        parser_add.add_argument('remote', help='name of the remote')
        parser_add.add_argument('url', help='url of the remote')
        parser_add.add_argument('verify_ssl',
                                help='Verify SSL certificated. Default True',
                                default="True", nargs="?")
        parser_add.add_argument("-i", "--insert", nargs="?", const=0, type=int,
                                help="insert remote at specific index", action=OnceArgument)
        parser_rm = subparsers.add_parser('remove', help='remove a remote')
        parser_rm.add_argument('remote', help='name of the remote')
        parser_upd = subparsers.add_parser('update', help='update the remote url')
        parser_upd.add_argument('remote', help='name of the remote')
        parser_upd.add_argument('url', help='url')
        parser_upd.add_argument('verify_ssl',
                                help='Verify SSL certificated. Default True',
                                default="True", nargs="?")
        parser_upd.add_argument("-i", "--insert", nargs="?", const=0, type=int,
                                help="insert remote at specific index",
                                action=OnceArgument)

        subparsers.add_parser('list_ref',
                              help='list the package recipes and its associated remotes')
        parser_padd = subparsers.add_parser('add_ref',
                                            help="associate a recipe's reference to a remote")
        parser_padd.add_argument('reference', help='package recipe reference')
        parser_padd.add_argument('remote', help='name of the remote')
        parser_prm = subparsers.add_parser('remove_ref',
                                           help="dissociate a recipe's reference and its remote")
        parser_prm.add_argument('reference', help='package recipe reference')
        parser_pupd = subparsers.add_parser('update_ref', help="update the remote associated "
                                            "with a package recipe")
        parser_pupd.add_argument('reference', help='package recipe reference')
        parser_pupd.add_argument('remote', help='name of the remote')
        args = parser.parse_args(*args)

        reference = args.reference if hasattr(args, 'reference') else None

        verify_ssl = get_bool_from_text(args.verify_ssl) if hasattr(args, 'verify_ssl') else False

        remote = args.remote if hasattr(args, 'remote') else None
        url = args.url if hasattr(args, 'url') else None

        if args.subcommand == "list":
            remotes = self._conan.remote_list()
            self._outputer.remote_list(remotes)
        elif args.subcommand == "add":
            return self._conan.remote_add(remote, url, verify_ssl, args.insert)
        elif args.subcommand == "remove":
            return self._conan.remote_remove(remote)
        elif args.subcommand == "update":
            return self._conan.remote_update(remote, url, verify_ssl, args.insert)
        elif args.subcommand == "list_ref":
            refs = self._conan.remote_list_ref()
            self._outputer.remote_ref_list(refs)
        elif args.subcommand == "add_ref":
            return self._conan.remote_add_ref(reference, remote)
        elif args.subcommand == "remove_ref":
            return self._conan.remote_remove_ref(reference)
        elif args.subcommand == "update_ref":
            return self._conan.remote_update_ref(reference, remote)

    def profile(self, *args):
        """ Lists profiles in the '.conan/profiles' folder, or shows profile details.
        The 'list' subcommand will always use the default user 'conan/profiles' folder. But the
        'show' subcommand is able to resolve absolute and relative paths, as well as to map names to
        '.conan/profiles' folder, in the same way as the '--profile' install argument.
        """
        parser = argparse.ArgumentParser(description=self.profile.__doc__, prog="conan profile")
        subparsers = parser.add_subparsers(dest='subcommand')

        # create the parser for the "profile" command
        subparsers.add_parser('list', help='List current profiles')
        parser_show = subparsers.add_parser('show', help='Show the values defined for a profile')
        parser_show.add_argument('profile',  help="name of the profile in the '.conan/profiles' "
                                                  "folder or path to a profile file")

        parser_new = subparsers.add_parser('new', help='Creates a new empty profile')
        parser_new.add_argument('profile',  help="name for the profile in the '.conan/profiles' "
                                                 "folder or path and name for a profile file")
        parser_new.add_argument("--detect", action='store_true',
                                default=False,
                                help='Autodetect settings and fill [settings] section')

        parser_update = subparsers.add_parser('update', help='Update a profile with desired value')
        parser_update.add_argument('item', help='key="value to set", e.j: settings.compiler=gcc')
        parser_update.add_argument('profile',  help="name of the profile in the '.conan/profiles' "
                                                    "folder or path to a profile file")

        parser_get = subparsers.add_parser('get', help='Get a profile key')
        parser_get.add_argument('item', help='key of the value to get, e.g: settings.compiler')
        parser_get.add_argument('profile',  help="name of the profile in the '.conan/profiles' "
                                                 "folder or path to a profile file")

        parser_remove = subparsers.add_parser('remove', help='Remove a profile key')
        parser_remove.add_argument('item', help='key, e.g: settings.compiler')
        parser_remove.add_argument('profile',  help="name of the profile in the '.conan/profiles' "
                                                    "folder or path to a profile file")

        args = parser.parse_args(*args)

        profile = args.profile if hasattr(args, 'profile') else None

        if args.subcommand == "list":
            profiles = self._conan.profile_list()
            self._outputer.profile_list(profiles)
        elif args.subcommand == "show":
            profile_text = self._conan.read_profile(profile)
            self._outputer.print_profile(profile, profile_text)
        elif args.subcommand == "new":
            self._conan.create_profile(profile, args.detect)
        elif args.subcommand == "update":
            try:
                key, value = args.item.split("=", 1)
            except ValueError:
                raise ConanException("Please specify key=value")
            self._conan.update_profile(profile, key, value)
        elif args.subcommand == "get":
            key = args.item
            self._outputer.writeln(self._conan.get_profile_key(profile, key))
        elif args.subcommand == "remove":
            self._conan.delete_profile_key(profile, args.item)

    def get(self, *args):
        """ Gets a file or list a directory of a given reference or package.
        """
        parser = argparse.ArgumentParser(description=self.get.__doc__,
                                         prog="conan get")
        parser.add_argument('reference', help='package recipe reference')
        parser.add_argument('path',
                            help='Path to the file or directory. If not specified will get the '
                                 'conanfile if only a reference is specified and a conaninfo.txt '
                                 'file contents if the package is also specified',
                            default=None, nargs="?")
        parser.add_argument("-p", "--package", default=None, help='package ID',
                            action=OnceArgument)
        parser.add_argument("-r", "--remote", help='Get from this specific remote',
                            action=OnceArgument)
        parser.add_argument("-raw", "--raw", help='Do not decorate the text', default=False,
                            action='store_true')
        args = parser.parse_args(*args)

        ret, path = self._conan.get_path(args.reference, args.package, args.path, args.remote)
        if isinstance(ret, list):
            self._outputer.print_dir_list(ret, path, args.raw)
        else:
            self._outputer.print_file_contents(ret, path, args.raw)

        return

    def alias(self, *args):
        """Creates and exports an 'alias package recipe'. An "alias" package is a
        symbolic name (reference) for another package (target). When some
        package depends on an alias, the target one will be retrieved and used
        instead, so the alias reference, the symbolic name, does not appear
        in the final dependency graph.
        """
        parser = argparse.ArgumentParser(description=self.alias.__doc__,
                                         prog="conan alias")
        parser.add_argument('reference', help='Alias reference. e.j: mylib/1.X@user/channel')
        parser.add_argument('target', help='Target reference. e.j: mylib/1.12@user/channel')
        args = parser.parse_args(*args)

        self._conan.export_alias(args.reference, args.target)

    def _show_help(self):
        """ prints a summary of all commands
        """
        grps = [("Consumer commands", ("install", "config", "get", "info", "search")),
                ("Creator commands", ("new", "create", "upload", "export", "export-pkg", "test")),
                ("Package development commands", ("source", "build", "package")),
                ("Misc commands", ("profile", "remote", "user", "imports", "copy", "remove",
                                   "alias", "download", "help"))]

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
            self._user_io.out.writeln(group_name, Color.BRIGHT_MAGENTA)
            for name in comm_names:
                # future-proof way to ensure tabular formatting
                self._user_io.out.write(fmt % name, Color.GREEN)
                self._user_io.out.writeln(commands[name].__doc__.split('\n', 1)[0].strip())

        self._user_io.out.writeln("")
        self._user_io.out.writeln('Conan commands. Type "conan <command> -h" for help',
                                  Color.BRIGHT_YELLOW)

    def _commands(self):
        """ returns a list of available commands
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

    @staticmethod
    def _check_query_parameter_and_get_reference(pattern, query):
        reference = None
        if pattern:
            try:
                reference = ConanFileReference.loads(pattern)
            except ConanException:
                if query is not None:
                    raise ConanException("-q parameter only allowed with a valid recipe "
                                         "reference as search pattern. e.g conan search "
                                         "MyPackage/1.2@user/channel -q \"os=Windows\"")
        return reference

    def run(self, *args):
        """HIDDEN: entry point for executing commands, dispatcher to class
        methods
        """
        errors = False
        try:
            try:
                command = args[0][0]
                commands = self._commands()
                method = commands[command]
            except KeyError as exc:
                if command in ["-v", "--version"]:
                    self._user_io.out.success("Conan version %s" % client_version)
                    return False
                self._show_help()
                if command in ["-h", "--help"]:
                    return False
                raise ConanException("Unknown command %s" % str(exc))
            except IndexError:  # No parameters
                self._show_help()
                return False
            method(args[0][1:])
        except KeyboardInterrupt as exc:
            logger.error(exc)
            errors = True
        except SystemExit as exc:
            if exc.code != 0:
                logger.error(exc)
                self._user_io.out.error("Exiting with code: %d" % exc.code)
            errors = exc.code
        except ConanException as exc:
            errors = True
            msg = exception_message_safe(exc)
            self._user_io.out.error(msg)
        except Exception as exc:
            import traceback
            print(traceback.format_exc())
            errors = True
            msg = exception_message_safe(exc)
            self._user_io.out.error(msg)

        return errors


def get_reference_fields(arg_reference):
    """
    :param arg_reference: String with a complete reference, or only user/channel
    :return: name, version, user and channel, in a tuple
    """

    if not arg_reference:
        return None, None, None, None

    try:
        name_version, user_channel = arg_reference.split("@")
        name, version = name_version.split("/")
        user, channel = user_channel.split("/")
    except ValueError:
        name, version = None, None
        try:
            user, channel = arg_reference.split("/")
        except ValueError:
            raise ConanException("Invalid parameter '%s', specify the full reference or "
                                 "user/channel" % arg_reference)

    return name, version, user, channel


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


def _add_common_install_arguments(parser, build_help):
    parser.add_argument("-u", "--update", action='store_true', default=False,
                        help="check updates exist from upstream remotes")
    parser.add_argument("-pr", "--profile", default=None, action=OnceArgument,
                        help='Apply the specified profile to the install command')
    parser.add_argument("-r", "--remote", help='look in the specified remote server',
                        action=OnceArgument)
    parser.add_argument("-o", "--options",
                        help='Define options values, e.g., -o Pkg:with_qt=true',
                        nargs=1, action=Extender)
    parser.add_argument("-s", "--settings",
                        help='Settings to build the package, overwriting the defaults. e.g., '
                             '-s compiler=gcc',
                        nargs=1, action=Extender)
    parser.add_argument("-e", "--env",
                        help='Environment variables that will be set during the package build, '
                             '-e CXX=/usr/bin/clang++',
                        nargs=1, action=Extender)
    if build_help:
        parser.add_argument("-b", "--build", action=Extender, nargs="*", help=build_help)


_help_build_policies = '''Optional, use it to choose if you want to build from sources:

    --build            Build all from sources, do not use binary packages.
    --build=never      Never build, use binary packages or fail if a binary package is not found.
    --build=missing    Build from code if a binary package is not found.
    --build=outdated   Build from code if the binary is not built with the current recipe or
                       when missing binary package.
    --build=[pattern]  Build always these packages from source, but never build the others.
                       Allows multiple --build parameters. 'pattern' is a fnmatch file pattern
                       of a package name.

    Default behavior: If you don't specify anything, it will be similar to --build=never, but
    package recipes can override it and decide to build with "build_policy"
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
    """
    try:
        conan_api, client_cache, user_io = Conan.factory()
    except ConanException:  # Error migrating
        sys.exit(2)

    outputer = CommandOutputer(user_io, client_cache)
    command = Command(conan_api, client_cache, user_io, outputer)
    current_dir = os.getcwd()
    try:
        import signal

        def ctrl_c_handler(_, __):
            print('You pressed Ctrl+C!')
            sys.exit(3)

        def ctrl_break_handler(_, __):
            print('You pressed Ctrl+Break!')
            sys.exit(4)

        signal.signal(signal.SIGINT, ctrl_c_handler)
        if sys.platform == 'win32':
            signal.signal(signal.SIGBREAK, ctrl_break_handler)
        error = command.run(args)
    finally:
        os.chdir(current_dir)
    sys.exit(error)
