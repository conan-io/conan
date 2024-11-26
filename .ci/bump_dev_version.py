import os
import time


def replace_in_file(file_path, search, replace):
    with open(file_path, "r") as handle:
        content = handle.read()
        if search not in content:
            raise Exception("Incorrect development version in conan/__init__.py")
    content = content.replace(search, replace)
    content = content.encode("utf-8")
    with open(file_path, "wb") as handle:
        handle.write(content)

def bump_dev():
    vfile = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../conan/__init__.py")
    snapshot = "%s" % int(time.time())
    replace_in_file(vfile, "-dev'", "-dev%s'" % snapshot)


if __name__ == "__main__":
    bump_dev()
