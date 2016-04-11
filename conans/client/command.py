from conans.client.paths import ConanPaths
import sys
import os
from conans.client.output import ConanOutput, Color
import argparse
from conans.errors import ConanException
import inspect
from conans.client.remote_manager import RemoteManager
from conans.client.userio import UserIO
from conans.client.rest.auth_manager import ConanApiAuthManager
from conans.client.rest.rest_client import RestApiClient
from conans.client.store.localdb import LocalDB
from conans.util.log import logger
from conans.model.ref import ConanFileReference
from conans.client.manager import ConanManager
from conans.paths import CONANFILE
import requests
from conans.client.rest.version_checker import VersionCheckerRequester
from conans import __version__ as CLIENT_VERSION
from conans.client.conf import MIN_SERVER_COMPATIBLE_VERSION
from conans.model.version import Version
from conans.client.migrations import ClientMigrator
import hashlib
from conans.util.files import rmdir, load
from argparse import RawTextHelpFormatter
import re
from conans.client.runner import ConanRunner
from conans.client.remote_registry import RemoteRegistry


class Extender(argparse.Action):
    '''Allows to use the same flag several times in a command and creates a list with the values.
       For example:
           conans install OpenSSL/1.0.2e@lasote/stable -o qt:value -o mode:2 -s cucumber:true
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
    """ A single command of the conans application, with all the first level commands.
    Manages the parsing of parameters and delegates functionality in
    collaborators.
    It can also show help of the tool
    """
    def __init__(self, paths, user_io, runner, remote_manager):
        assert isinstance(user_io, UserIO)
        assert isinstance(paths, ConanPaths)
        self._conan_paths = paths
        self._user_io = user_io
        self._runner = runner
        self._manager = ConanManager(paths, user_io, runner, remote_manager)

    def _parse_args(self, parser):
        parser.add_argument("-r", "--remote", help='look for in the remote storage')
        parser.add_argument("--options", "-o",
                            help='load options to build the package, e.g., -o with_qt=true',
                            nargs=1, action=Extender)
        parser.add_argument("--settings", "-s",
                            help='load settings to build the package, -s compiler:gcc',
                            nargs=1, action=Extender)
        parser.add_argument("--build", "-b", action=Extender, nargs="*",
                            help='''Optional, use it to choose if you want to build from sources:

