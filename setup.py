#!/usr/bin/env python
from setuptools import setup, find_packages


setup(
    name='mantis-cli',
    version='1.6.0',
    description='Management command to build and deploy webapps, especially based on Django',
    long_description=open('README.md').read(),
    author='Erik Telepovský',
    author_email='info@pragmaticmates.com',
    maintainer='Pragmatic Mates',
    maintainer_email='info@pragmaticmates.com',
    url='https://github.com/PragmaticMates/mantis-cli',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[],
    entry_points={
        'console_scripts': ['mantis=mantis.command_line:run'],
    },
    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.6',
        'Operating System :: OS Independent',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Framework :: Django',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Development Status :: 3 - Alpha'
    ],
    license='GNU General Public License (GPL)',
    keywords="management deployment docker command",
)
