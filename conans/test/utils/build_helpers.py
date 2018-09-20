
import subprocess
from conans.util.files import decode_text
from semver import SemVer


def get_cmake_version():
    out, err = subprocess.Popen(["cmake", "--version"], stdout=subprocess.PIPE).communicate()
    version_line = decode_text(out).split('\n', 1)[0]
    return SemVer(version_line.rsplit(' ', 1)[-1], loose=True)
