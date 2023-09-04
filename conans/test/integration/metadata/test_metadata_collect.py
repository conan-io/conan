import os
import shutil
import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient
from conans.util.files import save

# TODO: Simplify API for simpler command
collect = '''\
import os, shutil, glob
from conan.errors import ConanException
from conan.cli.command import conan_command
from conan.api.output import ConanOutput
from conans.client.graph.install_graph import InstallGraph
from conan.cli import make_abs_path
from conan.cli.args import common_graph_args, validate_common_graph_args
from conan.cli.command import conan_command
from conan.cli.formatters.graph import format_graph_json
from conan.cli.printers import print_profiles
from conan.cli.printers.graph import print_graph_packages, print_graph_basic


@conan_command(group="Metadata")
def collect(conan_api, parser, *args):
    """
    command to advanced metadata
    """
    common_graph_args(parser)
    parser.add_argument("-m", "--metadata", action='append',
                        help='Download the metadata matching the pattern, even if the package is '
                             'already in the cache and not downloaded')
    parser.add_argument("-mr", "--metadata-remote", help='Download the metadata from this remote')
    parser.add_argument("-of", "--output-folder", help='The root output folder for metadata')
    args = parser.parse_args(*args)
    validate_common_graph_args(args)
    cwd = os.getcwd()

    if args.path:
        path = conan_api.local.get_conanfile_path(args.path, cwd, py=None)
        source_folder = os.path.dirname(path)
    else:
        source_folder = cwd
        path = None

    output_folder = None
    metadata = args.metadata if args.metadata else ["*"]

    # Basic collaborators, remotes, lockfile, profiles
    remotes = conan_api.remotes.list(args.remote) if not args.no_remote else []
    lockfile = conan_api.lockfile.get_lockfile(lockfile=args.lockfile, conanfile_path=path,
                                               cwd=cwd, partial=args.lockfile_partial)
    profile_host, profile_build = conan_api.profiles.get_profiles_from_args(args)
    print_profiles(profile_host, profile_build)
    if path:
        deps_graph = conan_api.graph.load_graph_consumer(path, args.name, args.version,
                                                         args.user, args.channel,
                                                         profile_host, profile_build, lockfile,
                                                         remotes, args.update,
                                                         is_build_require=args.build_require)
    else:
        deps_graph = conan_api.graph.load_graph_requires(args.requires, args.tool_requires,
                                                         profile_host, profile_build, lockfile,
                                                         remotes, args.update)
    print_graph_basic(deps_graph)
    deps_graph.report_graph_error()
    conan_api.graph.analyze_binaries(deps_graph, args.build, remotes=remotes, update=args.update,
                                     lockfile=lockfile)
    print_graph_packages(deps_graph)

    out = ConanOutput()
    conan_api.install.install_binaries(deps_graph=deps_graph, remotes=remotes)

    install_graph = InstallGraph(deps_graph)
    install_order = install_graph.install_order(by_levels=False)

    if args.metadata_remote:
        out.title(f"Downloading metadata from {args.metadata_remote}")
        remote = conan_api.remotes.get(args.metadata_remote)

        for install_reference in install_order:
            if install_reference.ref.revision is None:  # Is an editable, do not download
                continue
            try:
                conan_api.download.recipe(install_reference.ref, remote, metadata)
            except ConanException as e:
                out.warning(f"Recipe {install_reference.ref} not found in remote: {e}")
            for package in install_reference.packages.values():
                node = package.nodes[0]
                try:
                    conan_api.download.package(node.pref, remote, metadata)
                except ConanException as e:
                    out.warning(f"Package {node.pref} not found in remote: {e}")

    # Copying and collecting metadata from all packages into local copy
    def _copy_metadata(src, dst):
        os.makedirs(dst, exist_ok=True)
        for root, dirs, files in os.walk(src):

        all_files = glob.glob(os.path.join(src, "**/*"), recursive=True)
        print("ALL FILES", all_files)
        for m in metadata:
            print("PATTERN ", m)
            files = glob.glob(os.path.join(src, "**"), recursive=True)
            print("FILES: ", files)
            for f in files:
                print("F: ", f)
                shutil.copy2(f, dst)

    output_folder = args.output_folder or os.path.join(os.getcwd(), "metadata")
    for install_reference in install_order:
        conanfile = install_reference.node.conanfile
        folder = os.path.join(output_folder, conanfile.ref.name, str(conanfile.ref.version))
        if os.path.exists(folder):
            conanfile.output.warning(f"Folder for {conanfile} already exist, removing it: {folder}")
            shutil.rmtree(folder)
        conanfile.output.info(f"Copying recipe metadata from {conanfile.recipe_metadata_folder}")
        _copy_metadata(conanfile.recipe_metadata_folder, os.path.join(folder, "recipe"))
        for package in install_reference.packages.values():
            pkg_metadata_folder = package.nodes[0].conanfile.package_metadata_folder
            conanfile.output.info(f"Copying package metadata from {pkg_metadata_folder}")
            _copy_metadata(pkg_metadata_folder, os.path.join(folder, "package"))
'''


