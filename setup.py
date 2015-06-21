import os
from setuptools import setup

setup(
    name = "prometheus_client",
    version = "0.0.10",
    author = "Brian Brazil",
    author_email = "brian.brazil@gmail.com",
    description = ("Python client for the Prometheus monitoring system."),
    long_description = ("See https://github.com/prometheus/client_python/blob/master/README.md for documentation."),
    license = "Apache Software License 2.0",
    keywords = "prometheus monitoring instrumentation client",
    url = "https://github.com/prometheus/client_python",
    packages=['prometheus_client', 'prometheus_client.bridge'],
    test_suite="tests",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Information Technology",
        "Intended Audience :: System Administrators",
        "Topic :: System :: Monitoring",
        "License :: OSI Approved :: Apache Software License",
    ],
)
