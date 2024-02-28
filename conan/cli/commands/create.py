import os
import shutil
import json
from io import BytesIO

from conan.api.output import ConanOutput
from conan.cli.args import add_lockfile_args, add_common_install_arguments
from conan.cli.command import conan_command, OnceArgument
from conan.cli.commands.export import common_args_export
from conan.cli.formatters.graph import format_graph_json
from conan.cli.printers import print_profiles
from conan.cli.printers.graph import print_graph_packages, print_graph_basic
from conan.errors import ConanException
from conans.client.graph.graph import BINARY_BUILD
from conans.util.files import mkdir
from conan.api.model import ListPattern
from conan.api.conan_api import ConfigAPI


@conan_command(group="Creator", formatters={"json": format_graph_json})
def create(conan_api, parser, *args):
    """
    Create a package.
    """
    common_args_export(parser)
    add_lockfile_args(parser)
    add_common_install_arguments(parser)
    parser.add_argument("--build-require", action='store_true', default=False,
                        help='Whether the package being created is a build-require (to be used'
                             ' as tool_requires() by other packages)')
    parser.add_argument("-tf", "--test-folder", action=OnceArgument,
                        help='Alternative test folder name. By default it is "test_package". '
                             'Use "" to skip the test stage')
    parser.add_argument("-tm", "--test-missing", action='store_true', default=False,
                        help='Run the test_package checks only if the package is built from source'
                             ' but not if it already existed (using --build=missing)')
    parser.add_argument("-bt", "--build-test", action="append",
                        help="Same as '--build' but only for the test_package requires. By default"
                             " if not specified it will take the '--build' value if specified")
    raw_args = args[0]
    args = parser.parse_args(*args)

    if args.test_missing and args.test_folder == "":
        raise ConanException('--test-folder="" is incompatible with --test-missing')

    cwd = os.getcwd()
    path = conan_api.local.get_conanfile_path(args.path, cwd, py=True)
    overrides = eval(args.lockfile_overrides) if args.lockfile_overrides else None
    lockfile = conan_api.lockfile.get_lockfile(lockfile=args.lockfile,
                                               conanfile_path=path,
                                               cwd=cwd,
                                               partial=args.lockfile_partial,
                                               overrides=overrides)
    remotes = conan_api.remotes.list(args.remote) if not args.no_remote else []
    profile_host, profile_build = conan_api.profiles.get_profiles_from_args(args)

    ref, conanfile = conan_api.export.export(path=path,
                                             name=args.name, version=args.version,
                                             user=args.user, channel=args.channel,
                                             lockfile=lockfile,
                                             remotes=remotes)

    # FIXME: Dirty: package type still raw, not processed yet
    is_build = args.build_require or conanfile.package_type == "build-scripts"
    # The package_type is not fully processed at export
    is_python_require = conanfile.package_type == "python-require"
    lockfile = conan_api.lockfile.update_lockfile_export(lockfile, conanfile, ref, is_build)

    print_profiles(profile_host, profile_build)
    if not os.environ.get("CONAN_REMOTE_ENVIRONMNET") and (profile_host.remote and profile_host.remote.get('remote') == 'docker'):
        return _docker_runner(conan_api, profile_host, args, raw_args)


    if args.build is not None and args.build_test is None:
        args.build_test = args.build

    if is_python_require:
        deps_graph = conan_api.graph.load_graph_requires([], [],
                                                         profile_host=profile_host,
                                                         profile_build=profile_build,
                                                         lockfile=lockfile,
                                                         remotes=remotes, update=args.update,
                                                         python_requires=[ref])
    else:
        requires = [ref] if not is_build else None
        tool_requires = [ref] if is_build else None
        deps_graph = conan_api.graph.load_graph_requires(requires, tool_requires,
                                                         profile_host=profile_host,
                                                         profile_build=profile_build,
                                                         lockfile=lockfile,
                                                         remotes=remotes, update=args.update)
        print_graph_basic(deps_graph)
        deps_graph.report_graph_error()

        # Not specified, force build the tested library
        build_modes = [ref.repr_notime()] if args.build is None else args.build
        if args.build is None and conanfile.build_policy == "never":
            raise ConanException(
                "This package cannot be created, 'build_policy=never', it can only be 'export-pkg'")
        conan_api.graph.analyze_binaries(deps_graph, build_modes, remotes=remotes,
                                         update=args.update, lockfile=lockfile)
        print_graph_packages(deps_graph)

        conan_api.install.install_binaries(deps_graph=deps_graph, remotes=remotes)
        # We update the lockfile, so it will be updated for later ``test_package``
        lockfile = conan_api.lockfile.update_lockfile(lockfile, deps_graph, args.lockfile_packages,
                                                      clean=args.lockfile_clean)

    test_package_folder = getattr(conanfile, "test_package_folder", None) \
        if args.test_folder is None else args.test_folder
    test_conanfile_path = _get_test_conanfile_path(test_package_folder, path)
    # If the user provide --test-missing and the binary was not built from source, skip test_package
    if args.test_missing and deps_graph.root.dependencies\
            and deps_graph.root.dependencies[0].dst.binary != BINARY_BUILD:
        test_conanfile_path = None  # disable it

    if test_conanfile_path:
        # TODO: We need arguments for:
        #  - decide update policy "--test_package_update"
        # If it is a string, it will be injected always, if it is a RecipeReference, then it will
        # be replaced only if ``python_requires = "tested_reference_str"``
        tested_python_requires = ref.repr_notime() if is_python_require else ref
        from conan.cli.commands.test import run_test
        # The test_package do not make the "conan create" command return a different graph or
        # produce a different lockfile. The result is always the same, irrespective of test_package
        run_test(conan_api, test_conanfile_path, ref, profile_host, profile_build, remotes, lockfile,
                 update=None, build_modes=args.build, build_modes_test=args.build_test,
                 tested_python_requires=tested_python_requires, tested_graph=deps_graph)

    conan_api.lockfile.save_lockfile(lockfile, args.lockfile_out, cwd)
    return {"graph": deps_graph,
            "conan_api": conan_api}


