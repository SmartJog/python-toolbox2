import os
import subprocess
from setuptools import setup, find_packages

import toolbox2


try:
    # Build manpages
    subprocess.call(['txt2tags', '-o', 'doc/toolbox2.1', 'doc/toolbox2.t2t'])
    subprocess.call(['txt2tags', '-o', 'doc/toolbox2-transcode.1', 'doc/toolbox2-transcode.t2t'])
except OSError:
    print('Warning: txt2tags was not found, skipping manpages generation.')

data_files = [(d, [os.path.join(d, f) for f in files]) for d, dirs, files in os.walk('share/fonts')]
data_files.append(('/etc/', ['conf/toolbox2.conf']))

setup(
    name='python-toolbox2',
    author='The development team at Arkena',
    author_email='opensource@arkena.com',
    long_description=open('Readme.rst').read(),
    url='https://github.com/SmartJog/python-toolbox2/',
    version=toolbox2.__version__,
    packages=find_packages(),
    scripts=['bin/toolbox2', 'bin/toolbox2-transcode'],
    data_files=data_files,
    classifiers=[
        "Programming Language :: Python",
        "License :: LGPL 2.1",
        "Operating System :: OS Independent",
    ],
)
