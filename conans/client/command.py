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
from conans.paths import CONANFILE
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
        parser.add_argument("-c", "--pure-c", "--pure_c", action='store_true', default=False,
                            help='Create a C language package only package, '
                                 'deleting "self.settings.compiler.libcxx" setting '
                                 'in the configure method')
        parser.add_argument("-s", "--sources", action='store_true', default=False,
                            help='Create a package with embedded sources in "src" folder, '
                                 'using "exports_sources" instead of retrieving external code with '
                                 'the "source()" method')
        parser.add_argument("-b", "--bare", action='store_true', default=False,
                            help='Create the minimum package recipe, without build() or package()'
                            'methods. Useful in combination with "package_files" command')
        parser.add_argument("-cis", "--ci-shared", "--ci_shared", action='store_true',
                            default=False,
                            help='Package will have a "shared" option to be used in CI')
        parser.add_argument("-cilg", "--ci-travis-gcc", "--ci_travis_gcc", action='store_true',
                            default=False,
                            help='Generate travis-ci files for linux gcc')
        parser.add_argument("-cilc", "--ci-travis-clang", "--ci_travis_clang", action='store_true',
                            default=False,
                            help='Generate travis-ci files for linux clang')
        parser.add_argument("-cio", "--ci-travis-osx", "--ci_travis_osx", action='store_true',
                            default=False,
                            help='Generate travis-ci files for OSX apple-clang')
        parser.add_argument("-ciw", "--ci-appveyor-win", "--ci_appveyor_win", action='store_true',
                            default=False, help='Generate appveyor files for Appveyor '
                                                'Visual Studio')
        parser.add_argument("-ciglg", "--ci-gitlab-gcc", "--ci_gitlab_gcc", action='store_true',
                            default=False,
                            help='Generate GitLab files for linux gcc')
        parser.add_argument("-ciglc", "--ci-gitlab-clang", "--ci_gitlab_clang", action='store_true',
                            default=False,
                            help='Generate GitLab files for linux clang')
        parser.add_argument("-gi", "--gitignore", action='store_true', default=False,
                            help='Generate a .gitignore with the known patterns to excluded')
        parser.add_argument("-ciu", "--ci-upload-url", "--ci_upload_url",
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
        """ Runs a test_folder/conanfile.py to test an existing package.
        The package to be tested must exist in the local cache or any configured remote.
        To create and test a binary package for a local directory conanfile.py use the
        'conan create' command.
        """
        parser = argparse.ArgumentParser(description=self.test.__doc__, prog="conan test")
        parser.add_argument("reference", nargs="?",
                            help='a full package reference pkg/version@user/channel, '
                            'or just the package name "pkg" if the test_package conanfile is '
                            'requiring more than one reference')
        parser.add_argument('--path', '-p', default=None,
                            help='Optional. Folder with a test_folder directory. '
                                 'Default current directory.')
        parser.add_argument("-tf", "--test-folder", "--test_folder",
                            help='alternative test folder name, by default is "test_package"')

        _add_common_install_arguments(parser, build_help=_help_build_policies)

        args = parser.parse_args(*args)

        if not args.reference:
            name = version = user = channel = None
        else:
            try:
                name, version, user, channel = ConanFileReference.loads(args.reference)
            except ConanException:
                if "@" not in args.reference:
                    if "/" in args.reference:
                        raise ConanException("Specify the full reference or only a package name "
                                             "without version (if the test_package/conanfile.py "
                                             "is requiring the reference to be tested")
                    else:
                        name = args.reference
                        version = None
                        channel = None
                        user = None
                else:
                    raise ConanException("Invalid refernce: %s" % args.reference)

        return self._conan.test(args.profile, args.settings, args.options,
                                args.env, args.path, args.test_folder,
                                args.remote, args.update,
                                user=user, channel=channel, name=name,
                                version=version, build_modes=args.build)

    def test_package(self, *args):
        """THIS METHOD IS DEPRECATED and will be removed.
        Use 'conan create' to generate binary packages for a recipe.
        If you want to test a package you can use 'conan test' command.
        """

        parser = argparse.ArgumentParser(description=self.test_package.__doc__,
                                         prog="conan test_package")
        parser.add_argument("reference", nargs="?",
                            help='a full package reference Pkg/version@user/channel, '
                            'or just the user/channel if package and version are defined in recipe')
        parser.add_argument("-ne", "--not-export", default=False, action='store_true',
                            help='Do not export the conanfile before test execution')
        parser.add_argument("-tf", "--test-folder", "--test_folder",
                            help='alternative test folder name, by default is "test_package"')
        parser.add_argument('--keep-source', '-k', default=False, action='store_true',
                            help='Optional. Do not remove the source folder in local cache. '
                                 'Use for testing purposes only')
        parser.add_argument('--test-only', '-t', default=False, action='store_true',
                            help='Just run the test, without exporting or building the package')
        parser.add_argument("--cwd", "-c", help='Use this directory as the current directory')

        _add_manifests_arguments(parser)
        _add_common_install_arguments(parser, build_help=_help_build_policies)

        args = parser.parse_args(*args)

        name, version, user, channel = get_reference_fields(args.reference)

        if args.test_only:
            args.build = ["never"]
            args.not_export = True
            args.keep_source = True

        return self._conan.test_package(args.profile, args.settings, args.options,
                                        args.env, args.scope, args.test_folder, args.not_export,
                                        args.build, args.keep_source, args.verify, args.manifests,
                                        args.manifests_interactive, args.remote, args.update,
                                        cwd=args.cwd, user=user, channel=channel, name=name,
                                        version=version)

    def create(self, *args):
        """ Creates a binary package for the recipe (conanfile.py) located in the current directory.
        Uses the specified configuration in a profile or in -s settings, -o options etc.
        If a 'test_package' folder (the name can be configured with -tf) is found, the command will
        run the consumer project to ensure that the package has been created correctly. Check the
        'conan test' command to know more about the 'test_folder' project.
        """
        parser = argparse.ArgumentParser(description=self.create.__doc__,
                                         prog="conan create")
        parser.add_argument("reference", help='user/channel, or a full package reference'
                                              ' (Pkg/version@user/channel), if name and version '
                                              ' are not declared in the recipe')
        parser.add_argument('--cwd', '-c', default=None,
                            help='Optional. Folder with a %s. Default current directory.'
                            % CONANFILE)
        parser.add_argument("--file", "-f", help="specify conanfile filename")

        parser.add_argument("-ne", "--not-export", default=False, action='store_true',
                            help='Do not export the conanfile')
        parser.add_argument("-tf", "--test-folder", "--test_folder",
                            help='alternative test folder name, by default is "test_package"')
        parser.add_argument('--keep-source', '-k', default=False, action='store_true',
                            help='Optional. Do not remove the source folder in local cache. '
                                 'Use for testing purposes only')

        _add_manifests_arguments(parser)
        _add_common_install_arguments(parser, build_help=_help_build_policies)

        args = parser.parse_args(*args)

        name, version, user, channel = get_reference_fields(args.reference)

        return self._conan.create(args.profile, args.settings, args.options,
                                  args.env, args.scope, args.test_folder, args.not_export,
                                  args.build, args.keep_source, args.verify, args.manifests,
                                  args.manifests_interactive, args.remote, args.update,
                                  conan_file_path=args.cwd, name=name, version=version, user=user,
                                  channel=channel, filename=args.file)

    def download(self, *args):
        """Downloads a conan package to the local cache without using settings by specifying the
        package ID to be installed. Not transitive, requirements of the specified reference
        wont be retrieved. Useful together with 'conan copy' to automate the promotion of packages
        to a different user/channel. If only a reference is specified, it will download all packages
        in the specified remote. If no remote is specified will search sequentially in the available
        configured remotes."""

        parser = argparse.ArgumentParser(description=self.download.__doc__, prog="conan download")
        parser.add_argument("reference",
                            help='package recipe reference e.g., MyPackage/1.2@user/channel')
        parser.add_argument("--package", "-p", nargs=1, action=Extender,
                            help='Force install specified package ID (ignore settings/options)')
        parser.add_argument("-r", "--remote", help='look in the specified remote server')

        args = parser.parse_args(*args)
        reference = ConanFileReference.loads(args.reference)

        return self._conan.download(reference=reference, package=args.package, remote=args.remote)

    def install(self, *args):
        """Installs the requirements specified in a 'conanfile.py' or 'conanfile.txt'.
           If any requirement is not found in the local cache it will retrieve the recipe from a
           remote, looking for it sequentially in the available configured remotes.
           When the recipes have been downloaded it will try to download a binary package matching
           the specified settings, only from the remote from which the recipe was retrieved.
           If no binary package is found you can build the package from sources using the '--build'
           option.
           It can also be used to install a concrete recipe/package specifying a reference in the
           "path" parameter.
        """
        parser = argparse.ArgumentParser(description=self.install.__doc__, prog="conan install")
        parser.add_argument("path", nargs='?', default="",
                            help='path to a recipe (conanfile.py). e.g., ./my_project/')
        parser.add_argument("--file", "-f", help="specify conanfile filename")
        parser.add_argument("--generator", "-g", nargs=1, action=Extender,
                            help='Generators to use')
        parser.add_argument("--werror", action='store_true', default=False,
                            help='Error instead of warnings for graph inconsistencies')
        parser.add_argument("--build-folder", "--build_folder", "-c",
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
                                       env=args.env, scope=args.scope,
                                       remote=args.remote, werror=args.werror,
                                       verify=args.verify, manifests=args.manifests,
                                       manifests_interactive=args.manifests_interactive,
                                       build=args.build, profile_name=args.profile,
                                       update=args.update, generators=args.generator,
                                       no_imports=args.no_imports, filename=args.file,
                                       build_folder=args.build_folder)
        else:
            return self._conan.install_reference(reference, settings=args.settings,
                                                 options=args.options,
                                                 env=args.env, scope=args.scope,
                                                 remote=args.remote, werror=args.werror,
                                                 verify=args.verify, manifests=args.manifests,
                                                 manifests_interactive=args.manifests_interactive,
                                                 build=args.build, profile_name=args.profile,
                                                 update=args.update,
                                                 generators=args.generator,
                                                 build_folder=args.build_folder)

    def config(self, *args):
        """Manages conan configuration information
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
        args = parser.parse_args(*args)

        if args.subcommand == "set":
            try:
                key, value = args.item.split("=", 1)
            except:
                raise ConanException("Please specify key=value")
            return self._conan.config_set(key, value)
        elif args.subcommand == "get":
            return self._conan.config_get(args.item)
        elif args.subcommand == "rm":
            return self._conan.config_rm(args.item)
        elif args.subcommand == "install":
            return self._conan.config_install(args.item)

    def info(self, *args):
        """Prints information about a package recipe's dependency graph.
        You can use it for your current project (just point to the path of your conanfile
        if you want), or for any existing package in your local cache.
        """

        info_only_options = ["id", "build_id", "remote", "url", "license", "requires", "update",
                             "required", "date", "author", "None"]
        path_only_options = ["export_folder", "build_folder", "package_folder", "source_folder"]
        str_path_only_options = ", ".join(['"%s"' % field for field in path_only_options])
        str_only_options = ", ".join(['"%s"' % field for field in info_only_options])

        parser = argparse.ArgumentParser(description=self.info.__doc__, prog="conan info")
        parser.add_argument("reference", nargs='?', default="",
                            help='reference name or path to conanfile file, '
                            'e.g., MyPackage/1.2@user/channel or ./my_project/')
        parser.add_argument("--file", "-f", help="specify conanfile filename")
        parser.add_argument("--only", "-n", nargs=1, action=Extender,
                            help='show the specified fields only from: '
                                 '%s or use --paths with options %s. Use --only None to show only '
                                 'references.'
                                 % (str_only_options, str_path_only_options))
        parser.add_argument("--paths", action='store_true', default=False,
                            help='Show package paths in local cache')
        parser.add_argument("--package-filter", "--package_filter", nargs='?',
                            help='print information only for packages that match the filter'
                                 'e.g., MyPackage/1.2@user/channel or MyPackage*')
        parser.add_argument("--build-order", "--build_order", "-bo",
                            help='given a modified reference, return an ordered list to build (CI)',
                            nargs=1, action=Extender)
        parser.add_argument("--json", "-j", nargs='?', const="1", type=str,
                            help='Only with --build_order option, return the information in a json.'
                                 ' e.j --json=/path/to/filename.json or --json to output the json')
        parser.add_argument("--graph", "-g",
                            help='Creates file with project dependencies graph. It will generate '
                            'a DOT or HTML file depending on the filename extension')
        parser.add_argument("--build-folder", "--build_folder",
                            help='Use this directory as the directory where to put the generator'
                                 'files, conaninfo/conanbuildinfo.txt etc.')
        build_help = 'given a build policy (same install command "build" parameter), return an ' \
                     'ordered list of  ' \
                     'packages that would be built from sources in install command (simulation)'

        _add_common_install_arguments(parser, build_help=build_help)
        args = parser.parse_args(*args)

        # BUILD ORDER ONLY
        if args.build_order:
            ret = self._conan.info_build_order(args.reference, settings=args.settings,
                                               options=args.options,
                                               env=args.env, scope=args.scope,
                                               profile_name=args.profile,
                                               filename=args.file, remote=args.remote,
                                               build_order=args.build_order,
                                               check_updates=args.update,
                                               build_folder=args.build_folder)
            if args.json:
                json_arg = True if args.json == "1" else args.json
                self._outputer.json_build_order(ret, json_arg, args.build_folder)
            else:
                self._outputer.build_order(ret)

        # INSTALL SIMULATION, NODES TO INSTALL
        elif args.build is not None:
            nodes, _ = self._conan.info_nodes_to_build(args.reference, build_modes=args.build,
                                                       settings=args.settings,
                                                       options=args.options, env=args.env,
                                                       scope=args.scope,
                                                       profile_name=args.profile,
                                                       filename=args.file,
                                                       remote=args.remote,
                                                       check_updates=args.update,
                                                       build_folder=args.build_folder)
            self._outputer.nodes_to_build(nodes)
        # INFO ABOUT DEPS OF CURRENT PROJECT OR REFERENCE
        else:
            data = self._conan.info_get_graph(args.reference, remote=args.remote,
                                              settings=args.settings,
                                              options=args.options, env=args.env, scope=args.scope,
                                              profile_name=args.profile, update=args.update,
                                              filename=args.file, build_folder=args.build_folder)
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
                self._outputer.info_graph(args.graph, deps_graph, project_reference,
                                          args.build_folder)
            else:
                self._outputer.info(deps_graph, graph_updates_info, only, args.remote,
                                    args.package_filter, args.paths, project_reference)
        return

    def source(self, *args):
        """ Calls your local conanfile.py 'source()' method to configure the source directory.
            I.e., downloads and unzip the package source.
        """
        parser = argparse.ArgumentParser(description=self.source.__doc__, prog="conan source")
        parser.add_argument("path", help='path to a recipe (conanfile.py), e.g., conan source .')

        parser.add_argument("--source-folder", "--source_folder", "-s",
                            help='Destination directory. Defaulted to current directory')
        parser.add_argument("--install-folder", "-if",
                            help="local folder containing the conaninfo.txt and conanbuildinfo.txt "
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
        """ Utility command to call the build() method of a local 'conanfile.py'.
        The recipe will be built in the local directory specified by --build_folder,
        reading the sources from --source_folder. If you are using a build helper, like CMake(), the
        --package_folder will be configured as destination folder for the install step.
        """

        parser = argparse.ArgumentParser(description=self.build.__doc__, prog="conan build")
        parser.add_argument("path", help='path to a recipe (conanfile.py), e.g., conan build .')
        parser.add_argument("--file", "-f", help="specify conanfile filename")
        parser.add_argument("--source-folder", "--source_folder", "-sf",
                            help="local folder containing the sources. Defaulted to the directory "
                                 "of the conanfile. A relative path can also be specified "
                                 "(relative to the current directory)")
        parser.add_argument("--build-folder", "--build_folder", "-bf",
                            help="build folder, working directory of the build process. Defaulted "
                                 "to the current directory. A relative path can also be specified "
                                 "(relative to the current directory)")
        parser.add_argument("--package-folder", "--package_folder", "-pf",
                            help="folder to install the package (when the build system or build() "
                                 "method does it). Defaulted to the '{build_folder}/package' folder"
                                 ". A relative path can be specified (relative to the build_folder "
                                 "directory). Also an absolute path is allowed.")
        args = parser.parse_args(*args)
        return self._conan.build(path=args.path, source_folder=args.source_folder,
                                 package_folder=args.package_folder, filename=args.file,
                                 build_folder=args.build_folder)

    def package(self, *args):
        """ Calls your conanfile.py 'package' method of a local conanfile.py
        It won't create a new package, use 'create' instead for creating packages in the conan
        local cache, or 'build' for building in the user space.

        This command works locally, in the user space, and it will copy artifacts from the
        provided folder to the current one.
        """
        parser = argparse.ArgumentParser(description=self.package.__doc__, prog="conan package")
        parser.add_argument("path", help='path to a recipe (conanfile.py), e.g., conan package .')
        parser.add_argument("--source-folder", "--source_folder", "-sf",
                            help="local folder containing the sources. Defaulted to the directory "
                                 "of the conanfile. A relative path can also be specified "
                                 "(relative to the current directory)")
        parser.add_argument("--build-folder", "--build_folder", "-bf",
                            help="build folder, working directory of the build process. Defaulted "
                                 "to the current directory. A relative path can also be specified "
                                 "(relative to the current directory)")
        parser.add_argument("--package-folder", "--package_folder", "-pf",
                            help="folder to install the package. Defaulted to the "
                                 "'{build_folder}/package' folder. A relative path can be specified"
                                 " (relative to the build_folder directory). Also an absolute path"
                                 "is allowed.")

        args = parser.parse_args(*args)
        try:
            if "@" in args.path and ConanFileReference.loads(args.path):
                raise ArgumentError(None,
                                    "'conan package' doesn't accept a reference anymore. "
                                    " The path parameter should be a folder containing a "
                                    "conanfile.py file. If you were using the 'conan package' "
                                    "command for development purposes we recommend to use "
                                    "the local development commands: 'conan build' + "
                                    "'conan package' and finally 'conan create' to regenerate the "
                                    "package, or 'conan export_package' to store the already built "
                                    "binaries in the local cache without rebuilding them.")
        except ConanException:
            pass

        return self._conan.package(path=args.path, build_folder=args.build_folder,
                                   source_folder=args.source_folder,
                                   package_folder=args.package_folder)

    def imports(self, *args):
        """ Execute the 'imports' stage of a conanfile.txt or a conanfile.py.
        It requires to have been previously installed and have a conanbuildinfo.txt generated file.
        """
        parser = argparse.ArgumentParser(description=self.imports.__doc__, prog="conan imports")
        parser.add_argument("path",
                            help="path to a recipe (conanfile.py). e.g., ./my_project/"
                            "With --undo option, this parameter is the folder "
                            "containing the conan_imports_manifest.txt file generated in a previous"
                            "execution. e.j: conan imports ./imported_files --undo ")
        parser.add_argument("--file", "-f", help="Use another filename, "
                            "e.g.: conan imports -f=conanfile2.py")
        parser.add_argument("-d", "--dest",
                            help="Directory to copy the artifacts to. By default it will be the"
                                 " current directory")
        parser.add_argument("--install-folder", "-if",
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

        return self._conan.imports(args.path, args.dest, args.file, args.install_folder)

    def export_pkg(self, *args):
        """Exports the specified recipe and then creates a package binary from given precompiled
           artifacts in user folder, skipping the build() method of the recipe, by calling the
           package() method to extract the artifacts from the local "--source_folder" and
           "--build_folder".
        """
        parser = argparse.ArgumentParser(description=self.export_pkg.__doc__,
                                         prog="conan export-pkg .")
        parser.add_argument("path", help='path to a recipe (conanfile.py). e.j: "." ')
        parser.add_argument("reference", help='user/channel, or a full package reference'
                                              ' (Pkg/version@user/channel), if name and version '
                                              ' are not declared in the recipe (conanfile.py)')
        parser.add_argument("--source-folder", "--source_folder", "-sf",
                            help="local folder containing the sources. Defaulted to the directory "
                                 "of the conanfile. A relative path can also be specified "
                                 "(relative to the current directory)")
        parser.add_argument("--build-folder", "--build_folder", "-bf",
                            help="build folder, working directory of the build process. Defaulted "
                                 "to the current directory. A relative path can also be specified "
                                 "(relative to the current directory)")
        parser.add_argument("--profile", "-pr",
                            help='Profile for this package')
        parser.add_argument("--options", "-o",
                            help='Options for this package. e.g., -o with_qt=true',
                            nargs=1, action=Extender)
        parser.add_argument("--settings", "-s",
                            help='Settings for this package e.g., -s compiler=gcc',
                            nargs=1, action=Extender)
        parser.add_argument("--env", "-e",
                            help='Environment variables that will be set during the package build, '
                                 '-e CXX=/usr/bin/clang++',
                            nargs=1, action=Extender)
        parser.add_argument('-f', '--force', default=False,
                            action='store_true', help='Overwrite existing package if existing')
        parser.add_argument('--no-export', '-ne', help='Do not export the recipe', default=False,
                            action='store_true')

        args = parser.parse_args(*args)
        name, version, user, channel = get_reference_fields(args.reference)

        return self._conan.export_pkg(path=args.path,
                                      name=name,
                                      version=version,
                                      source_folder=args.source_folder,
                                      build_folder=args.build_folder,
                                      profile_name=args.profile,
                                      env=args.env,
                                      settings=args.settings,
                                      options=args.options,
                                      force=args.force,
                                      no_export=args.no_export,
                                      user=user,
                                      channel=channel)

    def export(self, *args):
        """ Copies the package recipe (conanfile.py and associated files) to your local cache.
        From the local cache it can be shared and reused in other projects.
        Also, from the local cache, it can be uploaded to any remote with the "upload" command.
        """
        parser = argparse.ArgumentParser(description=self.export.__doc__, prog="conan export")
        parser.add_argument("reference", help='user/channel, or a full package reference'
                                              ' (Pkg/version@user/channel), if name and version '
                                              ' are not declared in the recipe')
        parser.add_argument('--path', '-p', default=None,
                            help='Optional. Folder with a %s. Default current directory.'
                            % CONANFILE)
        parser.add_argument("--file", "-f", help="specify conanfile filename")
        parser.add_argument('--keep-source', '-k', default=False, action='store_true',
                            help='Optional. Do not remove the source folder in the local cache. '
                                 'Use for testing purposes only')
        args = parser.parse_args(*args)
        name, version, user, channel = get_reference_fields(args.reference)

        return self._conan.export(user=user, channel=channel, path=args.path,
                                  keep_source=args.keep_source, filename=args.file,
                                  name=name, version=version)

    def remove(self, *args):
        """Remove any package recipe or binary matching a pattern.
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
        parser.add_argument('-r', '--remote', help='Will remove from the specified remote')
        parser.add_argument('-q', '--query', default=None, help='Packages query: "os=Windows AND '
                                                                '(arch=x86 OR compiler=gcc)".'
                                                                ' The "pattern" parameter '
                                                                'has to be a package recipe '
                                                                'reference: MyPackage/1.2'
                                                                '@user/channel')
        parser.add_argument("--outdated", "-o", help="Remove only outdated from recipe packages",
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
        """ Copy conan recipes and packages to another user/channel.
        Useful to promote packages (e.g. from "beta" to "stable").
        Also for moving packages from one user to another.
        """
        parser = argparse.ArgumentParser(description=self.copy.__doc__, prog="conan copy")
        parser.add_argument("reference", default="",
                            help='package recipe reference'
                            'e.g., MyPackage/1.2@user/channel')
        parser.add_argument("user_channel", default="",
                            help='Destination user/channel'
                            'e.g., lasote/testing')
        parser.add_argument("--package", "-p", nargs=1, action=Extender,
                            help='copy specified package ID')
        parser.add_argument("--all", action='store_true',
                            default=False,
                            help='Copy all packages from the specified package recipe')
        parser.add_argument("--force", action='store_true',
                            default=False,
                            help='Override destination packages and the package recipe')
        args = parser.parse_args(*args)
        return self._conan.copy(reference=args.reference, user_channel=args.user_channel,
                                force=args.force,
                                all=args.all, package=args.package)

    def user(self, *parameters):
        """ Update your cached user name (and auth token) to avoid it being requested later.
        e.g. while you're uploading a package.
        You can have more than one user (one per remote). Changing the user, or introducing the
        password is only necessary to upload packages to a remote.
        """
        parser = argparse.ArgumentParser(description=self.user.__doc__, prog="conan user")
        parser.add_argument("name", nargs='?', default=None,
                            help='Username you want to use. '
                                 'If no name is provided it will show the current user.')
        parser.add_argument("-p", "--password", help='User password. Use double quotes '
                            'if password with spacing, and escape quotes if existing')
        parser.add_argument("--remote", "-r", help='look in the specified remote server')
        parser.add_argument('-c', '--clean', default=False,
                            action='store_true', help='Remove user and tokens for all remotes')
        args = parser.parse_args(*parameters)  # To enable -h
        return self._conan.user(name=args.name, clean=args.clean, remote=args.remote,
                                password=args.password)

    def search(self, *args):
        """ Search package recipes and binaries in the local cache or in a remote server.

        If you provide a pattern, then it will search for existing package recipes matching that pattern.
        If a full and complete package reference is provided, like Pkg/0.1@user/channel, then the existing
        package binaries for that reference will be displayed.
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
                            action='store_true', help='Make a case-sensitive search. Use it to guarantee case-sensitive '
                            'search in Windows or other case-insensitive filesystems')
        parser.add_argument('-r', '--remote', help='Remote origin')
        parser.add_argument('--raw', default=False, action='store_true',
                            help='Print just the list of recipes')
        parser.add_argument('--table',
                            help='Outputs html file with a table of binaries. Only valid if '
                                 '"pattern" is a package recipe reference')
        parser.add_argument('-q', '--query', default=None, help='Packages query: "os=Windows AND '
                                                                '(arch=x86 OR compiler=gcc)".'
                                                                ' The "pattern" parameter '
                                                                'has to be a package recipe '
                                                                'reference: MyPackage/1.2'
                                                                '@user/channel')
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
        """ Uploads a package recipe and the generated binary packages to a specified remote
        """
        parser = argparse.ArgumentParser(description=self.upload.__doc__,
                                         prog="conan upload")
        parser.add_argument('pattern', help='Pattern or package recipe reference, '
                                            'e.g., "openssl/*", "MyPackage/1.2@user/channel"')
        # TODO: packageparser.add_argument('package', help='user name')
        parser.add_argument("--package", "-p", default=None, help='package ID to upload')
        parser.add_argument("--remote", "-r", help='upload to this specific remote')
        parser.add_argument("--all", action='store_true',
                            default=False, help='Upload both package recipe and packages')
        parser.add_argument("--skip-upload", "--skip_upload", action='store_true',
                            default=False, help='Do not upload anything, just run '
                                                'the checks and the compression.')
        parser.add_argument("--force", action='store_true',
                            default=False,
                            help='Do not check conan recipe date, override remote with local')
        parser.add_argument("--check", action='store_true',
                            default=False,
                            help='Perform an integrity check, using the manifests, before upload')
        parser.add_argument('--confirm', '-c', default=False,
                            action='store_true',
                            help='If pattern is given upload all matching recipes without '
                                 'confirmation')
        parser.add_argument('--retry', default=2, type=int,
                            help='In case of fail retries to upload again the specified times')
        parser.add_argument('--retry-wait', '--retry_wait', default=5, type=int,
                            help='Waits specified seconds before retry again')

        args = parser.parse_args(*args)
        return self._conan.upload(pattern=args.pattern, package=args.package, remote=args.remote,
                                  all=args.all,
                                  force=args.force, confirm=args.confirm, retry=args.retry,
                                  retry_wait=args.retry_wait,
                                  skip_upload=args.skip_upload, integrity_check=args.check)

    def remote(self, *args):
        """ Handles the remote list and the package recipes associated to a remote.
        """
        parser = argparse.ArgumentParser(description=self.remote.__doc__, prog="conan remote")
        subparsers = parser.add_subparsers(dest='subcommand', help='sub-command help')

        # create the parser for the "a" command
        subparsers.add_parser('list', help='list current remotes')
        parser_add = subparsers.add_parser('add', help='add a remote')
        parser_add.add_argument('remote',  help='name of the remote')
        parser_add.add_argument('url',  help='url of the remote')
        parser_add.add_argument('verify_ssl',
                                help='Verify SSL certificated. Default True',
                                default="True", nargs="?")
        parser_add.add_argument("-i", "--insert", nargs="?", const=0, type=int,
                                help="insert remote at specific index")
        parser_rm = subparsers.add_parser('remove', help='remove a remote')
        parser_rm.add_argument('remote',  help='name of the remote')
        parser_upd = subparsers.add_parser('update', help='update the remote url')
        parser_upd.add_argument('remote',  help='name of the remote')
        parser_upd.add_argument('url',  help='url')
        parser_upd.add_argument('verify_ssl',
                                help='Verify SSL certificated. Default True',
                                default="True", nargs="?")
        parser_upd.add_argument("-i", "--insert", nargs="?", const=0, type=int,
                                help="insert remote at specific index")

        subparsers.add_parser('list_ref',
                              help='list the package recipes and its associated remotes')
        parser_padd = subparsers.add_parser('add_ref',
                                            help="associate a recipe's reference to a remote")
        parser_padd.add_argument('reference',  help='package recipe reference')
        parser_padd.add_argument('remote',  help='name of the remote')
        parser_prm = subparsers.add_parser('remove_ref',
                                           help="dissociate a recipe's reference and its remote")
        parser_prm.add_argument('reference',  help='package recipe reference')
        parser_pupd = subparsers.add_parser('update_ref', help="update the remote associated "
                                            "with a package recipe")
        parser_pupd.add_argument('reference',  help='package recipe reference')
        parser_pupd.add_argument('remote',  help='name of the remote')
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
        """ List profiles in the '.conan/profiles' folder, or show profile details.
        The 'list' subcommand will always use the default user 'conan/profiles' folder. But the
        'show' subcommand is able to resolve absolute and relative paths, as well as to map names to
        '.conan/profiles' folder, in the same way as the '--profile' install argument.
        """
        parser = argparse.ArgumentParser(description=self.profile.__doc__, prog="conan profile")
        subparsers = parser.add_subparsers(dest='subcommand', help='sub-command help')

        # create the parser for the "profile" command
        subparsers.add_parser('list', help='list current profiles')
        parser_show = subparsers.add_parser('show', help='show the values defined for a profile.'
                                                         ' Can be a path (relative or absolute) to'
                                                         ' a profile file in  any location.')
        parser_show.add_argument('profile',  help='name of the profile')

        parser_new = subparsers.add_parser('new', help='Creates a new empty profile')
        parser_new.add_argument('profile',  help='name of the profile')
        parser_new.add_argument("--detect", action='store_true',
                                default=False,
                                help='Autodetect settings and fill [settings] section')

        parser_update = subparsers.add_parser('update', help='Update a profile')
        parser_update.add_argument('item', help='key="value to set", e.j: settings.compiler=gcc')
        parser_update.add_argument('profile',  help='name of the profile')

        parser_get = subparsers.add_parser('get', help='Get a profile key')
        parser_get.add_argument('item', help='key="value to get", e.j: settings.compiler')
        parser_get.add_argument('profile',  help='name of the profile')

        parser_remove = subparsers.add_parser('remove', help='Remove a profile key')
        parser_remove.add_argument('item', help='key", e.j: settings.compiler')
        parser_remove.add_argument('profile',  help='name of the profile')

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
            except:
                raise ConanException("Please specify key=value")
            self._conan.update_profile(profile, key, value)
        elif args.subcommand == "get":
            key = args.item
            self._outputer.writeln(self._conan.get_profile_key(profile, key))
        elif args.subcommand == "remove":
            self._conan.delete_profile_key(profile, args.item)

        return

    def get(self, *args):
        """ Gets a file or list a directory of a given reference or package
        """
        parser = argparse.ArgumentParser(description=self.get.__doc__,
                                         prog="conan get")
        parser.add_argument('reference', help='package recipe reference')
        parser.add_argument('path',
                            help='Path to the file or directory. If not specified will get the '
                                 'conafile if only a reference is specified and a conaninfo.txt '
                                 'file contents if the package is also specified',
                            default=None, nargs="?")
        parser.add_argument("--package", "-p", default=None, help='package ID')
        parser.add_argument("--remote", "-r", help='Get from this specific remote')
        parser.add_argument("--raw", "-raw", help='Do not decorate the text', default=False,
                            action='store_true')
        args = parser.parse_args(*args)

        ret, path = self._conan.get_path(args.reference, args.package, args.path, args.remote)
        if isinstance(ret, list):
            self._outputer.print_dir_list(ret, path, args.raw)
        else:
            self._outputer.print_file_contents(ret, path, args.raw)

        return

    def alias(self, *args):
        """ Creates and export an alias recipe
        """
        parser = argparse.ArgumentParser(description=self.upload.__doc__,
                                         prog="conan alias")
        parser.add_argument('reference', help='Alias reference. e.j: mylib/1.X@user/channel')
        parser.add_argument('target', help='Target reference. e.j: mylib/1.12@user/channel')
        args = parser.parse_args(*args)

        self._conan.export_alias(args.reference, args.target)

        return

    def _show_help(self):
        """ prints a summary of all commands
        """
        grps = [("Consumer commands", ("install", "config", "get", "info", "search")),
                ("Creator's commands", ("new", "create", "upload", "export", "export-pkg", "test")),
                ("Package development commands", ("source", "build", "package")),
                ("Misc commands", ("profile", "remote", "user", "imports", "copy", "remove",
                                   "alias", "download")),
                ("Deprecated", ("test_package",))]

        def check_all_commands_listed():
            """Keep updated the main directory, raise if don't"""
            all_commands = self._commands()
            all_in_grps = [command for _, command_list in grps for command in command_list]
            if set(all_in_grps) != set(all_commands):
                diff = set(all_commands) - set(all_in_grps)
                raise Exception("Some command is missing in the main help: %s" % ",".join(diff))
            return all_commands

        commands = check_all_commands_listed()
        max_len = max((len(c) for c in commands)) + 2
        fmt = '  %-{}s'.format(max_len)

        for group_name, comm_names in grps:
            self._user_io.out.writeln(group_name, Color.MAGENTA)
            for name in comm_names:
                # future-proof way to ensure tabular formatting
                self._user_io.out.write(fmt % name, Color.GREEN)
                self._user_io.out.writeln(commands[name].__doc__.split('\n', 1)[0].strip())

        self._user_io.out.writeln("")
        self._user_io.out.writeln('Conan commands. Type $conan "command" -h for help',
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
                    msg = "-q parameter only allowed with a valid recipe reference as search " \
                          "pattern. e.j conan search " \
                          "MyPackage/1.2@user/channel -q \"os=Windows\""
                    raise ConanException(msg)
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
        except:
            raise ConanException("Invalid parameter '%s', specify the full reference or "
                                 "user/channel" % arg_reference)

    return name, version, user, channel


def _add_manifests_arguments(parser):
    parser.add_argument("--manifests", "-m", const=default_manifest_folder, nargs="?",
                        help='Install dependencies manifests in folder for later verify.'
                             ' Default folder is .conan_manifests, but can be changed')
    parser.add_argument("--manifests-interactive", "-mi", const=default_manifest_folder,
                        nargs="?",
                        help='Install dependencies manifests in folder for later verify, '
                             'asking user for confirmation. '
                             'Default folder is .conan_manifests, but can be changed')
    parser.add_argument("--verify", "-v", const=default_manifest_folder, nargs="?",
                        help='Verify dependencies manifests against stored ones')


def _add_common_install_arguments(parser, build_help):
    parser.add_argument("--update", "-u", action='store_true', default=False,
                        help="check updates exist from upstream remotes")
    parser.add_argument("--scope", "-sc", nargs=1, action=Extender,
                        help='Use the specified scope in the install command')
    parser.add_argument("--profile", "-pr", default=None,
                        help='Apply the specified profile to the install command')
    parser.add_argument("-r", "--remote", help='look in the specified remote server')
    parser.add_argument("--options", "-o",
                        help='Options to build the package, overwriting the defaults. e.g., '
                             '-o with_qt=true',
                        nargs=1, action=Extender)
    parser.add_argument("--settings", "-s",
                        help='Settings to build the package, overwriting the defaults. e.g., '
                             '-s compiler=gcc',
                        nargs=1, action=Extender)
    parser.add_argument("--env", "-e",
                        help='Environment variables that will be set during the package build, '
                             '-e CXX=/usr/bin/clang++',
                        nargs=1, action=Extender)
    if build_help:
        parser.add_argument("--build", "-b", action=Extender, nargs="*", help=build_help)


_help_build_policies = '''Optional, use it to choose if you want to build from sources:

        --build            Build all from sources, do not use binary packages.
        --build=never      Default option. Never build, use binary packages or fail if a binary package is not found.
        --build=missing    Build from code if a binary package is not found.
        --build=outdated   Build from code if the binary is not built with the current recipe or when missing binary package.
        --build=[pattern]  Build always these packages from source, but never build the others. Allows multiple --build parameters.
'''


def main(args):
    """ main entry point of the conan application, using a Command to
    parse parameters
    """
    try:
        conan_api, client_cache, user_io = Conan.factory()
    except ConanException:  # Error migrating
        sys.exit(-1)

    outputer = CommandOutputer(user_io, client_cache)
    command = Command(conan_api, client_cache, user_io, outputer)
    current_dir = os.getcwd()
    try:
        import signal

        def sigint_handler(_, __):
            print('You pressed Ctrl+C!')
            sys.exit(0)

        signal.signal(signal.SIGINT, sigint_handler)
        error = command.run(args)
    finally:
        os.chdir(current_dir)
    sys.exit(error)
