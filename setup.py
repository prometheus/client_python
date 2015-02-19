import os
from setuptools import setup

# Utility function to read the README file.
# Used for the long_description.  It's nice, because now 1) we have a top level
# README file and 2) it's easier to type in the README file than to put a raw
# string in below ...
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name = "prometheus_client",
    version = "0.0.5",
    author = "Brian Brazil",
    author_email = "brian.brazil@gmail.com",
    description = ("Python client for the Prometheus monitoring system."),
    long_description = ("See https://github.com/brian-brazil/client_python/blob/master/README.md for documentation."),
    license = "Apache Software License 2.0",
    keywords = "prometheus monitoring instrumentation client",
    url = "https://github.com/prometheus/client_python",
    packages=['prometheus_client'],
    test_suite="tests",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Information Technology",
        "Intended Audience :: System Administrators",
        "Topic :: System :: Monitoring",
        "License :: OSI Approved :: Apache Software License",
    ],
)
