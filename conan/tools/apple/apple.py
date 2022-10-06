#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os

from conans.util.runners import check_output_runner
from conans.client.tools.apple import to_apple_arch as _to_apple_arch


def is_apple_os(conanfile):
    """returns True if OS is Apple one (Macos, iOS, watchOS or tvOS"""
    os_ = conanfile.settings.get_safe("os")
    return str(os_) in ['Macos', 'iOS', 'watchOS', 'tvOS']


def to_apple_arch(conanfile):
    """converts conan-style architecture into Apple-style arch"""
    arch_ = conanfile.settings.get_safe("arch")
    return _to_apple_arch(arch_)


def _guess_apple_sdk_name(os_, arch):
    if str(arch).startswith('x86'):
        return {'Macos': 'macosx',
                'iOS': 'iphonesimulator',
                'watchOS': 'watchsimulator',
                'tvOS': 'appletvsimulator'}.get(str(os_))
    else:
        return {'Macos': 'macosx',
                'iOS': 'iphoneos',
                'watchOS': 'watchos',
                'tvOS': 'appletvos'}.get(str(os_), None)


def apple_sdk_name(settings):
    """returns proper SDK name suitable for OS and architecture
    we're building for (considering simulators)"""
    arch = settings.get_safe('arch')
    os_ = settings.get_safe('os')
    os_sdk = settings.get_safe('os.sdk')
    os_sdk_version = settings.get_safe('os.sdk_version') or ""
    return "{}{}".format(os_sdk, os_sdk_version) if os_sdk else _guess_apple_sdk_name(os_, arch)


def apple_min_version_flag(conanfile):
    """compiler flag name which controls deployment target"""
    os_version = conanfile.settings.get_safe("os.version")
    if not os_version:
        return ''

    os_ = conanfile.settings.get_safe("os")
    os_sdk = conanfile.settings.get_safe("os.sdk")
    os_subsystem = conanfile.settings.get_safe("os.subsystem")
    arch = conanfile.settings.get_safe("arch")

    if not os_version:
        return ''
    os_sdk = os_sdk if os_sdk else _guess_apple_sdk_name(os_, arch)
    flag = {'macosx': '-mmacosx-version-min',
            'iphoneos': '-mios-version-min',
            'iphonesimulator': '-mios-simulator-version-min',
            'watchos': '-mwatchos-version-min',
            'watchsimulator': '-mwatchos-simulator-version-min',
            'appletvos': '-mtvos-version-min',
            'appletvsimulator': '-mtvos-simulator-version-min'}.get(str(os_sdk))
    if os_subsystem == 'catalyst':
        # especial case, despite Catalyst is macOS, it requires an iOS version argument
        flag = '-mios-version-min'
    if not flag:
        return ''
    return "%s=%s" % (flag, os_version)


def apple_sdk_path(conanfile):
    sdk_path = conanfile.conf.get("tools.apple:sdk_path")
    if not sdk_path:
        sdk_path = XCRun(conanfile).sdk_path
    return sdk_path


class XCRun(object):

    def __init__(self, conanfile, sdk=None):
        """sdk=False will skip the flag
           sdk=None will try to adjust it automatically"""
        if sdk is None and conanfile.settings:
            sdk = apple_sdk_name(conanfile.settings)
        self.sdk = sdk

    def _invoke(self, args):
        def cmd_output(cmd):
            return check_output_runner(cmd).strip()

        command = ['xcrun']
        if self.sdk:
            command.extend(['-sdk', self.sdk])
        command.extend(args)
        return cmd_output(command)

    def find(self, tool):
        """find SDK tools (e.g. clang, ar, ranlib, lipo, codesign, etc.)"""
        return self._invoke(['--find', tool])

    @property
    def sdk_path(self):
        """obtain sdk path (aka apple sysroot or -isysroot"""
        return self._invoke(['--show-sdk-path'])

    @property
    def sdk_version(self):
        """obtain sdk version"""
        return self._invoke(['--show-sdk-version'])

    @property
    def sdk_platform_path(self):
        """obtain sdk platform path"""
        return self._invoke(['--show-sdk-platform-path'])

    @property
    def sdk_platform_version(self):
        """obtain sdk platform version"""
        return self._invoke(['--show-sdk-platform-version'])

    @property
    def cc(self):
        """path to C compiler (CC)"""
        return self.find('clang')

    @property
    def cxx(self):
        """path to C++ compiler (CXX)"""
        return self.find('clang++')

    @property
    def ar(self):
        """path to archiver (AR)"""
        return self.find('ar')

    @property
    def ranlib(self):
        """path to archive indexer (RANLIB)"""
        return self.find('ranlib')

    @property
    def strip(self):
        """path to symbol removal utility (STRIP)"""
        return self.find('strip')

    @property
    def libtool(self):
        """path to libtool"""
        return self.find('libtool')


