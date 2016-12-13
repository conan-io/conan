import argparse
import inspect
import hashlib
import re
import sys
import os
import requests
from argparse import RawTextHelpFormatter
from collections import defaultdict

from conans import __version__ as CLIENT_VERSION
from conans.client.client_cache import ClientCache
from conans.client.conf import MIN_SERVER_COMPATIBLE_VERSION
from conans.client.manager import ConanManager
from conans.client.migrations import ClientMigrator
from conans.client.remote_manager import RemoteManager
from conans.client.remote_registry import RemoteRegistry
from conans.client.rest.auth_manager import ConanApiAuthManager
from conans.client.rest.rest_client import RestApiClient
from conans.client.rest.version_checker import VersionCheckerRequester
from conans.client.output import ConanOutput, Color
from conans.client.runner import ConanRunner
from conans.client.store.localdb import LocalDB
from conans.client.userio import UserIO
from conans.errors import ConanException
from conans.model.ref import ConanFileReference
from conans.model.scope import Scopes
from conans.model.version import Version
from conans.paths import CONANFILE, conan_expand_user
from conans.search.search import DiskSearchManager, DiskSearchAdapter
from conans.util.log import logger
from conans.util.env_reader import get_env
from conans.util.files import rmdir, load, save_files
from conans.util.config_parser import get_bool_from_text_value
from conans.client.printer import Printer

