import argparse
import json
import os

from conans.build_info.conan_build_info import get_build_info


def run():

    parser = argparse.ArgumentParser(description='Extracts build-info from a specified '
                                                 'conan trace log and return a valid JSON')
    parser.add_argument('trace_path', help='Path to the conan trace log file e.j: '
                                           '/tmp/conan_trace.log')
    args = parser.parse_args()

    if not os.path.exists(args.trace_path):
        print("Error, conan trace log not found! '%s'" % args.trace_path)
        exit(1)

    try:
        info = get_build_info(args.trace_path)
        print(json.dumps(info.serialize()))
    except Exception as exc:
        print(exc)
        exit(1)

if __name__ == "__main__":
    run()
