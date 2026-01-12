import os
import re

from conan.api.conan_api import ConanAPI
from conan.api.model import ListPattern, RecipeReference
from conan.api.output import ConanOutput
from conan.cli.command import conan_command, conan_subcommand
from conan.internal.util.files import save, load


@conan_subcommand()
def dep_remove(conan_api, parser, subparser, *args):
    """
    Removes a requirement from your local conanfile.
    """
    subparser.add_argument("path", default=".", nargs="?",
                        help="Path to a folder containing a recipe (conanfile.py). "
                             "Defaults to current directory")
    subparser.add_argument("name", help="Dependency name.")
    subparser.add_argument("-to", "--tool-requires", action="store_true",
                           help="It is a tool requirement.")
    subparser.add_argument("-te", "--test-requires", action="store_true",
                           help="It is a test requirement.")
    args = parser.parse_args(*args)
    name = args.name
    path = conan_api.local.get_conanfile_path(args.path, os.getcwd(), py=None)
    # Check if that requirement exists in the conanfile. If yes, abort.
    conanfile = load(path)
    ConanOutput().debug(f"Loaded conanfile from {path}.")
    if args.tool_requires:
        req_attr = "tool_requires"
        req_func = "build_requirements"
    elif args.test_requires:
        req_attr = "test_requires"
        req_func = "build_requirements"
    else:
        req_attr = "requires"
        req_func = "requirements"
    if not re.search(rf"self\.{req_attr}\([\"']{name}", conanfile):
        ConanOutput().warning(f"The {req_func} {name} is not declared in your conanfile.")
        return
    # Replace the whole line
    conanfile = re.sub(rf"^\s*self\.{req_attr}\([\"']{name}.*\n?", '',
                       conanfile, flags=re.MULTILINE)
    save(path, conanfile)
    ConanOutput().success(f"Removed {name} dependency as {req_attr}.")


@conan_subcommand()
def dep_add(conan_api, parser, subparser, *args):
    """
    Add a new requirement to your local conanfile as a version range.
    By default, it will look for the requirement versions remotely.
    """
    subparser.add_argument("path", default=".", nargs="?",
                        help="Path to a folder containing a recipe (conanfile.py). "
                             "Defaults to current directory",)
    subparser.add_argument("name", help="Dependency name.")
    subparser.add_argument("-to", "--tool-requires", action="store_true",
                           help="It is a tool requirement.")
    subparser.add_argument("-te", "--test-requires", action="store_true",
                           help="It is a test requirement.")
    group = subparser.add_mutually_exclusive_group()
    group.add_argument("-r", "--remote", default=None, action="append",
                       help="Remote names. Accepts wildcards ('*' means all the remotes available)")
    group.add_argument("-nr", "--no-remote", action="store_true",
                       help='Do not use remote, resolve exclusively in the cache')
    args = parser.parse_args(*args)
    name = args.name
    path = conan_api.local.get_conanfile_path(args.path, os.getcwd(), py=None)
    remotes = conan_api.remotes.list(args.remote) if not args.no_remote else [None]
    # Check if that requirement exists in the conanfile. If yes, abort.
    conanfile = load(path)
    ConanOutput().debug(f"Loaded conanfile from {path}.")
    if args.tool_requires:
        req_attr = "tool_requires"
        req_func = "build_requirements"
    elif args.test_requires:
        req_attr = "test_requires"
        req_func = "build_requirements"
    else:
        req_attr = "requires"
        req_func = "requirements"
    if re.search(rf"self\.{req_attr}\([\"']{name}", conanfile):
        ConanOutput().warning(f"The {req_func} {name} is already in use.")
        return
    # Search the latest version in remotes/cache
    ref_pattern = ListPattern(f"{name}/*")
    # If neither remote nor cache are defined, show results only from cache
    results = {}
    for remote in remotes:
        try:
            pkglist = conan_api.list.select(ref_pattern, remote=remote)
        except Exception as e:
            remote_name = "Cache" if remote is None else remote.name
            ConanOutput().warning(f"[{remote_name}] {str(e)}")
        else:
            results = pkglist.serialize()
            if results:
                break
    if not results:
        ConanOutput().error(f"Recipe {name} not found.")
        return
    # Put the upper limit for that requirement (next major version)
    reference = RecipeReference.loads(results.popitem()[0])
    version_range = f"{reference.name}/[^{reference.version}]"
    full_version_range = f'self.{req_attr}("{version_range}")'
    if full_version_range:
        tab_space = " " * 4
        if f"def {req_func}(" in conanfile:
            conanfile = conanfile.replace(f"def {req_func}(self):\n",
                                          f"def {req_func}(self):\n{tab_space * 2}{full_version_range}\n")
        else:
            requirements_func = f"\n{tab_space}def {req_func}(self):\n{tab_space * 2}{full_version_range}\n"
            conanfile += requirements_func
    save(path, conanfile)
    ConanOutput().success(f"Added '{version_range}' as a new {req_attr}.")


@conan_command(group="Consumer")
def dep(conan_api: ConanAPI, parser, *args):
    """
    Adds/removes requirements to/from your local conanfile.
    """
