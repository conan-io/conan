import argparse
import json
import os
import sys

from conans.build_info.conan_build_info import get_build_info
from conans.build_info.conan_build_info_v2 import start, stop, create, update, publish
from conans.errors import ConanException
from conans.util.files import save
from conans.client.output import ConanOutput


class ArgumentParserError(Exception):
    pass


class ErrorCatchingArgumentParser(argparse.ArgumentParser):
    def exit(self, status=0, message=None):
        if status:
            raise ArgumentParserError(f"Exiting because of an error: {message}")

    def error(self, message):
        raise ArgumentParserError(message)


def run():
    output = ConanOutput(sys.stdout, sys.stderr, True)
    exc_v1 = None
    exc_v2 = None
    valid_commands = ["start", "stop", "create", "update", "publish"]
    try:
        parser_v1 = ErrorCatchingArgumentParser(description="Extracts build-info from a specified "
                                                            "conan trace log and return a valid JSON")
        parser_v1.add_argument("trace_path", help="Path to the conan trace log file e.g.: "
                                                  "/tmp/conan_trace.log")
        parser_v1.add_argument("--output", default=False,
                               help="Optional file to output the JSON contents, if not specified "
                                    "the JSON will be printed to stdout")
        args = parser_v1.parse_args()
        if args.trace_path not in valid_commands and not os.path.exists(args.trace_path):
            output.error("Error, conan trace log not found! '%s'" % args.trace_path)
        if args.output and not os.path.exists(os.path.dirname(args.output)):
            output.error("Error, output file directory not found! '%s'" % args.trace_path)
        try:
            info = get_build_info(args.trace_path)
            the_json = json.dumps(info.serialize())
            if args.output:
                save(args.output, the_json)
            else:
                output.write(the_json)
        except Exception as exc:
            exc_v1 = exc
            pass
    except ArgumentParserError as exc:
        exc_v1 = exc
        pass

    finally:
        parser_v2 = ErrorCatchingArgumentParser(description="Generates build info build info from "
                                                            "collected information and lockfiles",
                                                prog="conan_build_info")
        subparsers = parser_v2.add_subparsers(dest="subcommand", help="sub-command help")

        parser_start = subparsers.add_parser("start",
                                             help="Command to incorporate to the "
                                                  "artifacts.properties the build name and number")
        parser_start.add_argument("build_name", type=str, help="build name to assign")
        parser_start.add_argument("build_number", type=int,
                                  help="build number to assign")

        subparsers.add_parser("stop", help="Command to remove from the artifacts.properties "
                                           "the build name and number")

        parser_create = subparsers.add_parser("create",
                                              help="Command to generate a build info json from a "
                                                   "lockfile")
        parser_create.add_argument("build_info_file", type=str,
                                   help="build info json for output")
        parser_create.add_argument("--lockfile", type=str, required=True, help="input lockfile")
        parser_create.add_argument("--multi_module", nargs='?', default=True, help="input lockfile")
        parser_create.add_argument("--skip_env", nargs='?', default=True, help="input lockfile")
        parser_create.add_argument("--user", type=str, nargs="?", default=None, help="user")
        parser_create.add_argument("--password", type=str, nargs="?", default=None, help="password")
        parser_create.add_argument("--apikey", type=str, nargs="?", default=None, help="apikey")

        parser_update = subparsers.add_parser("update",
                                              help="Command to update a build info json with "
                                                   "another one")
        parser_update.add_argument("build_info_1", type=str, help="build info 1")
        parser_update.add_argument("build_info_2", type=str, help="build info 2")

        parser_publish = subparsers.add_parser("publish",
                                               help="Command to publish the build info to "
                                                    "Artifactory")
        parser_publish.add_argument("build_info_file", type=str,
                                    help="build info to upload")
        parser_publish.add_argument("--url", type=str, required=True, help="url")
        parser_publish.add_argument("--user", type=str, nargs="?", default=None, help="user")
        parser_publish.add_argument("--password", type=str, nargs="?", default=None, help="password")
        parser_publish.add_argument("--apikey", type=str, nargs="?", default=None, help="apikey")

        def check_credential_arguments():
            if args.user and args.apikey:
                parser_v2.error("Please select one authentificacion method --user USER "
                                "--password PASSWORD or --apikey APIKEY")
            if args.user and not args.password:
                parser_v2.error(
                    "Please specify a password for user '{}' with --password PASSWORD".format(
                        args.user))

        try:
            args = parser_v2.parse_args()
            if args.subcommand == "start":
                start(args.build_name, args.build_number, output)
            if args.subcommand == "stop":
                stop(output)
            if args.subcommand == "create":
                check_credential_arguments()
                create(output, args.build_info_file, args.lockfile, args.multi_module, args.skip_env,
                       args.user, args.password, args.apikey)
            if args.subcommand == "update":
                update(args.build_info_1, args.build_info_2, output)
            if args.subcommand == "publish":
                check_credential_arguments()
                publish(args.build_info_file, args.url, args.user, args.password, args.apikey)
        except ArgumentParserError as exc:
            exc_v2 = exc
        except ConanException as exc:
            output.error(exc)

    if exc_v1 and exc_v2:
        output.error("Error executing conan_build_info. There are two possible uses:\n")
        output.info("Extracting build information from conan traces (in deprecation):\n")
        output.error(str(exc_v1))
        parser_v1.print_help()
        output.info("Calculating build info from collected information and lockfiles "
                    "(recommended use):\n")
        output.error(str(exc_v2))
        parser_v2.print_help()


if __name__ == "__main__":
    run()
