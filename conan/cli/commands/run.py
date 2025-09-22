import os

from conan.cli.command import conan_command


@conan_command(group="Creator")
def run(conan_api, parser, *args):
    """
    Run a command in the environment defined by a previous call to 'conan install'.
    """
    # Initially we're not adding a way to specify the requirement from here,
    # or a conanfile to use, because that would add 300 args,
    # and the idea is to start small. If we see a need for this, it might be
    # discussed later, but the recommended way is to do 'conan install' first
    # if your use-case is more complex than the current one, and then
    # just source the envs directly
    parser.add_argument("command", help="Command to run",
                        nargs='+')
    parser.add_argument("--context", help="Context to use, host or build",
                        choices=["host", "build"], default="host")
    args = parser.parse_args(*args)
    command = " ".join(args.command)
    cwd = os.getcwd()
    # TODO: most of this will need to go into something like
    #conan_api.local.run(args.command, cwd, ...)
    import subprocess

    # TODO: We'll also need a way to find the env files,
    # harcoded for now, but things to take into account are:
    # - tools.env.virtualenv:powershell conf when using Windows
    #    - then different shells/prefixes will be necessary
    # - what context? How do we choose it? Is the current parameter a good idea?
    # - error handling
    # - Should we capture the output? Does not look like a good idea for interactive commands
    prefix = "conanbuild.sh" if args.context == "build" else "conanrun.sh"
    composed_command = f". {prefix} && {command}"
    subprocess.run(composed_command, shell=True, cwd=cwd, check=True)