def _check_tested_reference_matches(deps_graph, tested_ref, out):
    """ Check the test_profile_override_conflict test. If we are testing a build require
    but we specify the build require with a different version in the profile, it has priority,
    it is correct but weird and likely a mistake"""
    # https://github.com/conan-io/conan/issues/10453
    direct_refs = [n.conanfile.ref for n in deps_graph.root.neighbors()]
    # There is a reference with same name but different
    missmatch = [ref for ref in direct_refs if ref.name == tested_ref.name and ref != tested_ref]
    if missmatch:
        out.warning("The package created was '{}' but the reference being "
                    "tested is '{}'".format(missmatch[0], tested_ref))


def test_package(conan_api, deps_graph, test_conanfile_path):
    out = ConanOutput()
    out.title("Testing the package")
    # TODO: Better modeling when we are testing a python_requires
    conanfile = deps_graph.root.conanfile
    if len(deps_graph.nodes) == 1 and not hasattr(conanfile, "python_requires"):
        raise ConanException("The conanfile at '{}' doesn't declare any requirement, "
                             "use `self.tested_reference_str` to require the "
                             "package being created.".format(test_conanfile_path))
    conanfile_folder = os.path.dirname(test_conanfile_path)
    # To make sure the folders are correct
    conanfile.folders.set_base_folders(conanfile_folder, output_folder=None)
    if conanfile.build_folder and conanfile.build_folder != conanfile.source_folder:
        # should be the same as build folder, but we can remove it
        out.info("Removing previously existing 'test_package' build folder: "
                 f"{conanfile.build_folder}")
        shutil.rmtree(conanfile.build_folder, ignore_errors=True)
        mkdir(conanfile.build_folder)
    conanfile.output.info(f"Test package build: {conanfile.folders.build}")
    conanfile.output.info(f"Test package build folder: {conanfile.build_folder}")
    conan_api.install.install_consumer(deps_graph=deps_graph,
                                       source_folder=conanfile_folder)

    out.title("Testing the package: Building")
    conan_api.local.build(conanfile)

    out.title("Testing the package: Executing test")
    conanfile.output.highlight("Running test()")
    conan_api.local.test(conanfile)


