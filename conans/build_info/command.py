import argparse
import json
import os

from conans.build_info.conan_build_info import get_build_info
from conans.util.files import save


def run():

    parser = argparse.ArgumentParser(description='Extracts build-info from a specified '
                                                 'conan trace log and return a valid JSON')
    parser.add_argument('trace_path', help='Path to the conan trace log file e.j: '
                                           '/tmp/conan_trace.log')
    parser.add_argument("--output", default=False,
                        help='Optional file to output the JSON contents, if not specified the JSON'
                             ' will be printed to stdout')

    args = parser.parse_args()

    if not os.path.exists(args.trace_path):
        print("Error, conan trace log not found! '%s'" % args.trace_path)
        exit(1)
    if args.output and not os.path.exists(os.path.dirname(args.output)):
        print("Error, output file directory not found! '%s'" % args.trace_path)
        exit(1)

    try:
        info = get_build_info(args.trace_path)
        the_json = json.dumps(info.serialize())
        if args.output:
            save(args.output, the_json)
        else:
            print(the_json)
    except Exception as exc:
        print(exc)
        exit(1)

if __name__ == "__main__":
    run()
