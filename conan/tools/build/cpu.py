import math
import multiprocessing
import os

from conans.util.files import load


def build_jobs(conanfile):
    """
    Returns the number of CPUs available for parallel builds.
    It returns the configuration value for ``tools.build:jobs`` if exists, otherwise,
    it defaults to the helper function ``_cpu_count()``.
    ``_cpu_count()`` reads cgroup to detect the configured number of CPUs.
    Currently, there are two versions of cgroup available.

    In the case of cgroup v1, if the data in cgroup is invalid, processor detection comes into play.
    Whenever processor detection is not enabled, ``build_jobs()`` will safely return 1.

    In the case of cgroup v2, if no limit is set, processor detection is used. When the limit is set,
    the behavior is as described in cgroup v1.

    :param conanfile: The current recipe object. Always use ``self``.
    :return: ``int`` with the number of jobs
    """
    njobs = conanfile.conf.get("tools.build:jobs",
                               default=_cpu_count(),
                               check_type=int)
    return njobs


def _cpu_count():
    try:
        try:
            # This is necessary to deduce docker cpu_count
            cfs_quota_us = cfs_period_us = 0
            # cgroup2
            if os.path.exists("/sys/fs/cgroup/cgroup.controllers"):
                cpu_max = load("/sys/fs/cgroup/cpu.max").split()
                if cpu_max[0] != "max":
                    if len(cpu_max) == 1:
                        cfs_quota_us, cfs_period_us = int(cpu_max[0]), 100_000
                    else:
                        cfs_quota_us, cfs_period_us = map(int, cpu_max)
            else:  # cgroup1
                cfs_quota_us = int(load("/sys/fs/cgroup/cpu/cpu.cfs_quota_us"))
                cfs_period_us = int(load("/sys/fs/cgroup/cpu/cpu.cfs_period_us"))
            if cfs_quota_us > 0 and cfs_period_us > 0:
                return int(math.ceil(cfs_quota_us / cfs_period_us))
        except (EnvironmentError, TypeError):
            pass
        return multiprocessing.cpu_count()
    except NotImplementedError:
        # print("multiprocessing.cpu_count() not implemented. Defaulting to 1 cpu")
        return 1  # Safe guess
