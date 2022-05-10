
def cross_building(conanfile=None, skip_x64_x86=False):
    """
    Return ``True`` or ``False`` if we are cross building according to the settings.

    :param conanfile: The current recipe object. Always use ``self``.
    :param skip_x64_x86: Do not consider cross building when building to 32 bits from 64 bits:
           x86_64 to x86, sparcv9 to sparc or ppc64 to ppc32
    :return: ``True`` if we are cross building, ``False`` otherwise.
    """

    build_os = conanfile.settings_build.get_safe('os')
    build_arch = conanfile.settings_build.get_safe('arch')
    host_os = conanfile.settings.get_safe("os")
    host_arch = conanfile.settings.get_safe("arch")

    if skip_x64_x86 and host_os is not None and (build_os == host_os) and \
            host_arch is not None and ((build_arch == "x86_64") and (host_arch == "x86") or
                                       (build_arch == "sparcv9") and (host_arch == "sparc") or
                                       (build_arch == "ppc64") and (host_arch == "ppc32")):
        return False

    if host_os is not None and (build_os != host_os):
        return True
    if host_arch is not None and (build_arch != host_arch):
        return True

    return False