--build            Build all from sources, do not use binary packages.
--build=never      Default option. Never build, use binary packages or fail if a binary package is not found.
--build=missing    Build from code if a binary package is not found.
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

    def _detect_tested_library_name(self):
        conanfile_content = load(CONANFILE)
        match = re.search('^\s*name\s*=\s*"(.*)"', conanfile_content, re.MULTILINE)
        if match:
            return "%s*" % match.group(1)

        self._user_io.out.warn("Cannot detect a valid conanfile in current directory")
        return None

    def _get_build_sources_parameter(self, build_param):
        # returns True if we want to build the missing libraries
        #         False if building is forbidden
        #         A list with patterns: Will force build matching libraries,
        #                               will look for the package for the rest

        if isinstance(build_param, list):
            if len(build_param) == 0:  # All packages from source
                return ["*"]
            elif len(build_param) == 1 and build_param[0] == "never":
                return False  # Default
            elif len(build_param) == 1 and build_param[0] == "missing":
                return True
            else:  # A list of expressions to match (if matches, will build from source)
                return ["%s*" % ref_expr for ref_expr in build_param]
        else:
            return False  # Nothing is built

    def test(self, *args):
        """ build and run your package test. Must have conanfile.py with "test"
        method and "test" subfolder with package consumer test project
        """
        parser = argparse.ArgumentParser(description=self.test.__doc__, prog="conan test",
                                         formatter_class=RawTextHelpFormatter)
        parser.add_argument("path", nargs='?', default="", help='path to conanfile file, '
                            'e.g. /my_project/')
        parser.add_argument("-f", "--folder", help='alternative test folder name')
        self._parse_args(parser)

        args = parser.parse_args(*args)
        test_folder_name = args.folder or "test"

        root_folder = os.path.normpath(os.path.join(os.getcwd(), args.path))
        test_folder = os.path.join(root_folder, test_folder_name)
        if not os.path.exists(test_folder):
            raise ConanException("test folder not available")

        lib_to_test = self._detect_tested_library_name()

        # Get False or a list of patterns to check
        if args.build is None and lib_to_test:  # Not specified, force build the tested library
            args.build = [lib_to_test]
        else:
            args.build = self._get_build_sources_parameter(args.build)

        options = args.options or []
        settings = args.settings or []

        sha = hashlib.sha1("".join(options + settings).encode()).hexdigest()
        build_folder = os.path.join(test_folder, "build", sha)
        rmdir(build_folder)
        # shutil.copytree(test_folder, build_folder)

        options = self._get_tuples_list_from_extender_arg(args.options)
        settings = self._get_tuples_list_from_extender_arg(args.settings)

        self._manager.install(reference=test_folder,
                              current_path=build_folder,
                              remote=args.remote,
                              options=options,
                              settings=settings,
                              build_mode=args.build)
        self._manager.build(test_folder, build_folder, test=True)

    def install(self, *args):
        """ install in the local store the given requirements.
        Requirements can be defined in the command line or in a conanfile.
        EX: conans install opencv/2.4.10@lasote/testing
        """
        parser = argparse.ArgumentParser(description=self.install.__doc__, prog="conan install",
                                         formatter_class=RawTextHelpFormatter)
        parser.add_argument("reference", nargs='?', default="",
                            help='package recipe reference'
                            'e.g., OpenSSL/1.0.2e@lasote/stable or ./my_project/')
        parser.add_argument("--package", "-p", nargs=1, action=Extender,
                            help='Force install specified package ID (ignore settings/options)')
        parser.add_argument("--all", action='store_true', default=False,
                            help='Install all packages from the specified package recipe')
        parser.add_argument("--file", "-f", help="specify conanfile filename")
        parser.add_argument("--update", "-u", action='store_true', default=False,
                            help="update with new upstream packages")
        self._parse_args(parser)

        args = parser.parse_args(*args)

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
                                     "e.g., OpenSSL/1.0.2e@lasote/stable")
            self._manager.download(reference, args.package, remote=args.remote)
        else:  # Classic install, package chosen with settings and options
            # Get False or a list of patterns to check
            args.build = self._get_build_sources_parameter(args.build)
            options = self._get_tuples_list_from_extender_arg(args.options)
            settings = self._get_tuples_list_from_extender_arg(args.settings)

            self._manager.install(reference=reference,
                                  current_path=current_path,
                                  remote=args.remote,
                                  options=options,
                                  settings=settings,
                                  build_mode=args.build,
                                  filename=args.file,
                                  update=args.update)

    def info(self, *args):
        """ Prints information about the requirements.
        Requirements can be defined in the command line or in a conanfile.
        EX: conans info opencv/2.4.10@lasote/testing
        """
        parser = argparse.ArgumentParser(description=self.info.__doc__, prog="conan info",
                                         formatter_class=RawTextHelpFormatter)
        parser.add_argument("reference", nargs='?', default="",
                            help='reference name or path to conanfile file, '
                            'e.g., OpenSSL/1.0.2e@lasote/stable or ./my_project/')
        parser.add_argument("--file", "-f", help="specify conanfile filename")
        parser.add_argument("-r", "--remote", help='look for in the remote storage')
        parser.add_argument("--options", "-o",
                            help='load options to build the package, e.g., -o with_qt=true',
                            nargs=1, action=Extender)
        parser.add_argument("--settings", "-s",
                            help='load settings to build the package, -s compiler:gcc',
                            nargs=1, action=Extender)

        args = parser.parse_args(*args)

        options = self._get_tuples_list_from_extender_arg(args.options)
        settings = self._get_tuples_list_from_extender_arg(args.settings)
        current_path = os.getcwd()
        try:
            reference = ConanFileReference.loads(args.reference)
        except:
            reference = os.path.normpath(os.path.join(current_path, args.reference))

        self._manager.install(reference=reference,
                              current_path=current_path,
                              remote=args.remote,
                              options=options,
                              settings=settings,
                              build_mode=False,
                              info=True,
                              filename=args.file)

    def build(self, *args):
        """ calls your project conanfile.py "build" method.
            EX: conans build ./my_project
            Intended for package creators, requires a conanfile.py.
        """
        parser = argparse.ArgumentParser(description=self.build.__doc__, prog="conan build")
        parser.add_argument("path", nargs="?",
                            help='path to user conanfile.py, e.g., conans build .',
                            default="")
        parser.add_argument("--file", "-f", help="specify conanfile filename")
        args = parser.parse_args(*args)
        current_path = os.getcwd()
        if args.path:
            root_path = os.path.abspath(args.path)
        else:
            root_path = current_path
        self._manager.build(root_path, current_path, filename=args.file)

    def package(self, *args):
        """ calls your conanfile.py "package" method for a specific package or
            regenerates the existing package's manifest.
            Intended for package creators, for regenerating a package without
            recompiling the source.
            e.g. conan package OpenSSL/1.0.2e@lasote/stable 9cf83afd07b678da9c1645f605875400847ff3
        """
        parser = argparse.ArgumentParser(description=self.package.__doc__, prog="conan package")
        parser.add_argument("reference", help='package recipe reference name. e.g., openssl/1.0.2@lasote/testing')
        parser.add_argument("package", nargs="?", default="",
                            help='Package ID to regenerate. e.g., '
                                 '9cf83afd07b678d38a9c1645f605875400847ff3')
        parser.add_argument("-o", "--only-manifest", default=False, action='store_true',
                            help='Just regenerate manifest for the existing package.'
                                 'If True conan won\'t call your conanfile\'s package method.')
        parser.add_argument("--all", action='store_true',
                            default=False, help='Package all packages from specified reference')

        args = parser.parse_args(*args)

        try:
            reference = ConanFileReference.loads(args.reference)
        except:
            raise ConanException("Invalid package recipe reference. e.g., OpenSSL/1.0.2e@lasote/stable")

        if not args.all and not args.package:
            raise ConanException("'conan package': Please specify --all or a package ID")

        self._manager.package(reference, args.package, args.only_manifest, args.all)

    def export(self, *args):
        """ copies the package recipe (conanfile.py and associated files) to your local store,
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

        current_path = args.path or os.getcwd()
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
                            'e.g., OpenSSL/1.0.2e@lasote/stable')
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
        args = parser.parse_args(*parameters)  # To enable -h
        self._manager.user(args.remote, args.name, args.password)

    def search(self, *args):
        """ show local/remote packages
        """
        parser = argparse.ArgumentParser(description=self.search.__doc__, prog="conan search")
        parser.add_argument('pattern', nargs='?', help='Pattern name, e.g., openssl/*')
        parser.add_argument('--case-sensitive', default=False,
                            action='store_true', help='Make a case-sensitive search')
        parser.add_argument('-r', '--remote', help='Remote origin')
        parser.add_argument('-v', '--verbose', default=False,
                            action='store_true', help='Show packages')
        parser.add_argument('-x', '--extra-verbose', default=False,
                            action='store_true', help='Show packages options and settings')
        parser.add_argument('-p', '--package', help='Package ID pattern. EX: 23*', default=None)
        args = parser.parse_args(*args)

        self._manager.search(args.pattern,
                             args.remote,
                             ignorecase=not args.case_sensitive,
                             verbose=args.verbose,
                             extra_verbose=args.extra_verbose,
                             package_pattern=args.package)

    def upload(self, *args):
        """ uploads a conanfile or binary packages from the local store to any remote.
        To upload something, it should be "exported" first.
        """
        parser = argparse.ArgumentParser(description=self.upload.__doc__,
                                         prog="conan upload")
        parser.add_argument("reference",
                            help='package recipe reference, e.g., OpenSSL/1.0.2e@lasote/stable')
        # TODO: packageparser.add_argument('package', help='user name')
        parser.add_argument("--package", "-p", default=None, help='package ID to upload')
        parser.add_argument("--remote", "-r", help='upload to this specific remote')
        parser.add_argument("--all", action='store_true',
                            default=False, help='Upload both package recipe and packages')
        parser.add_argument("--force", action='store_true',
                            default=False,
                            help='Do not check conans date, override remote with local')

        args = parser.parse_args(*args)

        conan_ref = ConanFileReference.loads(args.reference)
        package_id = args.package

        if not conan_ref and not package_id:
            raise ConanException("Enter conans or package id")

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
        parser_rm = subparsers.add_parser('remove', help='remove a remote')
        parser_rm.add_argument('remote',  help='name of the remote')
        parser_upd = subparsers.add_parser('update', help='update the remote url')
        parser_upd.add_argument('remote',  help='name of the remote')
        parser_upd.add_argument('url',  help='url')
        subparsers.add_parser('list_ref', help='list the package recipes and its associated remotes')
        parser_padd = subparsers.add_parser('add_ref', help="associate a recipe's reference to a remote")
        parser_padd.add_argument('reference',  help='package recipe reference')
        parser_padd.add_argument('remote',  help='name of the remote')
        parser_prm = subparsers.add_parser('remove_ref', help="dissociate a recipe's reference and its remote")
        parser_prm.add_argument('reference',  help='package recipe reference')
        parser_pupd = subparsers.add_parser('update_ref', help="update the remote associated with a package recipe")
        parser_pupd.add_argument('reference',  help='package recipe reference')
        parser_pupd.add_argument('remote',  help='name of the remote')
        args = parser.parse_args(*args)

        registry = RemoteRegistry(self._conan_paths.registry, self._user_io.out)
        if args.subcommand == "list":
            for r in registry.remotes:
                self._user_io.out.info("%s: %s" % (r.name, r.url))
        elif args.subcommand == "add":
            registry.add(args.remote, args.url)
        elif args.subcommand == "remove":
            registry.remove(args.remote)
        elif args.subcommand == "update":
            registry.update(args.remote, args.url)
        elif args.subcommand == "list_ref":
            for ref, remote in registry.refs.items():
                self._user_io.out.info("%s: %s" % (ref, remote))
        elif args.subcommand == "add_ref":
            registry.add_ref(args.reference, args.remote)
        elif args.subcommand == "remove_ref":
            registry.remove_ref(args.reference)
        elif args.subcommand == "update_ref":
            registry.update_ref(args.reference, args.remote)

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
            logger.error(exc)
#             import traceback
#             logger.debug(traceback.format_exc())
            errors = True
            self._user_io.out.error(str(exc))

        return errors


def migrate_and_get_paths(base_folder, out, manager, storage_folder=None):
    # Init paths
    paths = ConanPaths(base_folder, storage_folder, out)

    # Migration system
    migrator = ClientMigrator(paths, Version(CLIENT_VERSION), out, manager)
    migrator.migrate()

    # Init again paths, migration could change config
    paths = ConanPaths(base_folder, storage_folder, out)
    return paths


def get_command():

    def instance_remote_manager(paths):
        requester = requests.Session()
        requester.proxies = paths.conan_config.proxies
        # Verify client version against remotes
        version_checker_requester = VersionCheckerRequester(requester, Version(CLIENT_VERSION),
                                                            Version(MIN_SERVER_COMPATIBLE_VERSION),
                                                            out)
        # To handle remote connections
        rest_api_client = RestApiClient(out, requester=version_checker_requester)
        # To store user and token
        localdb = LocalDB(paths.localdb)
        # Wraps RestApiClient to add authentication support (same interface)
        auth_manager = ConanApiAuthManager(rest_api_client, user_io, localdb)
        # Handle remote connections
        remote_manager = RemoteManager(paths, auth_manager, out)
        return remote_manager

    if hasattr(sys.stdout, "isatty") and sys.stdout.isatty():
        import colorama
        colorama.init()
        color = True
    else:
        color = False
    out = ConanOutput(sys.stdout, color)
    user_io = UserIO(out=out)

    user_folder = os.getenv("CONAN_USER_HOME", os.path.expanduser("~"))
    try:
        # To capture exceptions in conan.conf parsing
        paths = ConanPaths(user_folder, None, out)
        # obtain a temp ConanManager instance to execute the migrations
        remote_manager = instance_remote_manager(paths)
        manager = ConanManager(paths, user_io, ConanRunner(), remote_manager)
        paths = migrate_and_get_paths(user_folder, out, manager)
    except Exception as e:
        out.error(str(e))
        sys.exit(True)

    # Get the new command instance after migrations have been done
    manager = instance_remote_manager(paths)
    command = Command(paths, user_io, ConanRunner(), manager)
    return command


def main(args):
    """ main entry point of the conans application, using a Command to
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
