import math
import multiprocessing

from conans.util.files import load


def build_jobs(conanfile):
    njobs = conanfile.conf.get("tools.build:jobs",
                               default=_cpu_count(),
                               check_type=int)
    return njobs


def _cpu_count():
    try:
        try:
            # This is necessary to deduce docker cpu_count
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
