from setuptools import setup

setup(
    name="prometheus_client",
    version="0.5.0",
    author="Brian Brazil",
    author_email="brian.brazil@robustperception.io",
    description="Python client for the Prometheus monitoring system.",
    long_description=(
        "See https://github.com/prometheus/client_python/blob/master/README.md"
        " for documentation."),
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
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Information Technology",
        "Intended Audience :: System Administrators",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Topic :: System :: Monitoring",
        "License :: OSI Approved :: Apache Software License",
    ],
)
