#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys

from setuptools import setup
from setuptools.command.test import test as TestCommand


with open('steamwatch/__version__.py') as versionfile:
    VERSION = versionfile.read().split('\'')[1]

if sys.argv[-1] == 'publish':
    os.system('python setup.py sdist upload')
    sys.exit()

readme = open('README.rst').read()

with open('requirements.txt') as f:
    requires = [line for line in f.readlines()]


class PyTest(TestCommand):

    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        import pytest
        errcode = pytest.main(self.test_args)
        sys.exit(errcode)

setup(
    name='steamwatch',
    version=VERSION,
    description='Watch prices on Steam store',
    long_description=readme,
    author='Alexander Keil',
    author_email='alex@akeil.net',
    url='https://github.com/akeil/steamwatch',
    packages=[
        'steamwatch',
    ],
    package_dir={'steamwatch': 'steamwatch'},
    include_package_data=True,
    install_requires=requires,
    cmdclass={'test': PyTest,},
    tests_require=['pytest',],
    extras_require={
        'testing': ['pytest',],
    },
    license="BSD",
    zip_safe=True,
    keywords='steam steamstore',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
    ],
    test_suite='tests',
    entry_points={
        'console_scripts': [
            'steamwatch = steamwatch.main:main',
        ],
        'steamwatch.signals': [
            'app_added = steamwatch.application:log_signal',
            'app_removed = steamwatch.application:log_signal',
            'package_linked = steamwatch.application:log_signal',
            'threshold = steamwatch.application:log_signal',
            'currency_changed = steamwatch.application:log_signal',
            'price_changed = steamwatch.application:log_signal',
            'release_date_changed = steamwatch.application:log_signal',
            'coming_soon_changed = steamwatch.application:log_signal',
            'supports_linux_changed = steamwatch.application:log_signal',
        ]
    }
)
