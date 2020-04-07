from conans.client.build.cppstd_flags import cppstd_from_settings, cppstd_default
from conans.errors import ConanInvalidConfiguration, ConanException
from conans.model.version import Version


def deduced_cppstd(conanfile):
    """ Return either the current cppstd or the default one used by the current compiler

        1. If settings.compiler.cppstd is not None - will return settings.compiler.cppstd
        2. It settings.compiler.cppstd is None - will use compiler to deduce (reading the
            default from cppstd_default)
        3. If settings.compiler is None - will raise a ConanInvalidConfiguration exception
        4. If can't detect the default cppstd for settings.compiler - will return None

    :param conanfile: ConanFile instance with compiler and cppstd information
    """
    cppstd = cppstd_from_settings(conanfile.settings)
    if cppstd:
        return cppstd

    compiler = conanfile.settings.get_safe("compiler")
    if not compiler:
        raise ConanInvalidConfiguration("Could not obtain cppstd because either compiler is not "
                                        "specified in the profile or the 'settings' field of the "
                                        "recipe is missing")
    compiler_version = conanfile.settings.get_safe("compiler.version")
    if not compiler_version:
        raise ConanInvalidConfiguration("Could not obtain cppstd because compiler.version "
                                        "is not specified in the profile")

    return cppstd_default(conanfile.settings)


def _remove_extension(_cppstd):
    """ Removes gnu prefix from cppstd

    :param cppstd: cppstd version
    :return: Cppstd without extension
    """
    return str(_cppstd).replace("gnu", "")


def _contains_extension(cppstd):
    """ Returns if cppstd contains gnu extension

    :param cppstd: cppstd version
    :return: True, if current cppstd contains the gnu extension. Otherwise, False.
    """
    return str(cppstd).startswith("gnu") and _remove_extension(cppstd).isdigit()


def normalized_cppstd(cppstd):
    """ Return a normalized cppstd value by removing extensions and
        adding a millennium to allow ordering on it

    :param cppstd: cppstd version
    """
    if not isinstance(cppstd, str) and not str(cppstd).isdigit():
        raise ConanException("cppstd parameter must either be a string or a digit")

    def add_millennium(_cppstd):
        return "19%s" % _cppstd if _cppstd == "98" else "20%s" % _cppstd

    return add_millennium(_remove_extension(cppstd))


def check_gnu_extension(cppstd):
    """ Check if cppstd enables gnu extensions

    :param cppstd: cppstd version
    """
    if not isinstance(cppstd, str) and not str(cppstd).isdigit():
        raise ConanException("cppstd parameter must either be a string or a digit")

    if not _contains_extension(cppstd):
        raise ConanInvalidConfiguration("The cppstd GNU extension is required")


def check_min_cppstd(conanfile, cppstd, gnu_extensions=False):
    """ Check if the current cppstd fits the minimal version required.

        In case the current cppstd doesn't fit the minimal version required
        by cppstd, a ConanInvalidConfiguration exception will be raised.

    :param conanfile: ConanFile instance with cppstd information
    :param cppstd: Minimal cppstd version required
    :param gnu_extensions: GNU extension is required (e.g gnu17)
    """
    if not str(cppstd).isdigit():
        raise ConanException("cppstd parameter must be a number")
    if not isinstance(gnu_extensions, bool):
        raise ConanException("gnu_extensions parameter must be a bool")

    current_cppstd = deduced_cppstd(conanfile)
    if not current_cppstd:
        raise ConanInvalidConfiguration("Could not detect default cppstd for the current compiler.")

    if gnu_extensions:
        check_gnu_extension(current_cppstd)

    if normalized_cppstd(current_cppstd) < normalized_cppstd(cppstd):
        raise ConanInvalidConfiguration("Current cppstd ({}) is lower than the required C++ "
                                        "standard ({}).".format(current_cppstd, cppstd))


def valid_min_cppstd(conanfile, cppstd, gnu_extensions=False):
    """ Validate if current cppstd fits the minimal version required.

    :param conanfile: ConanFile instance with cppstd information
    :param cppstd: Minimal cppstd version required
    :param gnu_extensions: GNU extension is required (e.g gnu17)
    :return: True, if current cppstd matches the required cppstd version. Otherwise, False.
    """
    if not str(cppstd).isdigit():
        raise ConanException("cppstd parameter must be a number")
    if not isinstance(gnu_extensions, bool):
        raise ConanException("gnu_extensions parameter must be a bool")

    try:
        check_min_cppstd(conanfile, cppstd, gnu_extensions)
    except ConanInvalidConfiguration:
        return False
    return True