def _get_test_conanfile_path(tf, conanfile_path):
    """Searches in the declared test_folder or in the standard "test_package"
    """
    if tf == "":  # Now if parameter --test-folder="" we have to skip tests
        return None
    base_folder = os.path.dirname(conanfile_path)
    test_conanfile_path = os.path.join(base_folder, tf or "test_package", "conanfile.py")
    if os.path.exists(test_conanfile_path):
        return test_conanfile_path
    elif tf:
        raise ConanException(f"test folder '{tf}' not available, or it doesn't have a conanfile.py")


def _docker_runner(conan_api, profile, args, raw_args):
    """
    run conan inside a Docker continer
    """
    # import docker only if needed
    import docker
    docker_client = docker.from_env()
    docker_api = docker.APIClient()
    dockerfile = str(profile.remote.get('dockerfile', ''))
    image = str(profile.remote.get('image', 'conanremote'))

    remote_home = os.path.join(args.path, '.conanremote')
    tgz_path = os.path.join(remote_home, 'conan_cache_save.tgz')
    volumes = {
        args.path: {'bind': args.path, 'mode': 'rw'}
    }

    environment = {
        'CONAN_REMOTE_WS': args.path,
        'CONAN_REMOTE_COMMAND': ' '.join(['conan create'] + raw_args),
        'CONAN_REMOTE_ENVIRONMNET': '1'
    }
    # https://docker-py.readthedocs.io/en/stable/api.html#module-docker.api.build

    ConanOutput().info(msg=f'\nBuilding the Docker image: {image}')
    docker_build_logs = None
    if dockerfile:
        docker_build_logs = docker_api.build(path=dockerfile, tag=image)
    else:
        dockerfile = '''
FROM ubuntu
RUN apt update && apt upgrade -y
RUN apt install -y build-essential
RUN apt install -y python3-pip cmake git
RUN cd /root && git clone https://github.com/davidsanfal/conan.git conan-io
RUN cd /root/conan-io && pip install -e .
'''
        docker_build_logs = docker_api.build(fileobj=BytesIO(dockerfile.encode('utf-8')), tag=image)
    for chunk in docker_build_logs:
        for line in chunk.decode("utf-8").split('\r\n'):
            if line:
                stream = json.loads(line).get('stream')
                if stream:
                    ConanOutput().info(stream.strip())

    shutil.rmtree(remote_home, ignore_errors=True)
    os.mkdir(remote_home)
    conan_api.cache.save(conan_api.list.select(ListPattern("*")), tgz_path)
    shutil.copytree(os.path.join(ConfigAPI(conan_api).home(), 'profiles'), os.path.join(remote_home, 'profiles'))
    with open(os.path.join(remote_home, 'conan-remote-init.sh'), 'w+') as f:
        f.writelines("""#!/bin/bash

conan cache restore ${CONAN_REMOTE_WS}/.conanremote/conan_cache_save.tgz
mkdir ${HOME}/.conan2/profiles
cp -r ${CONAN_REMOTE_WS}/.conanremote/profiles/. -r ${HOME}/.conan2/profiles/.

echo "Running: ${CONAN_REMOTE_COMMAND}"
eval "${CONAN_REMOTE_COMMAND}"

conan cache save "*" --file ${CONAN_REMOTE_WS}/.conanremote/conan_cache_docker.tgz""")

    # Init docker python api
    ConanOutput().info(msg=f'\Running the Docker container\n')
    container = docker_client.containers.run(image,
                                             f'/bin/bash {os.path.join(remote_home, "conan-remote-init.sh")}',
                                             volumes=volumes,
                                             environment=environment,
                                             detach=True)
    for line in container.attach(stdout=True, stream=True, logs=True):
        ConanOutput().info(line.decode('utf-8', errors='ignore').strip())
    container.wait()
    container.stop()
    container.remove()

    tgz_path = os.path.join(remote_home, 'conan_cache_docker.tgz')
    ConanOutput().info(f'New cache path: {tgz_path}')
    package_list = conan_api.cache.restore(tgz_path)
    return {"graph": {},
            "conan_api": conan_api}
