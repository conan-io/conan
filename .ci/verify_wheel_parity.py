"""Fail if any package file in the sdist is missing from the wheel.

Catches `package_data` gaps: files that ship in the source tarball but do
not end up installed by pip when using the wheel.
"""
import glob
import sys
import tarfile
import zipfile

PACKAGE_PREFIXES = ("conan/", "conans/")


def sdist_package_files(path):
    with tarfile.open(path) as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            # Strip the top-level "<name>-<version>/" directory.
            _, _, name = member.name.partition("/")
            if name.startswith(PACKAGE_PREFIXES):
                yield name


def wheel_package_files(path):
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            if name.endswith("/"):
                continue
            if name.startswith(PACKAGE_PREFIXES):
                yield name


def main():
    sdist = glob.glob("dist/*.tar.gz")[0]
    wheel = glob.glob("dist/*.whl")[0]
    missing = set(sdist_package_files(sdist)) - set(wheel_package_files(wheel))
    if missing:
        print("ERROR: files present in sdist but missing from wheel "
              "(likely package_data gap):")
        for name in sorted(missing):
            print(f"  {name}")
        sys.exit(1)


if __name__ == "__main__":
    main()