def fix_apple_shared_install_name(conanfile):

    def _get_install_name(path_to_dylib):
        command = "otool -D {}".format(path_to_dylib)
        install_name = check_output_runner(command).strip().split(":")[1].strip()
        return install_name

    def _darwin_collect_dylibs(lib_folder):
        return [os.path.join(lib_folder, f) for f in os.listdir(lib_folder) if f.endswith(".dylib")
                and not os.path.islink(os.path.join(lib_folder, f))]

    def _fix_install_name(dylib_path, new_name):
        command = f"install_name_tool {dylib_path} -id {new_name}"
        conanfile.run(command)

    def _fix_dep_name(dylib_path, old_name, new_name):
        command = f"install_name_tool {dylib_path} -change {old_name} {new_name}"
        conanfile.run(command)

    def _darwin_collect_executables(bin_folder):
        ret = []
        for f in os.listdir(bin_folder):
            full_path = os.path.join(bin_folder, f)

            # Run "otool -hv" to verify it is an executable
            check_bin = "otool -hv {}".format(full_path)
            if "EXECUTE" in check_output_runner(check_bin):
                ret.append(full_path)
        return ret

    def _get_rpath_entries(binary_file):
        entries = []
        command = "otool -l {}".format(binary_file)
        otool_output = check_output_runner(command).splitlines()
        for count, text in enumerate(otool_output):
            pass
            if "LC_RPATH" in text:
                rpath_entry = otool_output[count+2].split("path ")[1].split(" ")[0]
                entries.append(rpath_entry)
        return entries

    def _get_shared_dependencies(binary_file):
        command = "otool -L {}".format(binary_file)
        all_shared = check_output_runner(command).strip().split(":")[1].strip()
        ret = [s.split("(")[0].strip() for s in all_shared.splitlines()]
        return ret

    def _fix_dylib_files(conanfile):
        substitutions = {}
        libdirs = getattr(conanfile.cpp.package, "libdirs")
        for libdir in libdirs:
            full_folder = os.path.join(conanfile.package_folder, libdir)
            if not os.path.exists(full_folder):
                # as method package is running before package_info, the cpp.package might be
                # wrong
                continue
            shared_libs = _darwin_collect_dylibs(full_folder)
            # fix LC_ID_DYLIB in first pass
            for shared_lib in shared_libs:
                install_name = _get_install_name(shared_lib)
                #TODO: we probably only want to fix the install the name if
                # it starts with `/`.
                rpath_name = f"@rpath/{os.path.basename(install_name)}"
                _fix_install_name(shared_lib, rpath_name)
                substitutions[install_name] = rpath_name

            # fix dependencies in second pass
            for shared_lib in shared_libs:
                for old, new in substitutions.items():
                    _fix_dep_name(shared_lib, old, new)

        return substitutions

    def _fix_executables(conanfile, substitutions):
        # Fix the install name for executables inside the package
        # that reference libraries we just patched
        bindirs = getattr(conanfile.cpp.package, "bindirs")
        for bindir in bindirs:
            full_folder = os.path.join(conanfile.package_folder, bindir)
            if not os.path.exists(full_folder):
                # as method package is running before package_info, the cpp.package might be
                # wrong
                continue
            executables = _darwin_collect_executables(full_folder)
            for executable in executables:

                # Fix install names of libraries from within the same package
                deps = _get_shared_dependencies(executable)
                for dep in deps:
                    dep_base = os.path.join(os.path.dirname(dep), os.path.basename(dep).split('.')[0])
                    match = [k for k in substitutions.keys() if k.startswith(dep_base)]
                    if match:
                        _fix_dep_name(executable, dep, substitutions[match[0]])

                # Add relative rpath to library directories, avoiding possible
                # existing duplicates
                libdirs = getattr(conanfile.cpp.package, "libdirs")
                libdirs = [os.path.join(conanfile.package_folder, dir) for dir in libdirs]
                rel_paths = [f"@executable_path/{os.path.relpath(dir, full_folder)}" for dir in libdirs]
                existing_rpaths = _get_rpath_entries(executable)
                rpaths_to_add = list(set(rel_paths) - set(existing_rpaths))
                for entry in rpaths_to_add:
                    command = f"install_name_tool {executable} -add_rpath {entry}"
                    conanfile.run(command)

    if is_apple_os(conanfile) and conanfile.options.get_safe("shared", False):
        substitutions = _fix_dylib_files(conanfile)
        _fix_executables(conanfile, substitutions)