def check_max_cppstd(conanfile, cppstd, gnu_extensions=False):
    """ Check if the current cppstd fits the maximal version required.

        In case the current cppstd doesn't fit the maximal version required
        by cppstd, a ConanInvalidConfiguration exception will be raised.

    :param conanfile: ConanFile instance with cppstd information
    :param cppstd: Minimal cppstd version required
    :param gnu_extensions: GNU extension is required (e.g gnu17)
    """
    if not str(cppstd).isdigit():
        raise ConanException("cppstd parameter must be a number")
    if not isinstance(gnu_extensions, bool):
        raise ConanException("gnu_extensions parameter must be a bool")

    current_cppstd = deduced_cppstd(conanfile)
    if not current_cppstd:
        raise ConanInvalidConfiguration("Could not detect default cppstd for the current compiler.")

    if gnu_extensions:
        check_gnu_extension(current_cppstd)

    if normalized_cppstd(current_cppstd) > normalized_cppstd(cppstd):
        raise ConanInvalidConfiguration("Current cppstd ({}) is higher than the required C++ "
                                        "standard ({}).".format(current_cppstd, cppstd))


def valid_max_cppstd(conanfile, cppstd, gnu_extensions=False):
    """ Validate if current cppstd fits the maximal version required.

    :param conanfile: ConanFile instance with cppstd information
    :param cppstd: Minimal cppstd version required
    :param gnu_extensions: GNU extension is required (e.g gnu17)
    :return: True, if current cppstd matches the required cppstd version. Otherwise, False.
    """
    if not str(cppstd).isdigit():
        raise ConanException("cppstd parameter must be a number")
    if not isinstance(gnu_extensions, bool):
        raise ConanException("gnu_extensions parameter must be a bool")

    try:
        check_max_cppstd(conanfile, cppstd, gnu_extensions)
    except ConanInvalidConfiguration:
        return False
    return True


def check_cppstd(conanfile, min=None, max=None, excludes=[], gnu_extensions=False, strict=False):
    """ Check if the current cppstd fits specified requirements

        In case the current cppstd doesn't fit specified requirements
        a ConanInvalidConfiguration exception will be raised.

        In case information about cppstd is lacking
        a ConanUnknownConfiguration exception will be raised.

    :param conanfile: ConanFile instance
    :param min: Minimal cppstd version required
    :param max: Maximal cppstd version required
    :param excludes: A list of cppstd version excluded
    :param gnu_extensions: GNU extension is required (e.g gnu17)
    :param strict: Unkown configurations are invalid
    """
    if min and not str(min).isdigit():
        raise ConanException("min parameter must be a number")
    if max and not str(max).isdigit():
        raise ConanException("max parameter must be a number")
    if not isinstance(excludes, list):
        raise ConanException("excludes parameter must be a list")
    if not isinstance(gnu_extensions, bool):
        raise ConanException("gnu_extensions parameter must be a bool")
    if not isinstance(strict, bool):
        raise ConanException("strict parameter must be a bool")
    if min and max:
        if normalized_cppstd(min) > normalized_cppstd(max):
            raise ConanException("min parameter is bigger than the max parameter")

    current_cppstd = deduced_cppstd(conanfile)
    if not current_cppstd:
        msg = "Default standard version information is missing for the current compiler"
        if strict:
            raise ConanInvalidConfiguration(msg)
        conanfile.output.warn(msg)
        return

    if gnu_extensions:
        check_gnu_extension(current_cppstd)

    if min:
        if normalized_cppstd(current_cppstd) < normalized_cppstd(min):
            raise ConanInvalidConfiguration("Current cppstd ({}) is less than the minimum required C++ "
                                            "standard ({})".format(current_cppstd, min))

    if max:
        if normalized_cppstd(current_cppstd) > normalized_cppstd(max):
            raise ConanInvalidConfiguration("Current cppstd ({}) is higher than the maximum required C++ "
                                            "standard ({})".format(current_cppstd, max))

    if current_cppstd in excludes:
        raise ConanInvalidConfiguration(
            "Current cppstd ({}) is excluded from requirements".format(current_cppstd))


def check_compiler(conanfile, required, strict=False):
    """ Check if the current compiler fits specified requirements

        In case the current compiler doesn't fit specified requirements
        a ConanInvalidConfiguration exception will be raised.

        In case information about compiler is lacking and strict flag is set
        a ConanUnknownConfiguration exception will be raised.

    :param conanfile: ConanFile instance
    :param required: A dict of required compiler versions required
    :param strict: Unkown configurations are invalid
    """
    if not isinstance(required, dict):
        raise ConanException("required parameter must be a dict")
    if not isinstance(strict, bool):
        raise ConanException("strict parameter must be a bool")

    compiler = conanfile.settings.get_safe("compiler")
    if not compiler:
        raise ConanInvalidConfiguration("Could not obtain cppstd because either compiler is not "
                                        "specified in the profile or the 'settings' field of the "
                                        "recipe is missing")
    try:
        if compiler not in required:
            raise ConanInvalidConfiguration("Compiler support information is missing")
    except ConanInvalidConfiguration as e:
        if strict:
            raise
        conanfile.output.warn(e)
        return

    compiler_version = conanfile.settings.get_safe("compiler.version")
    if not compiler_version:
        raise ConanInvalidConfiguration("Could not obtain cppstd because compiler.version "
                                        "is not specified in the profile")
    version = Version(compiler_version)
    if version < required[compiler]:
        raise ConanInvalidConfiguration(
            "At least {} {} is required".format(compiler, required[compiler]))


