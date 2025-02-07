import os

from conan.internal.model.options import Options
from conan.internal.model.profile import Profile
from conans.util.files import save


def create_profile(folder, name, settings=None, package_settings=None, env=None,
                   package_env=None, options=None, conf=None):

    package_env = package_env or {}

    profile = Profile()
    profile.settings = settings or {}

    if package_settings:
        profile.package_settings = package_settings

    if options:
        profile.options = Options(options_values=options)

    if conf:
        _conf = "\n".join(conf) if isinstance(conf, list) else conf
        profile.conf.loads(_conf)

    """for package_name, envs in package_env.items():
        for var_name, value in envs:
            # Initialize Environment without Conanfile, what else can we do
            profile._environments.set_default(package_name, Environment(conanfile=None))\
                .define(var_name, value)

    for var_name, value in env or {}:
        profile._environments.set_default(None, Environment(conanfile=None)) \
            .define(var_name, value)"""

    save(os.path.join(folder, name), profile.dumps())
