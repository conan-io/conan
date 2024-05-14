from conans.util.thread import cpu_count


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
                               default=cpu_count(),
                               check_type=int)
    return njobs



