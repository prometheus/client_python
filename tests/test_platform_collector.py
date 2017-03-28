from __future__ import unicode_literals

import unittest

from prometheus_client import CollectorRegistry, PlatformCollector


class TestPlatformCollector(unittest.TestCase):
    def setUp(self):
        self.registry = CollectorRegistry()
        self.platform = _MockPlatform()

    def test_python_info(self):
        PlatformCollector(registry=self.registry, platform=self.platform)
        self.assertLabels("python_info", {
            "version": "python_version",
            "implementation": "python_implementation",
            "major": "pvt_major",
            "minor": "pvt_minor",
            "patchlevel": "pvt_patchlevel"
        })

    def test_machine_info(self):
        PlatformCollector(registry=self.registry, platform=self.platform)
        self.assertLabels("machine_info", {
            "bits": "a_bits",
            "linkage": "a_linkage",
            "machine": "u_machine",
            "processor": "u_processor"
        })

    def test_system_info_java(self):
        self.platform._system = "Java"
        PlatformCollector(registry=self.registry, platform=self.platform)
        self.assertLabels("system_info", {
            "system": "os_name",
            "name": "Java",
            "kernel": "os_version",
            "java_version": "jv_release",
            "vm_release": "vm_release",
            "vm_vendor": "vm_vendor",
            "vm_name": "vm_name"
        })

    def test_system_info_linux(self):
        self.platform._system = "Linux"
        PlatformCollector(registry=self.registry, platform=self.platform)
        self.assertLabels("system_info", {
            "system": "Linux",
            "name": "ld_distname",
            "kernel": "u_kernel",
            "version": "ld_version",
            "dist_id": "ld_id",
            "libc": "lv_lib",
            "libc_version": "lv_version"
        })

    def test_system_info_win32(self):
        self.platform._system = "Windows"
        PlatformCollector(registry=self.registry, platform=self.platform)
        self.assertLabels("system_info", {
            "system": "Windows",
            "name": "Windows wv_release",
            "kernel": "wv_version",
            "version": "wv_version",
            "csd": "wv_csd",
            "ptype": "wv_ptype"
        })

    def test_system_info_darwin(self):
        self.platform._system = "Darwin"
        PlatformCollector(registry=self.registry, platform=self.platform)
        self.assertLabels("system_info", {
            "system": "Darwin",
            "name": "Mac OS mv_release",
            "kernel": "u_kernel",
            "version": "mv_release"
        })

    def test_system_info_other(self):
        self.platform._system = "Non-standard"
        PlatformCollector(registry=self.registry, platform=self.platform)
        self.assertLabels("system_info", {
            "system": "u_system",
            "kernel": "u_kernel",
            "version": "u_version"
        })

    def assertLabels(self, name, labels):
        for metric in self.registry.collect():
            for n, l, value in metric.samples:
                if n == name:
                    assert l == labels


class _MockPlatform(object):
    def __init__(self):
        self._system = "system"

    def python_version_tuple(self):
        return "pvt_major", "pvt_minor", "pvt_patchlevel"

    def python_version(self):
        return "python_version"

    def python_implementation(self):
        return "python_implementation"

    def uname(self):
        return "u_system", "u_node", "u_kernel", "u_version", "u_machine", "u_processor"

    def architecture(self):
        return "a_bits", "a_linkage"

    def system(self):
        return self._system

    def java_ver(self):
        return "jv_release", "jv_vendor", ("vm_name", "vm_release", "vm_vendor"), ("os_name", "os_version", "os_arch")

    def linux_distribution(self):
        return "ld_distname", "ld_version", "ld_id"

    def libc_ver(self):
        return "lv_lib", "lv_version"

    def mac_ver(self):
        return "mv_release", ("mv_version", "mv_dev_stage", "mv_non_release_version"), "mv_machine"

    def win32_ver(self):
        return "wv_release", "wv_version", "wv_csd", "wv_ptype"
