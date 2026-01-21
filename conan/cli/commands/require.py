import os
import re

from conan.api.conan_api import ConanAPI
from conan.api.model import ListPattern, RecipeReference
from conan.api.output import ConanOutput
from conan.cli.command import conan_command, conan_subcommand
from conan.errors import ConanException
from conan.internal.util.files import save, load


@conan_subcommand()
def require_remove(conan_api, parser, subparser, *args):
    """
    Removes a requirement from your local conanfile.
    """
    subparser.add_argument("--folder",
                           help="Path to a folder containing a recipe (conanfile.py). "
                                "Defaults to the current directory",)
    subparser.add_argument("requires", nargs="*", help="Requirement name.")
    subparser.add_argument("-tor", "--tool", action="append", default=[],
                           help="Tool requirement name.")
    subparser.add_argument("-ter", "--test", action="append", default=[],
                           help="Test requirement name.")
    args = parser.parse_args(*args)
    path = conan_api.local.get_conanfile_path(args.folder or '.', os.getcwd(), py=True)
    # Check if that requirement exists in the conanfile. If yes, abort.
    conanfile = load(path)
    ConanOutput().debug(f"Loaded conanfile from {path}.")
    requires = [(r, "requires") for r in args.requires]
    tool_requires = [(r, "tool_requires") for r in args.tool]
    test_requires = [(r, "test_requires") for r in args.test]
    success_msgs = []
    for (name, req_attr) in requires + tool_requires + test_requires:
        if not re.search(rf"self\.{req_attr}\([\"']{name}", conanfile):
            ConanOutput().warning(f"The {req_attr} {name} is not declared in your conanfile.")
            continue
        # Replace the whole line
        conanfile = re.sub(rf"^\s*self\.{req_attr}\([\"']{name}.*\n?", '',
                           conanfile, flags=re.MULTILINE)
        success_msgs.append(f"Removed {name} dependency as {req_attr}.")
    save(path, conanfile)
    ConanOutput().success('\n'.join(success_msgs))


@conan_subcommand()
def require_add(conan_api, parser, subparser, *args):
    """
    Add a new requirement to your local conanfile as a version range.
    By default, it will look for the requirement versions remotely.
    """
    subparser.add_argument("--folder",
                           help="Path to a folder containing a recipe (conanfile.py). "
                                "Defaults to the current directory",)
    subparser.add_argument("requires", nargs="*", help="Requirement name.")
    subparser.add_argument("-tor", "--tool", action="append", default=[],
                           help="Tool requirement name.")
    subparser.add_argument("-ter", "--test", action="append", default=[],
                           help="Test requirement name.")
    group = subparser.add_mutually_exclusive_group()
    group.add_argument("-r", "--remote", default=None, action="append",
                       help="Remote names. Accepts wildcards ('*' means all the remotes available)")
    group.add_argument("-nr", "--no-remote", action="store_true",
                       help='Do not use remote, resolve exclusively in the cache')
    args = parser.parse_args(*args)
    requires = [(r, "requires", "requirements") for r in args.requires]
    tool_requires = [(r, "tool_requires", "build_requirements") for r in args.tool]
    test_requires = [(r, "test_requires", "build_requirements") for r in args.test]
    if not any(requires + tool_requires + test_requires):
        raise ConanException("You need to add any requires, tool_requires or test_requires.")
    path = conan_api.local.get_conanfile_path(args.folder or ".", os.getcwd(), py=True)
    remotes = conan_api.remotes.list(args.remote) if not args.no_remote else [None]
    conanfile = load(path)
    ConanOutput().debug(f"Loaded conanfile from {path}.")
    cached_results = {}
    success_msgs = []
    for (name, req_attr, req_func) in requires + tool_requires + test_requires:
        # Check if that requirement exists in the conanfile. If yes, do nothing.
        if re.search(rf"self\.{req_attr}\([\"']{name}", conanfile):
            ConanOutput().warning(f"The {req_attr} {name} is already in use.")
            continue
        if name in cached_results:
            # Avoid double-search in remotes/cache, e.g., protobuf
            reference = RecipeReference.loads(f"{name}/{cached_results[name]}")
        elif "/" in name:  # it already brings a version
            reference = RecipeReference.loads(name)
            cached_results[name] = reference.version  # caching the result
        else:  # Search the latest version in remotes/cache
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
                continue
            # Put the upper limit for that requirement (next major version)
            reference = RecipeReference.loads(results.popitem()[0])
            cached_results[name] = reference.version  # caching the result
        try:
            version_range = f"{reference.name}/[>={reference.version} <{str(reference.version.bump(0))}]"
        except ConanException:  # likely cannot bump the version, using it without ranges
            version_range = str(reference)
        full_version_range = f'self.{req_attr}("{version_range}")'
        if full_version_range:
            tab_space = " " * 4
            if f"def {req_func}(" in conanfile:
                conanfile = conanfile.replace(f"def {req_func}(self):\n",
                                              f"def {req_func}(self):\n{tab_space * 2}{full_version_range}\n")
            else:
                requirements_func = f"\n{tab_space}def {req_func}(self):\n{tab_space * 2}{full_version_range}\n"
                conanfile += requirements_func
        success_msgs.append(f"Added '{version_range}' as a new {req_attr}.")
    save(path, conanfile)
    ConanOutput().success('\n'.join(success_msgs))


@conan_command(group="Consumer")
def require(conan_api: ConanAPI, parser, *args):
    """
    Adds/removes requirements to/from your local conanfile.
    """
