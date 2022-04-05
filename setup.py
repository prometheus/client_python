from os import path

from setuptools import setup

with open(path.join(path.abspath(path.dirname(__file__)), 'README.md')) as f:
    long_description = f.read()


setup(
    name="prometheus_client",
    version="0.14.0",
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
    package_data={
        'prometheus_client': ['py.typed']
    },
    extras_require={
        'twisted': ['twisted'],
    },
    test_suite="tests",
    python_requires=">=3.6",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Information Technology",
        "Intended Audience :: System Administrators",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Topic :: System :: Monitoring",
        "License :: OSI Approved :: Apache Software License",
    ],
)
