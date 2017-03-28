#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import unicode_literals

import platform as pf

from . import core


class PlatformCollector(object):
    """Collector for platform information"""

    def __init__(self, registry=core.REGISTRY, platform=None):
        self._platform = pf if platform is None else platform
        self._metrics = [
            self._add_metric(*self._python()),
            self._add_metric(*self._machine()),
            self._add_metric(*self._system())
        ]
        if registry:
            registry.register(self)

    def collect(self):
        return self._metrics

    @staticmethod
    def _add_metric(name, documentation, data):
        labels = data.keys()
        values = [data[k] for k in labels]
        g = core.GaugeMetricFamily(name, documentation, labels=labels)
        g.add_metric(values, 1)
        return g

    def _python(self):
        major, minor, patchlevel = self._platform.python_version_tuple()
        return "python_info", "Python information", {
            "version": self._platform.python_version(),
            "implementation": self._platform.python_implementation(),
            "major": major,
            "minor": minor,
            "patchlevel": patchlevel
        }

    def _machine(self):
        _, _, _, _, machine, processor = self._platform.uname()
        bits, linkage = self._platform.architecture()
        return "machine_info", "Machine information", {
            "bits": bits,
            "linkage": linkage,
            "machine": machine,
            "processor": processor
        }

    def _system(self):
        system = self._platform.system()
        return {
            "Linux": self._linux,
            "Windows": self._win32,
            "Java": self._java,
            "Darwin": self._mac,
        }.get(system, self._system_other)()

    def _system_other(self):
        system, _, release, version, _, _ = self._platform.uname()
        return "system_info", "System information", {
            "system": system,
            "kernel": release,
            "version": version
        }

    def _java(self):
        java_version, _, vminfo, osinfo = self._platform.java_ver()
        vm_name, vm_release, vm_vendor = vminfo
        system, kernel, _ = osinfo
        return "system_info", "System information (Java)", {
            "system": system,
            "name": "Java",
            "kernel": kernel,
            "java_version": java_version,
            "vm_release": vm_release,
            "vm_vendor": vm_vendor,
            "vm_name": vm_name
        }

    def _win32(self):
        release, version, csd, ptype = self._platform.win32_ver()
        return "system_info", "System information (Windows)", {
            "system": "Windows",
            "name": "Windows {}".format(release),
            "kernel": version,
            "version": version,
            "csd": csd,
            "ptype": ptype
        }

    def _mac(self):
        release, _, machine = self._platform.mac_ver()
        _, _, kernel, _, _, _ = self._platform.uname()
        return "system_info", "System information (Darwin)", {
            "system": "Darwin",
            "name": "Mac OS {}".format(release),
            "kernel": kernel,
            "version": release
        }

    def _linux(self):
        name, version, dist_id = self._platform.linux_distribution()
        libc, libc_version = self._platform.libc_ver()
        _, _, kernel, _, _, _ = self._platform.uname()
        return "system_info", "System information (Linux)", {
            "system": "Linux",
            "name": name.strip(),
            "kernel": kernel,
            "version": version,
            "dist_id": dist_id,
            "libc": libc,
            "libc_version": libc_version
        }


PLATFORM_COLLECTOR = PlatformCollector()
"""PlatfprmCollector in default Registry REGISTRY"""