def compatible_cppstd(conanfile, current_cppstd=None, min=None, max=None,
                      backward=False, forward=True, gnu_extensions_compatible=True):
    """ Fill the conanfile compatible_packages field with compatible cppstd

    :param conanfile: ConanFile instance
    :param current_cppstd: Current cppstd to override deduction
    :param min: Inclusive cppstd lower bound
    :param max: Inclusive cppstd upper bound
    :param backward: Current cppstd is compatible with lower ones
    :param forward: Current cppstd is compatible with higher ones
    :param gnu_extensions_compatible: GNU extensions are not compatible
    """
    if current_cppstd is not None:
        if not isinstance(current_cppstd, str) and not str(current_cppstd).isdigit():
            raise ConanException("current_cppstd parameter must either be a string or a digit")
    if min is not None and not str(min).isdigit():
        raise ConanException("min parameter must be a number")
    if max is not None and not str(max).isdigit():
        raise ConanException("max parameter must be a number")
    if not isinstance(backward, bool):
        raise ConanException("backward parameter must be a bool")
    if not isinstance(forward, bool):
        raise ConanException("forward parameter must be a bool")
    if not isinstance(gnu_extensions_compatible, bool):
        raise ConanException("gnu_extensions_compatible parameter must be a bool")

    # We allow overriding cppstd deduction to leave a place for
    # custom user settings
    if not current_cppstd:
        current_cppstd = deduced_cppstd(conanfile)
        if not current_cppstd:
            raise ConanInvalidConfiguration(
                "Could not detect default cppstd for the current compiler.")
    else:
        current_cppstd = str(current_cppstd)

    # We have a list of original cppstd setting values because we'll
    # need it to pass to compatible packages
    # FIXME: Conanfile should carry range information of a setting with it
    cppstd_range = ["98", "11", "14", "17", "20"]

    if _remove_extension(current_cppstd) not in cppstd_range:
        raise ConanInvalidConfiguration(
            "current_cppstd not found in the list of known cppstd values (without extensions): {}".format(cppstd_range))
    if min and str(min) not in cppstd_range:
        raise ConanInvalidConfiguration(
            "min not found in the list of known cppstd values: {}".format(cppstd_range))
    if max and str(max) not in cppstd_range:
        raise ConanInvalidConfiguration(
            "max not found in the list of known cppstd values: {}".format(cppstd_range))

    gnu_cppstd_range = []
    for cppstd in cppstd_range:
        gnu_cppstd_range.append("gnu{}".format(cppstd))
    if gnu_extensions_compatible:
        cppstd_range.extend(gnu_cppstd_range)
    else:
        if _contains_extension(current_cppstd):
            cppstd_range = gnu_cppstd_range
    # None replaces cppstd if it's a default cppstd on a given compiler
    cppstd_range.append(None)

    current_normalized = normalized_cppstd(current_cppstd)
    lower, same, higher = [], [], []
    for cppstd in cppstd_range:
        if cppstd is None:
            default = cppstd_default(conanfile.settings)
            actual_cppstd = default
            normalized = normalized_cppstd(default)
        else:
            actual_cppstd = cppstd
            normalized = normalized_cppstd(cppstd)

        if max and normalized > normalized_cppstd(max):
            continue
        if min and normalized < normalized_cppstd(min):
            continue

        if normalized > current_normalized:
            higher.append(cppstd)
            continue

        if normalized < current_normalized:
            lower.append(cppstd)
            continue

        if _contains_extension(current_cppstd) == _contains_extension(actual_cppstd):
            continue
        same.append(cppstd)

    if forward:
        for cppstd in lower:
            compatible_pkg = conanfile.info.clone()
            compatible_pkg.settings.compiler.cppstd = cppstd
            conanfile.compatible_packages.append(compatible_pkg)

    for cppstd in same:
        compatible_pkg = conanfile.info.clone()
        compatible_pkg.settings.compiler.cppstd = cppstd
        conanfile.compatible_packages.append(compatible_pkg)

    if backward:
        for cppstd in higher:
            compatible_pkg = conanfile.info.clone()
            compatible_pkg.settings.compiler.cppstd = cppstd
            conanfile.compatible_packages.append(compatible_pkg)