def test_custom_command_collect_no_metadata():
    c = TestClient(default_server_user=True)
    command_file_path = os.path.join(c.cache_folder, 'extensions',
                                     'commands', 'metadata', 'cmd_collect.py')
    save(command_file_path, collect)
    c.save({"dep/conanfile.py": GenConanfile("dep", "0.1"),
            "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_requires("dep/0.1")})
    c.run("create dep")
    c.run("create pkg")
    c.run("metadata:collect --requires=pkg/0.1 --metadata=* --metadata-remote=default")
    # It does nothing, but it doesn't crash

    c.run("upload * -r=default -c")
    c.run("metadata:collect --requires=pkg/0.1 --metadata=* --metadata-remote=default")
    # It does nothing, but it doesn't crash

    c.run("editable add dep")
    c.run("metadata:collect --requires=pkg/0.1 --metadata=* --metadata-remote=default")
    # It does nothing, but it doesn't crash


conanfile = textwrap.dedent("""
    import os
    from conan import ConanFile
    from conan.tools.files import save, copy

    class Pkg(ConanFile):
        name = "{name}"
        version = "0.1"
        {requires}

        def source(self):
            save(self, os.path.join(self.recipe_metadata_folder, "logs", "src.log"),
                 f"srclog {{self.name}}!!")

        def build(self):
            save(self, "mylogs.txt", f"some logs {{self.name}}!!!")
            copy(self, "mylogs.txt", src=self.build_folder,
                 dst=os.path.join(self.package_metadata_folder, "logs"))
    """)


def test_custom_command_collect():
    c = TestClient(default_server_user=True)
    command_file_path = os.path.join(c.cache_folder, 'extensions',
                                     'commands', 'metadata', 'cmd_collect.py')
    save(command_file_path, collect)
    c.save({"dep/conanfile.py": conanfile.format(name="dep", requires=""),
            "pkg/conanfile.py": conanfile.format(name="pkg", requires='requires = "dep/0.1"')})
    c.run("create dep")
    c.run("create pkg")
    c.run("metadata:collect --requires=pkg/0.1 --metadata=* --metadata-remote=default")
    # It does nothing, but it doesn't crash
    assert "srclog dep!!" in c.load("metadata/dep/0.1/recipe/logs/src.log")
    assert "some logs dep!!!" in c.load("metadata/dep/0.1/package/logs/mylogs.txt")
    assert "srclog pkg!!" in c.load("metadata/pkg/0.1/recipe/logs/src.log")
    assert "some logs pkg!!!" in c.load("metadata/pkg/0.1/package/logs/mylogs.txt")

    shutil.rmtree(os.path.join(c.current_folder, "metadata"))

    c.run("upload * -r=default -c")
    c.run("remove * -c")
    c.run("metadata:collect --requires=pkg/0.1 --metadata=* --metadata-remote=default")
    assert "srclog dep!!" in c.load("metadata/dep/0.1/recipe/logs/src.log")
    assert "some logs dep!!!" in c.load("metadata/dep/0.1/package/logs/mylogs.txt")
    assert "srclog pkg!!" in c.load("metadata/pkg/0.1/recipe/logs/src.log")
    assert "some logs pkg!!!" in c.load("metadata/pkg/0.1/package/logs/mylogs.txt")
