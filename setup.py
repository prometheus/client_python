from os import path
import sys

from setuptools import setup

if sys.version_info >= (2, 7):
    with open(path.join(path.abspath(path.dirname(__file__)), 'README.md')) as f:
        long_description = f.read()
else:  # Assuming we don't run setup in order to publish under python 2.6
    long_description = "NA"


setup(
    name="prometheus_client",
    version="0.10.0",
    author="Brian Brazil",
    author_email="brian.brazil@robustperception.io",
    description="Python client for the Prometheus monitoring system.",
    long_description=long_description,
    long_description_content_type='text/markdown',
    license="Apache Software License 2.0",
    keywords="prometheus monitoring instrumentation client",
    url="https://github.com/prometheus/client_python",
    packages=[
        'prometheus_client',
        'prometheus_client.bridge',
        'prometheus_client.openmetrics',
        'prometheus_client.twisted',
    ],
    extras_require={
        'twisted': ['twisted'],
    },
    test_suite="tests",
    python_requires=">=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Information Technology",
        "Intended Audience :: System Administrators",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Topic :: System :: Monitoring",
        "License :: OSI Approved :: Apache Software License",
    ],
    options={'bdist_wheel': {'universal': '1'}},
)
