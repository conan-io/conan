import argparse
import json
import os

from conans.build_info.conan_build_info import get_build_info
from conans.util.files import save


class ErrorCatchingArgumentParser(argparse.ArgumentParser):
    def exit(self, status=0, message=None):
        if status:
            raise Exception(f"Exiting because of an error: {message}")

    def error(self, message):
        raise Exception(message)


def run():
    exc_v1 = None
    exc_v2 = None
    try:
        parser_v1 = ErrorCatchingArgumentParser(description="Extracts build-info from a specified "
                                                         "conan trace log and return a valid JSON")
        parser_v1.add_argument("trace_path", help="Path to the conan trace log file e.g.: "
                                               "/tmp/conan_trace.log")
        parser_v1.add_argument("--output", default=False,
                            help="Optional file to output the JSON contents, if not specified the "
                                 "JSON will be printed to stdout")
        args = parser_v1.parse_args()
        if not os.path.exists(args.trace_path):
            print("Error, conan trace log not found! '%s'" % args.trace_path)
        if args.output and not os.path.exists(os.path.dirname(args.output)):
            print("Error, output file directory not found! '%s'" % args.trace_path)
        try:
            info = get_build_info(args.trace_path)
            the_json = json.dumps(info.serialize())
            if args.output:
                save(args.output, the_json)
            else:
                print(the_json)
        except Exception as exc:
            exc_v1 = exc
            pass
    except Exception as exc:
        exc_v1 = exc
        pass

    finally:
        parser_v2 = ErrorCatchingArgumentParser(description="Generates build info v2",
                                             prog="conan_build_info")
        subparsers = parser_v2.add_subparsers(help="sub-command help")

        parser_start = subparsers.add_parser("start",
                                             help="Command to incorporate to the "
                                                  "artifacts.properties the build name and number")
        parser_start.add_argument("build_name", type=str, help="build name to assign")
        parser_start.add_argument("build_number", type=int, help="build number to assign")

        parser_stop = subparsers.add_parser("stop",
                                            help="Command to remove from the artifacts.properties "
                                                 "the build name and number")

        parser_create = subparsers.add_parser("create",
                                              help="Command to generate a build info json from a "
                                                   "lockfile")
        parser_create.add_argument("build_info_file", type=str, help="build info json for output")
        parser_create.add_argument("--lockfile", type=str, help="input lockfile")

        parser_update = subparsers.add_parser("update",
                                              help="Command to update a build info json with "
                                                   "another one")
        parser_update.add_argument("build_info_1", type=str, help="build info 1")
        parser_update.add_argument("build_info_2", type=str, help="build info 2")

        parser_publish = subparsers.add_parser("publish",
                                               help="Command to publish the build info to Artifactory")
        parser_publish.add_argument("build_info_file", type=str, help="build info to upload")
        parser_publish.add_argument("--url", type=str, help="url")
        parser_publish.add_argument("--user", type=str, help="user")
        parser_publish.add_argument("--password", type=str, help="password")
        parser_publish.add_argument("--apikey", type=str, help="apikey")

        try:
            args = parser_v2.parse_args()
            print(args)
        except Exception as exc:
            exc_v2 = exc
            pass

    if exc_v1 and exc_v2:
        print("Error executing conan_build_info:")
        print(str(exc_v1))
        parser_v1.print_help()
        print(str(exc_v2))
        parser_v2.print_help()


if __name__ == "__main__":
    run()
