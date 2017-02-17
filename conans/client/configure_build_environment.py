import copy
import os

from conans.model.settings import get_setting_str_safe

sun_cc_libcxx_flags_dict = {"libCstd": "-library=Cstd",
                            "libstdcxx": "-library=stdcxx4",
                            "libstlport": "-library=stlport4",
                            "libstdc++": "-library=stdcpp"}


class VisualStudioBuildEnvironment(object):
    """
    - LIB: library paths with semicolon separator
    - CL: /I (include paths)
    """
    def __init__(self, conanfile):
        self._deps_cpp_info = conanfile.deps_cpp_info

    @property
    def vars(self):
        cl_args = " ".join(['/I"%s"' % lib for lib in self._deps_cpp_info.include_paths])
        lib_paths = ";".join(['%s' % lib for lib in self._deps_cpp_info.lib_paths])
        return {"CL": cl_args,
                "LIB": lib_paths}


class AutoToolsBuildEnvironment(object):
    """
    - CPPFLAGS (C-PreProcesor-Flags NOT related with c++) (-I -D)
    - CFLAGS (not CPPFLAGS nor LDFLAGS, used for optimization or debugging)
    - CXXFLAGS (the CFLAGS for c++)
    - LDFLAGS (-L, others like -m64 -m32) linker
    """

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self._deps_cpp_info = conanfile.deps_cpp_info
        self._arch = get_setting_str_safe(conanfile.settings, "arch")
        self._build_type = get_setting_str_safe(conanfile.settings, "build_type")
        self._compiler = get_setting_str_safe(conanfile.settings, "compiler")
        self._libcxx = get_setting_str_safe(conanfile.settings, "compiler.libcxx")

        # Set the generic objects before mapping to env vars to let the user
        # alter some value
        self.libs = copy.copy(self._deps_cpp_info.libs)
        self.include_paths = copy.copy(self._deps_cpp_info.include_paths)
        self.library_paths = copy.copy(self._deps_cpp_info.lib_paths)

        self.defines = self._configure_defines()
        # Will go to CFLAGS and CXXFLAGS ["-m64" "-m32", "-g", "-s"]
        self.compilation_flags = self._configure_compilation_flags()
        # Only c++ flags [-stdlib, -library], will go to CXXFLAGS
        self.only_cpp_compilation_flags = self._configure_only_cpp_compilation_flags()
        # Not -L flags, ["-m64" "-m32"]
        self.linker_flags = self._configure_linker_flags
        # Not declared by default
        self.fpic = None

    def _configure_linker_flags(self):
        """Not the -L"""
        return [self._architecture_flag]

    def _configure_compilation_flags(self):
        ret = [self._architecture_flag]
        if self._build_type == "Debug":
            ret.append("-g")
        elif self._build_type == "Release" and self._compiler == "gcc":
            ret.append("-s")
        return ret

    def _configure_only_cpp_compilation_flags(self):
        ret = []
        if "clang" in str(self._compiler):
            if str(self._libcxx) == "libc++":
                ret.append("-stdlib=libc++")
            else:
                ret.append("-stdlib=libstdc++")

        elif str(self._compiler) == "sun-cc":
            flag = sun_cc_libcxx_flags_dict.get(self._libcxx, None)
            if flag:
                ret.append(flag)
        return ret

    def _configure_defines(self):
        # requires declared defines
        ret = copy.copy(self._deps_cpp_info.defines)

        # Debug definition for GCC
        if self._build_type == "Debug" and self._build_type == "gcc":
            ret.append("NDEBUG")

        # CXX11 ABI
        if self._libcxx == "libstdc++":
            ret.append("_GLIBCXX_USE_CXX11_ABI=0")
        elif self._libcxx == "libstdc++11":
            ret.append("_GLIBCXX_USE_CXX11_ABI=1")
        return ret

    @property
    def _architecture_flag(self):
        return {"x86_64": "-m64", "x86": "-m32"}.get(self._arch, "")

    @property
    def vars(self):
        def append(*args):
            ret = []
            for arg in args:
                if arg:
                    if isinstance(arg, list):
                        ret.extend(arg)
                    else:
                        ret.append(arg)
            return ret

        lib_paths = ['-L%s' % x for x in self.library_paths]
        include_paths = ['-I%s' % x for x in self.include_paths]

        ld_flags = append(self._configure_linker_flags(), lib_paths)
        cpp_flags = append(include_paths, ["-D%s" % x for x in self.defines])
        libs = ['-l%s' % lib for lib in self.libs]

        tmp_compilation_flags = copy.copy(self.compilation_flags)
        if self.fpic:
            tmp_compilation_flags.append("-fPIC")

        cxx_flags = append(tmp_compilation_flags, self.only_cpp_compilation_flags)
        c_flags = tmp_compilation_flags

        ret = {"CPPFLAGS": " ".join(cpp_flags),
               "CXXFLAGS": " ".join(cxx_flags),
               "CFLAGS": " ".join(c_flags),
               "LDFLAGS": " ".join(ld_flags),
               "LIBS": " ".join(libs)
               }

        return ret


class GCCBuildEnvironment(object):
    """

   VALID FOR CLANG, GCC and MINGW

    https://gcc.gnu.org/onlinedocs/gcc/Environment-Variables.html

    - LIBRARY_PATH
        The value of LIBRARY_PATH is a colon-separated list of directories, much like PATH. When configured as a
        native compiler, GCC tries the directories thus specified when searching for special linker files,
        if it can't find them using GCC_EXEC_PREFIX. Linking using GCC also uses these directories when searching
        for ordinary libraries for the -l option (but directories specified with -L come first).

    - CPATH
        list of directories separated by a special character, much like PATH, in which to look for header files.
        The special character, PATH_SEPARATOR, is target-dependent and determined at GCC build time.
        For Microsoft Windows-based targets it is a semicolon, and for almost all other targets it is a colon.
        Specifies a list of directories to be searched as if specified with -I, but after any paths given with -I
        options on the command line. This environment variable is used regardless of which language is being
        preprocessed. For language specific:

    - C_INCLUDE_PATH: Not used!!! used general CPATH instead
    - CPLUS_INCLUDE_PATH: Not used!!! used general CPATH instead

    """

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self._deps_cpp_info = conanfile.deps_cpp_info
        self._libcxx = get_setting_str_safe(conanfile.settings, "compiler.libcxx")
        self._compiler = get_setting_str_safe(conanfile.settings, "compiler")

    @property
    def _library_path(self):
        return ":".join(self._deps_cpp_info.lib_paths)

    @property
    def _path(self):
        return os.pathsep.join(self._deps_cpp_info.include_paths)

    @property
    def vars(self):
        ret = {"LIBRARY_PATH": self._library_path,
               "C_PATH": self._path}
        return ret
