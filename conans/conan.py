import sys
import os
import platform

# https://github.com/icloud-photos-downloader/icloud_photos_downloader/commit/5450392a6d7c28c6926207b03e063f1ec049da2f#
if platform.system() == "Darwin":
    from multiprocessing import freeze_support
    freeze_support() # fixing tqdm on macos

if os.getenv("CONAN_V2_CLI"):
    from conans.cli.cli import main
else:
    from conans.client.command import main


def run():
    main(sys.argv[1:])


if __name__ == '__main__':
    run()
