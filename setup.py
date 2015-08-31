import os
import subprocess
from distutils.command.build import build
from setuptools import setup, find_packages

import toolbox2


class MyBuild(build):
    """Customized build command - build manpages."""
    def run(self):
        try:
            print('Generating manpages...')
            subprocess.call(['rst2man', 'doc/toolbox2.rst', 'doc/toolbox2.1'])
            subprocess.call(['rst2man', 'doc/toolbox2-transcode.rst', 'doc/toolbox2-transcode.1'])
        except OSError:
            print('Warning: rst2man was not found, skipping manpages generation.')
        build.run(self)


data_files = [(d, [os.path.join(d, f) for f in files]) for d, dirs, files in os.walk('share/fonts')]
data_files.append(('/etc/', ['conf/toolbox2.conf']))

setup(
    name='python-toolbox2',
    author='The development team at Arkena',
    author_email='opensource@arkena.com',
    description='Generic interface to describe and manage actions on media assets.',
    long_description=open('Readme.rst').read(),
    url='https://github.com/SmartJog/python-toolbox2/',
    version=toolbox2.__version__,
    packages=find_packages(exclude=('tests', 'tests.*')),
    scripts=['bin/toolbox2', 'bin/toolbox2-transcode'],
    data_files=data_files,
    test_suite='tests',
    cmdclass={'build': MyBuild},
    classifiers=[
        "Programming Language :: Python",
        "License :: LGPL 2.1",
        "Operating System :: OS Independent",
    ],
)