class Extender(argparse.Action):
    '''Allows to use the same flag several times in a command and creates a list with the values.
       For example:
           conan install MyPackage/1.2@user/channel -o qt:value -o mode:2 -s cucumber:true
           It creates:
           options = ['qt:value', 'mode:2']
           settings = ['cucumber:true']
    '''

    def __call__(self, parser, namespace, values, option_strings=None):  # @UnusedVariable
        # Need None here incase `argparse.SUPPRESS` was supplied for `dest`
        dest = getattr(namespace, self.dest, None)
        if(not hasattr(dest, 'extend') or dest == self.default):
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
    def __init__(self, client_cache, user_io, runner, remote_manager, search_manager):
        assert isinstance(user_io, UserIO)
        assert isinstance(client_cache, ClientCache)
        self._client_cache = client_cache
        self._user_io = user_io
        self._runner = runner
        self._manager = ConanManager(client_cache, user_io, runner, remote_manager, search_manager)

    def _parse_args(self, parser):
        parser.add_argument("-r", "--remote", help='look for in the remote storage')
        parser.add_argument("--options", "-o",
                            help='load options to build the package, e.g., -o with_qt=true',
                            nargs=1, action=Extender)
        parser.add_argument("--settings", "-s",
                            help='load settings to build the package, -s compiler:gcc',
                            nargs=1, action=Extender)
        parser.add_argument("--env", "-e",
                            help='set environment variables to build the package, -e CXX=/usr/bin/clang++',
                            nargs=1, action=Extender)
        parser.add_argument("--build", "-b", action=Extender, nargs="*",
                            help='''Optional, use it to choose if you want to build from sources:

--build            Build all from sources, do not use binary packages.
--build=never      Default option. Never build, use binary packages or fail if a binary package is not found.
--build=missing    Build from code if a binary package is not found.
--build=outdated   Build from code if the binary is not built with the current recipe or when missing binary package.
--build=[pattern]  Build always these packages from source, but never build the others. Allows multiple --build parameters.
''')

    def _get_tuples_list_from_extender_arg(self, items):
        if not items:
            return []
        # Validate the pairs
        for item in items:
            chunks = item.split("=")
            if len(chunks) != 2:
                raise ConanException("Invalid input '%s', use 'name=value'" % item)
        return [(item[0], item[1]) for item in [item.split("=") for item in items]]

    def _get_simple_and_package_tuples(self, items):
        ''' Parse items like "thing:item=value or item2=value2 and returns a tuple list for
        the simple items (name, value) and a dict for the package items
        {package: [(item, value)...)], ...}
        '''
        simple_items = []
        package_items = defaultdict(list)
        tuples = self._get_tuples_list_from_extender_arg(items)
        for name, value in tuples:
            if ":" in name:  # Scoped items
                tmp = name.split(":", 1)
                ref_name = tmp[0]
                name = tmp[1]
                package_items[ref_name].append((name, value))
            else:
                simple_items.append((name, value))
        return simple_items, package_items

    def _get_build_sources_parameter(self, build_param):
        # returns True if we want to build the missing libraries
        #         False if building is forbidden
        #         A list with patterns: Will force build matching libraries,
        #                               will look for the package for the rest
        #         "outdated" if will build when the package is not generated with
        #                    the current exported recipe

        if isinstance(build_param, list):
            if len(build_param) == 0:  # All packages from source
                return ["*"]
            elif len(build_param) == 1 and build_param[0] == "never":
                return False  # Default
            elif len(build_param) == 1 and build_param[0] == "missing":
                return True
            elif len(build_param) == 1 and build_param[0] == "outdated":
                return "outdated"
            else:  # A list of expressions to match (if matches, will build from source)
                return ["%s*" % ref_expr for ref_expr in build_param]
        else:
            return False  # Nothing is built

    def _test_check(self, test_folder, test_folder_name):
        """ To ensure that the 0.9 version new layout is detected and users warned
        """
        # Check old tests, format
        test_conanfile = os.path.join(test_folder, "conanfile.py")
        if not os.path.exists(test_conanfile):
            raise ConanException("Test conanfile.py does not exist")
        test_conanfile_content = load(test_conanfile)
        if ".conanfile_directory" not in test_conanfile_content:
            self._user_io.out.error("""******* conan test command layout has changed *******

In your "%s" folder 'conanfile.py' you should use the
path to the conanfile_directory, something like:

    self.run('cmake %%s %%s' %% (self.conanfile_directory, cmake.command_line))

 """ % (test_folder_name))

        # Test the CMakeLists, if existing
        test_cmake = os.path.join(test_folder, "CMakeLists.txt")
        if os.path.exists(test_cmake):
            test_cmake_content = load(test_cmake)
            if "${CMAKE_BINARY_DIR}/conanbuildinfo.cmake" not in test_cmake_content:
                self._user_io.out.error("""******* conan test command layout has changed *******

In your "%s" folder 'CMakeLists.txt' you should use the
path to the CMake binary directory, like this:

   include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)

 """ % (test_folder_name))

    def new(self, *args):
        """ create a new package template conanfile.py and other optional files
        """
        parser = argparse.ArgumentParser(description=self.new.__doc__, prog="conan new",
                                         formatter_class=RawTextHelpFormatter)
        parser.add_argument("name", help='Package name, e.g.: Poco/1.7.3@user/testing')
        parser.add_argument("-t", "--test", action='store_true', default=False,
                            help='Create test_package skeleton to test package')
        parser.add_argument("-i", "--header", action='store_true', default=False,
                            help='Create a headers only package')
        parser.add_argument("-c", "--pure_c", action='store_true', default=False,
                            help='Create a C language package only package (non-headers)')

        args = parser.parse_args(*args)

        root_folder = os.getcwd()
        try:
            name, version, user, channel = ConanFileReference.loads(args.name)
            pattern = re.compile('[\W_]+')
            package_name = pattern.sub('', name).capitalize()
        except:
            raise ConanException("Bad parameter, please use full package name,"
                                 "e.g: MyLib/1.2.3@user/testing")
        from conans.client.new import (conanfile, conanfile_header, test_conanfile, test_cmake,
                                       test_main)
        if args.header:
            files = {"conanfile.py": conanfile_header.format(name=name, version=version,
                                                             package_name=package_name)}
        else:
            files = {"conanfile.py": conanfile.format(name=name, version=version,
                                                      package_name=package_name)}
            if args.pure_c:
                config = "\n    def config(self):\n        del self.settings.compiler.libcxx"
                files["conanfile.py"] = files["conanfile.py"] + config
        if args.test:
            files["test_package/conanfile.py"] = test_conanfile.format(name=name, version=version,
                                                                       user=user, channel=channel,
                                                                       package_name=package_name)
            files["test_package/CMakeLists.txt"] = test_cmake
            files["test_package/example.cpp"] = test_main
        save_files(root_folder, files)
        for f in sorted(files):
            self._user_io.out.success("File saved: %s" % f)

    def test_package(self, *args):
        """ build and run your package test. Must have conanfile.py with "test"
        method and "test_package" subfolder with package consumer test project
        """
        parser = argparse.ArgumentParser(description=self.test_package.__doc__,
                                         prog="conan test_package",
                                         formatter_class=RawTextHelpFormatter)
        parser.add_argument("path", nargs='?', default="", help='path to conanfile file, '
                            'e.g. /my_project/')
        parser.add_argument("-ne", "--not-export", default=False, action='store_true',
                            help='Do not export the conanfile before test execution')
        parser.add_argument("-f", "--folder", help='alternative test folder name')
        parser.add_argument("--scope", "-sc", nargs=1, action=Extender,
                            help='Define scopes for packages')
        parser.add_argument('--keep-source', '-k', default=False, action='store_true',
                            help='Optional. Do not remove the source folder in local store. '
                                 'Use for testing purposes only')
        parser.add_argument("--update", "-u", action='store_true', default=False,
                            help="update with new upstream packages")
        parser.add_argument("--profile", "-pr", default=None, help='Define a profile')
        self._parse_args(parser)

        args = parser.parse_args(*args)

        current_path = os.getcwd()
        root_folder = os.path.normpath(os.path.join(current_path, args.path))
        if args.folder:
            test_folder_name = args.folder
            test_folder = os.path.join(root_folder, test_folder_name)
            test_conanfile = os.path.join(test_folder, "conanfile.py")
            if not os.path.exists(test_conanfile):
                raise ConanException("test folder '%s' not available, "
                                     "or it doesn't have a conanfile.py" % args.folder)
        else:
            for name in ["test_package", "test"]:
                test_folder_name = name
                test_folder = os.path.join(root_folder, test_folder_name)
                test_conanfile = os.path.join(test_folder, "conanfile.py")
                if os.path.exists(test_conanfile):
                    break
            else:
                raise ConanException("test folder 'test_package' not available, "
                                     "or it doesn't have a conanfile.py")

        options = args.options or []
        settings = args.settings or []

        sha = hashlib.sha1("".join(options + settings).encode()).hexdigest()
        build_folder = os.path.join(test_folder, "build", sha)
        rmdir(build_folder)
        # shutil.copytree(test_folder, build_folder)

        options = self._get_tuples_list_from_extender_arg(args.options)
        env, package_env = self._get_simple_and_package_tuples(args.env)
        settings, package_settings = self._get_simple_and_package_tuples(args.settings)
        scopes = Scopes.from_list(args.scope) if args.scope else None

        manager = self._manager

        # Read profile environment and mix with the command line parameters
        if args.profile:
            try:
                profile = manager.read_profile(args.profile, current_path)
            except ConanException as exc:
                raise ConanException("Error reading '%s' profile: %s" % (args.profile, exc))
            else:
                profile.update_env(env)
                profile.update_packages_env(package_env)
                env = profile.env
                package_env = profile.package_env

        loader = manager._loader(current_path=None, user_settings_values=settings, user_options_values=options,
                                 scopes=scopes, package_settings=package_settings, env=env, package_env=package_env)
        conanfile = loader.load_conan(test_conanfile, self._user_io.out, consumer=True)
        try:
            # convert to list from ItemViews required for python3
            conanfile.requirements()
            reqs = list(conanfile.requires.items())
            first_dep = reqs[0][1].conan_reference
        except Exception:
            raise ConanException("Unable to retrieve first requirement of test conanfile.py")

        # Forcing an export!
        if not args.not_export:
            self._user_io.out.info("Exporting package recipe")
            user_channel = "%s/%s" % (first_dep.user, first_dep.channel)
            self._manager.export(user_channel, root_folder, keep_source=args.keep_source)

        lib_to_test = first_dep.name + "*"
        # Get False or a list of patterns to check
        if args.build is None and lib_to_test:  # Not specified, force build the tested library
            args.build = [lib_to_test]
        else:
            args.build = self._get_build_sources_parameter(args.build)

        self._manager.install(reference=test_folder,
                              current_path=build_folder,
                              remote=args.remote,
                              options=options,
                              settings=settings,
                              package_settings=package_settings,
                              build_mode=args.build,
                              scopes=scopes,
                              update=args.update,
                              generators=["env", "txt"],
                              profile_name=args.profile,
                              env=env,
                              package_env=package_env
                              )
        self._test_check(test_folder, test_folder_name)
        self._manager.build(test_folder, build_folder, test=True, profile_name=args.profile,
                            env=env, package_env=package_env)

    # Alias to test
    def test(self, *args):
        """ (deprecated). Alias to test_package, use it instead
        """
        self.test_package(*args)

    def install(self, *args):
        """ install in the local store the given requirements.
        Requirements can be defined in the command line or in a conanfile.
        EX: conan install opencv/2.4.10@lasote/testing
        """
        parser = argparse.ArgumentParser(description=self.install.__doc__, prog="conan install",
                                         formatter_class=RawTextHelpFormatter)
        parser.add_argument("reference", nargs='?', default="",
                            help='package recipe reference'
                            'e.g., MyPackage/1.2@user/channel or ./my_project/')
        parser.add_argument("--package", "-p", nargs=1, action=Extender,
                            help='Force install specified package ID (ignore settings/options)')
        parser.add_argument("--all", action='store_true', default=False,
                            help='Install all packages from the specified package recipe')
        parser.add_argument("--file", "-f", help="specify conanfile filename")
        parser.add_argument("--update", "-u", action='store_true', default=False,
                            help="update with new upstream packages")
        parser.add_argument("--scope", "-sc", nargs=1, action=Extender,
                            help='Define scopes for packages')
        parser.add_argument("--profile", "-pr", default=None, help='Define a profile')
        parser.add_argument("--generator", "-g", nargs=1, action=Extender,
                            help='Generators to use')
        parser.add_argument("--werror", action='store_true', default=False,
                            help='Error instead of warnings for graph inconsistencies')

        # Manifests arguments
        default_manifest_folder = '.conan_manifests'
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

        parser.add_argument("--no-imports", action='store_true', default=False,
                            help='Install specified packages but avoid running imports')

        self._parse_args(parser)

        args = parser.parse_args(*args)
        self._user_io.out.werror_active = args.werror

        current_path = os.getcwd()
        try:
            reference = ConanFileReference.loads(args.reference)
        except:
            reference = os.path.normpath(os.path.join(current_path, args.reference))

        if args.all or args.package:  # Install packages without settings (fixed ids or all)
            if args.all:
                args.package = []
            if not args.reference or not isinstance(reference, ConanFileReference):
                raise ConanException("Invalid package recipe reference. "
                                     "e.g., MyPackage/1.2@user/channel")
            self._manager.download(reference, args.package, remote=args.remote)
        else:  # Classic install, package chosen with settings and options
            # Get False or a list of patterns to check
            args.build = self._get_build_sources_parameter(args.build)
            options = self._get_tuples_list_from_extender_arg(args.options)
            settings, package_settings = self._get_simple_and_package_tuples(args.settings)
            env, package_env = self._get_simple_and_package_tuples(args.env)

            scopes = Scopes.from_list(args.scope) if args.scope else None
            if args.manifests and args.manifests_interactive:
                raise ConanException("Do not specify both manifests and "
                                     "manifests-interactive arguments")
            if args.verify and (args.manifests or args.manifests_interactive):
                raise ConanException("Do not specify both 'verify' and "
                                     "'manifests' or 'manifests-interactive' arguments")
            manifest_folder = args.verify or args.manifests or args.manifests_interactive
            if manifest_folder:
                if not os.path.isabs(manifest_folder):
                    if isinstance(reference, ConanFileReference):
                        manifest_folder = os.path.join(current_path, manifest_folder)
                    else:
                        manifest_folder = os.path.join(reference, manifest_folder)
                manifest_verify = args.verify is not None
                manifest_interactive = args.manifests_interactive is not None
            else:
                manifest_verify = manifest_interactive = False
            self._manager.install(reference=reference,
                                  current_path=current_path,
                                  remote=args.remote,
                                  options=options,
                                  settings=settings,
                                  build_mode=args.build,
                                  filename=args.file,
                                  update=args.update,
                                  manifest_folder=manifest_folder,
                                  manifest_verify=manifest_verify,
                                  manifest_interactive=manifest_interactive,
                                  scopes=scopes,
                                  generators=args.generator,
                                  profile_name=args.profile,
                                  package_settings=package_settings,
                                  env=env,
                                  package_env=package_env,
                                  no_imports=args.no_imports)

    def info(self, *args):
        """ Prints information about the requirements.
        Requirements can be defined in the command line or in a conanfile.
        EX: conan info opencv/2.4.10@lasote/testing
        """
        parser = argparse.ArgumentParser(description=self.info.__doc__, prog="conan info",
                                         formatter_class=RawTextHelpFormatter)
        parser.add_argument("reference", nargs='?', default="",
                            help='reference name or path to conanfile file, '
                            'e.g., MyPackage/1.2@user/channel or ./my_project/')
        parser.add_argument("--file", "-f", help="specify conanfile filename")
        parser.add_argument("-r", "--remote", help='look for in the remote storage')
        parser.add_argument("--options", "-o",
                            help='load options to build the package, e.g., -o with_qt=true',
                            nargs=1, action=Extender)
        parser.add_argument("--settings", "-s",
                            help='load settings to build the package, -s compiler:gcc',
                            nargs=1, action=Extender)
        parser.add_argument("--only", "-n",
                            help='show fields only')
        parser.add_argument("--update", "-u", action='store_true', default=False,
                            help="check updates exist from upstream remotes")
        parser.add_argument("--build_order", "-bo",
                            help='given a modified reference, return ordered list to build (CI)',
                            nargs=1, action=Extender)
        parser.add_argument("--scope", "-sc", nargs=1, action=Extender,
                            help='Define scopes for packages')
        args = parser.parse_args(*args)

        options = self._get_tuples_list_from_extender_arg(args.options)
        settings, package_settings = self._get_simple_and_package_tuples(args.settings)
        current_path = os.getcwd()
        try:
            reference = ConanFileReference.loads(args.reference)
        except:
            reference = os.path.normpath(os.path.join(current_path, args.reference))
        scopes = Scopes.from_list(args.scope) if args.scope else None
        self._manager.info(reference=reference,
                           current_path=current_path,
                           remote=args.remote,
                           options=options,
                           settings=settings,
                           package_settings=package_settings,
                           info=args.only or True,
                           check_updates=args.update,
                           filename=args.file,
                           build_order=args.build_order,
                           scopes=scopes)

    def build(self, *args):
        """ Calls your project conanfile.py "build" method.
            E.g. conan build ./my_project
            Intended for package creators, requires a conanfile.py.
        """
        parser = argparse.ArgumentParser(description=self.build.__doc__, prog="conan build")
        parser.add_argument("path", nargs="?",
                            help='path to user conanfile.py, e.g., conan build .',
                            default="")
        parser.add_argument("--file", "-f", help="specify conanfile filename")
        parser.add_argument("--profile", "-pr", default=None, help='Define a profile')
        args = parser.parse_args(*args)
        current_path = os.getcwd()
        if args.path:
            root_path = os.path.abspath(args.path)
        else:
            root_path = current_path
        self._manager.build(root_path, current_path, filename=args.file, profile_name=args.profile)

    def package(self, *args):
        """ Calls your conanfile.py "package" method for a specific package recipe.
            It will not create a new package, use 'install' or 'test_package' instead for
            packages in the conan local cache, or `build' for conanfile.py in user space.
            Intended for package creators, for regenerating a package without
            recompiling the source, i.e. for troubleshooting,
            and fixing the package() method, not normal operation. It requires
            the package has been built locally, it will not re-package otherwise.
            E.g. conan package MyPackage/1.2@user/channel 9cf83afd07b678da9c1645f605875400847ff3

            When used in a user space project, it will execute from the build folder specified
            as parameter, and the current directory. This is useful while creating package recipes
            or just for extracting artifacts from the current project, without even being a package
        """
        parser = argparse.ArgumentParser(description=self.package.__doc__, prog="conan package")
        parser.add_argument("reference", help='package recipe reference '
                            'e.g. MyPkg/0.1@user/channel, or local path to the build folder'
                            ' (relative or absolute)')
        parser.add_argument("package", nargs="?", default="",
                            help='Package ID to regenerate. e.g., '
                                 '9cf83afd07b678d38a9c1645f605875400847ff3'
                                 ' If not specified, ALL binaries for this recipe are re-packaged')

        args = parser.parse_args(*args)

        current_path = os.getcwd()
        try:
            reference = ConanFileReference.loads(args.reference)
            self._manager.package(reference, args.package)
        except:
            if "@" in args.reference:
                raise
            build_folder = args.reference
            if not os.path.isabs(build_folder):
                build_folder = os.path.normpath(os.path.join(current_path, build_folder))
            self._manager.local_package(current_path, build_folder)

    def _get_reference(self, args):
        current_path = os.getcwd()
        try:
            reference = ConanFileReference.loads(args.reference)
        except:
            if "@" in args.reference:
                raise
            if not os.path.isabs(args.reference):
                reference = os.path.normpath(os.path.join(current_path, args.reference))
            else:
                reference = args.reference
        return current_path, reference

    def source(self, *args):
        """ Calls your conanfile.py "source" method to configure the source directory.
            I.e., downloads and unzip the package source.
        """
        parser = argparse.ArgumentParser(description=self.source.__doc__, prog="conan source")
        parser.add_argument("reference", nargs='?', default="", help="package recipe reference. e.g., MyPackage/1.2@user/channel or ./my_project/")
        parser.add_argument("-f", "--force", default=False, action="store_true", help="force remove the source directory and run again.")

        args = parser.parse_args(*args)

        current_path, reference = self._get_reference(args)
        self._manager.source(current_path, reference, args.force)

    def imports(self, *args):
        """ Executes only the import functionality of the conanfile (txt or py). It requires
        to have been previously installed and have a conanbuildinfo.txt generated file
        """
        parser = argparse.ArgumentParser(description=self.imports.__doc__, prog="conan imports")
        parser.add_argument("reference", nargs='?', default="",
                            help="package recipe reference. e.g., MyPackage/1.2@user/channel or ./my_project/")
        parser.add_argument("--file", "-f", help="specify conanfile filename")
        parser.add_argument("-d", "--dest",
                            help="optional destination base directory, current dir by default")
        parser.add_argument("-u", "--undo", default=False, action="store_true",
                            help="Undo the imports, remove files copied to project or user space")

        args = parser.parse_args(*args)

        if args.undo:
            if not os.path.isabs(args.reference):
                current_path = os.path.normpath(os.path.join(os.getcwd(), args.reference))
            else:
                current_path = args.reference
            self._manager.imports_undo(current_path)
        else:
            dest_folder = args.dest
            current_path, reference = self._get_reference(args)
            self._manager.imports(current_path, reference, args.file, dest_folder)

    def export(self, *args):
        """ Copies the package recipe (conanfile.py and associated files) to your local store,
        where it can be shared and reused in other projects.
        From that store, it can be uploaded to any remote with "upload" command.
        """
        parser = argparse.ArgumentParser(description=self.export.__doc__, prog="conan export")
        parser.add_argument("user", help='user_name[/channel]. By default, channel is '
                                         '"testing", e.g., phil or phil/stable')
        parser.add_argument('--path', '-p', default=None,
                            help='Optional. Folder with a %s. Default current directory.'
                            % CONANFILE)
        parser.add_argument('--keep-source', '-k', default=False, action='store_true',
                            help='Optional. Do not remove the source folder in local store. '
                                 'Use for testing purposes only')
        args = parser.parse_args(*args)

        current_path = os.path.abspath(args.path or os.getcwd())
        keep_source = args.keep_source
        self._manager.export(args.user, current_path, keep_source)

    def remove(self, *args):
        """ Remove any package recipe or package from your local/remote store
        """
        parser = argparse.ArgumentParser(description=self.remove.__doc__, prog="conan remove")
        parser.add_argument('pattern', help='Pattern name, e.g., openssl/*')
        parser.add_argument('-p', '--packages', const=[], nargs='?',
                            help='By default, remove all the packages or select one, '
                                 'specifying the SHA key')
        parser.add_argument('-b', '--builds', const=[], nargs='?',
                            help='By default, remove all the build folders or select one, '
                                 'specifying the SHA key')
        parser.add_argument('-s', '--src', default=False, action="store_true",
                            help='Remove source folders')
        parser.add_argument('-f', '--force', default=False,
                            action='store_true', help='Remove without requesting a confirmation')
        parser.add_argument('-r', '--remote', help='Remote origin')
        args = parser.parse_args(*args)

        if args.packages:
            args.packages = args.packages.split(",")
        if args.builds:
            args.builds = args.builds.split(",")
        self._manager.remove(args.pattern, package_ids_filter=args.packages,
                             build_ids=args.builds,
                             src=args.src, force=args.force, remote=args.remote)

    def copy(self, *args):
        """ Copy package recipe and packages to another user/channel
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

        reference = ConanFileReference.loads(args.reference)
        new_ref = ConanFileReference.loads("%s/%s@%s" % (reference.name,
                                                         reference.version,
                                                         args.user_channel))
        if args.all:
            args.package = []
        self._manager.copy(reference, args.package, new_ref.user, new_ref.channel, args.force)

    def user(self, *parameters):
        """ shows or change the current user """
        parser = argparse.ArgumentParser(description=self.user.__doc__, prog="conan user")
        parser.add_argument("name", nargs='?', default=None,
                            help='Username you want to use. '
                                 'If no name is provided it will show the current user.')
        parser.add_argument("-p", "--password", help='User password. Use double quotes '
                            'if password with spacing, and escape quotes if existing')
        parser.add_argument("--remote", "-r", help='look for in the remote storage')
        parser.add_argument('-c', '--clean', default=False,
                            action='store_true', help='Remove user and tokens for all remotes')
        args = parser.parse_args(*parameters)  # To enable -h

        if args.clean:
            localdb = LocalDB(self._client_cache.localdb)
            localdb.init(clean=True)
            self._user_io.out.success("Deleted user data")
            return
        self._manager.user(args.remote, args.name, args.password)

    def search(self, *args):
        """ show local/remote packages
        """
        parser = argparse.ArgumentParser(description=self.search.__doc__, prog="conan search")
        parser.add_argument('pattern', nargs='?', help='Pattern name, e.g. openssl/* or package recipe reference if "-q" is used. e.g. MyPackage/1.2@user/channel')
        parser.add_argument('--case-sensitive', default=False,
                            action='store_true', help='Make a case-sensitive search')
        parser.add_argument('-r', '--remote', help='Remote origin')
        parser.add_argument('-q', '--query', default=None, help='Packages query: "os=Windows AND arch=x86". The "pattern" parameter has to be a package recipe reference: MyPackage/1.2@user/channel')
        args = parser.parse_args(*args)

        reference = None
        if args.pattern:
            try:
                reference = ConanFileReference.loads(args.pattern)
            except ConanException:
                if args.query is not None:
                    raise ConanException("-q parameter only allowed with a valid recipe "
                                         "reference as search pattern. e.j conan search "
                                         "MyPackage/1.2@user/channel -q \"os=Windows\"")

        self._manager.search(reference or args.pattern,
                             args.remote,
                             ignorecase=not args.case_sensitive,
                             packages_query=args.query)

    def upload(self, *args):
        """ uploads a conanfile or binary packages from the local store to any remote.
        To upload something, it should be "exported" first.
        """
        parser = argparse.ArgumentParser(description=self.upload.__doc__,
                                         prog="conan upload")
        parser.add_argument("reference",
                            help='package recipe reference, e.g., MyPackage/1.2@user/channel')
        # TODO: packageparser.add_argument('package', help='user name')
        parser.add_argument("--package", "-p", default=None, help='package ID to upload')
        parser.add_argument("--remote", "-r", help='upload to this specific remote')
        parser.add_argument("--all", action='store_true',
                            default=False, help='Upload both package recipe and packages')
        parser.add_argument("--force", action='store_true',
                            default=False,
                            help='Do not check conan recipe date, override remote with local')

        args = parser.parse_args(*args)

        conan_ref = ConanFileReference.loads(args.reference)
        package_id = args.package

        if not conan_ref and not package_id:
            raise ConanException("Enter conan reference or package id")

        self._manager.upload(conan_ref, package_id,
                             args.remote, all_packages=args.all, force=args.force)

    def remote(self, *args):
        """ manage remotes
        """
        parser = argparse.ArgumentParser(description=self.remote.__doc__, prog="conan remote")
        subparsers = parser.add_subparsers(dest='subcommand', help='sub-command help')

        # create the parser for the "a" command
        subparsers.add_parser('list', help='list current remotes')
        parser_add = subparsers.add_parser('add', help='add a remote')
        parser_add.add_argument('remote',  help='name of the remote')
        parser_add.add_argument('url',  help='url of the remote')
        parser_add.add_argument('verify_ssl',  help='Verify SSL certificated. Default True',
                                default="True", nargs="?")
        parser_rm = subparsers.add_parser('remove', help='remove a remote')
        parser_rm.add_argument('remote',  help='name of the remote')
        parser_upd = subparsers.add_parser('update', help='update the remote url')
        parser_upd.add_argument('remote',  help='name of the remote')
        parser_upd.add_argument('url',  help='url')
        parser_upd.add_argument('verify_ssl',  help='Verify SSL certificated. Default True',
                                default="True", nargs="?")
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

        registry = RemoteRegistry(self._client_cache.registry, self._user_io.out)
        if args.subcommand == "list":
            for r in registry.remotes:
                self._user_io.out.info("%s: %s [Verify SSL: %s]" % (r.name, r.url, r.verify_ssl))
        elif args.subcommand == "add":
            verify = get_bool_from_text_value(args.verify_ssl)
            registry.add(args.remote, args.url, args.verify_ssl)
        elif args.subcommand == "remove":
            registry.remove(args.remote)
        elif args.subcommand == "update":
            verify = get_bool_from_text_value(args.verify_ssl)
            registry.update(args.remote, args.url, verify)
        elif args.subcommand == "list_ref":
            for ref, remote in registry.refs.items():
                self._user_io.out.info("%s: %s" % (ref, remote))
        elif args.subcommand == "add_ref":
            registry.add_ref(args.reference, args.remote)
        elif args.subcommand == "remove_ref":
            registry.remove_ref(args.reference)
        elif args.subcommand == "update_ref":
            registry.update_ref(args.reference, args.remote)

    def profile(self, *args):
        """ manage profiles
        """
        parser = argparse.ArgumentParser(description=self.profile.__doc__, prog="conan profile")
        subparsers = parser.add_subparsers(dest='subcommand', help='sub-command help')

        # create the parser for the "profile" command
        subparsers.add_parser('list', help='list current profiles')
        parser_show = subparsers.add_parser('show', help='show the values defined for a profile')
        parser_show.add_argument('profile',  help='name of the profile')
        args = parser.parse_args(*args)

        if args.subcommand == "list":
            folder = self._client_cache.profiles_path
            if os.path.exists(folder):
                profiles = [name for name in os.listdir(folder) if not os.path.isdir(name)]
                for p in profiles:
                    self._user_io.out.info(p)
            else:
                self._user_io.out.info("No profiles defined")
        elif args.subcommand == "show":
            p = self._manager.read_profile(args.profile, os.getcwd())
            Printer(self._user_io.out).print_profile(args.profile, p)

    def _show_help(self):
        """ prints a summary of all commands
        """
        self._user_io.out.writeln('Conan commands. Type $conan "command" -h for help',
                                  Color.BRIGHT_YELLOW)
        commands = self._commands()
        for name in sorted(self._commands()):
            self._user_io.out.write('  %-10s' % name, Color.GREEN)
            self._user_io.out.writeln(commands[name].__doc__.split('\n', 1)[0])

    def _commands(self):
        """ returns a list of available commands
        """
        result = {}
        for m in inspect.getmembers(self, predicate=inspect.ismethod):
            method_name = m[0]
            if not method_name.startswith('_'):
                method = m[1]
                if method.__doc__ and not method.__doc__.startswith('HIDDEN'):
                    result[method_name] = method
        return result

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
                    self._user_io.out.success("Conan version %s" % CLIENT_VERSION)
                    return False
                self._show_help()
                if command in ["-h", "--help"]:
                    return False
                raise ConanException("Unknown command %s" % str(exc))
            except IndexError as exc:  # No parameters
                self._show_help()
                return False
            method(args[0][1:])
        except (KeyboardInterrupt, SystemExit) as exc:
            logger.error(exc)
            errors = True
        except ConanException as exc:
            msg = str(exc)
#             import traceback
#             logger.debug(traceback.format_exc())
            errors = True
            self._user_io.out.error(msg)

        return errors


def migrate_and_get_client_cache(base_folder, out, manager, storage_folder=None):
    # Init paths
    client_cache = ClientCache(base_folder, storage_folder, out)

    # Migration system
    migrator = ClientMigrator(client_cache, Version(CLIENT_VERSION), out, manager)
    migrator.migrate()

    # Init again paths, migration could change config
    client_cache = ClientCache(base_folder, storage_folder, out)
    return client_cache


def get_command():

    def instance_remote_manager(client_cache):
        requester = requests.Session()
        requester.proxies = client_cache.conan_config.proxies
        # Verify client version against remotes
        version_checker_requester = VersionCheckerRequester(requester, Version(CLIENT_VERSION),
                                                            Version(MIN_SERVER_COMPATIBLE_VERSION),
                                                            out)
        # To handle remote connections
        rest_api_client = RestApiClient(out, requester=version_checker_requester)
        # To store user and token
        localdb = LocalDB(client_cache.localdb)
        # Wraps RestApiClient to add authentication support (same interface)
        auth_manager = ConanApiAuthManager(rest_api_client, user_io, localdb)
        # Handle remote connections
        remote_manager = RemoteManager(client_cache, auth_manager, out)
        return remote_manager

    use_color = get_env("CONAN_COLOR_DISPLAY", 1)
    if use_color and hasattr(sys.stdout, "isatty") and sys.stdout.isatty():
        import colorama
        colorama.init()
        color = True
    else:
        color = False
    out = ConanOutput(sys.stdout, color)
    user_io = UserIO(out=out)

    user_folder = os.getenv("CONAN_USER_HOME", conan_expand_user("~"))

    try:
        # To capture exceptions in conan.conf parsing
        client_cache = ClientCache(user_folder, None, out)
        # obtain a temp ConanManager instance to execute the migrations
        remote_manager = instance_remote_manager(client_cache)

        # Get a DiskSearchManager
        search_adapter = DiskSearchAdapter()
        search_manager = DiskSearchManager(client_cache, search_adapter)
        manager = ConanManager(client_cache, user_io, ConanRunner(), remote_manager, search_manager)

        client_cache = migrate_and_get_client_cache(user_folder, out, manager)
    except Exception as e:
        out.error(str(e))
        sys.exit(True)

    # Get the new command instance after migrations have been done
    remote_manager = instance_remote_manager(client_cache)

    # Get a search manager
    search_adapter = DiskSearchAdapter()
    search_manager = DiskSearchManager(client_cache, search_adapter)
    command = Command(client_cache, user_io, ConanRunner(), remote_manager, search_manager)
    return command


def main(args):
    """ main entry point of the conan application, using a Command to
    parse parameters
    """
    command = get_command()
    current_dir = os.getcwd()
    try:
        import signal

        def sigint_handler(signal, frame):  # @UnusedVariable
            print('You pressed Ctrl+C!')
            sys.exit(0)

        signal.signal(signal.SIGINT, sigint_handler)
        error = command.run(args)
    finally:
        os.chdir(current_dir)
    sys.exit(error)
