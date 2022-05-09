import os

from conan.tools.env import Environment


def runenv_from_cpp_info(dep, os_name):
    """ return an Environment deducing the runtime information from a cpp_info
    """
    dyn_runenv = Environment()
    cpp_info = dep.cpp_info.aggregated_components()

    def _handle_paths(paths):
        return [p for p in paths if os.path.exists(p)]

    if cpp_info.bindirs:  # cpp_info.exes is not defined yet
        dyn_runenv.prepend_path("PATH", _handle_paths(cpp_info.bindirs))
    # If it is a build_require this will be the build-os, otherwise it will be the host-os
    if os_name and not os_name.startswith("Windows"):
        if cpp_info.libdirs:
            libdirs = _handle_paths(cpp_info.libdirs)
            dyn_runenv.prepend_path("LD_LIBRARY_PATH", libdirs)
            dyn_runenv.prepend_path("DYLD_LIBRARY_PATH", libdirs)
        if cpp_info.frameworkdirs:
            dyn_runenv.prepend_path("DYLD_FRAMEWORK_PATH", _handle_paths(cpp_info.frameworkdirs))
    return dyn_runenv


class VirtualRunEnv:
    """ Calculates the environment variables of the build time context and produces a conanbuildenv
        .bat or .sh script
    """

    def __init__(self, conanfile):
        """

        :param conanfile:  The current recipe object. Always use ``self``.
        """
        self._conanfile = conanfile
        self._conanfile.virtualrunenv = False
        self.basename = "conanrunenv"
        self.configuration = conanfile.settings.get_safe("build_type")
        if self.configuration:
            self.configuration = self.configuration.lower()
        self.arch = conanfile.settings.get_safe("arch")
        if self.arch:
            self.arch = self.arch.lower()

    @property
    def _filename(self):
        f = self.basename
        if self.configuration:
            f += "-" + self.configuration
        if self.arch:
            f += "-" + self.arch
        return f

    def environment(self):
        """
        Returns an ``Environment`` object containing the environment variables of the run context.

        :return: an ``Environment`` object instance containing the obtained variables.
        """
        runenv = Environment()
        # FIXME: Missing profile info
        # FIXME: Cache value?

        host_req = self._conanfile.dependencies.host
        test_req = self._conanfile.dependencies.test
        for require, dep in list(host_req.items()) + list(test_req.items()):
            if dep.runenv_info:
                runenv.compose_env(dep.runenv_info)
            if require.run:  # Only if the require is run (shared or application to be run)
                _os = self._conanfile.settings.get_safe("os")
                runenv.compose_env(runenv_from_cpp_info(dep, _os))

        return runenv

    def vars(self, scope="run"):
        """
        :param scope: Scope to be used.
        :return: An ``EnvVars`` instance containing the computed environment variables.
        """
        return self.environment().vars(self._conanfile, scope=scope)

    def generate(self, scope="run"):
        """
        Produces the launcher scripts activating the variables for the run context.

        :param scope: Scope to be used.
        """
        run_env = self.environment()
        if run_env:
            run_env.vars(self._conanfile, scope=scope).save_script(self._filename)
