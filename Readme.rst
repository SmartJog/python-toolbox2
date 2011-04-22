=======
python-toolbox2
=======

python-toolbox2 provides a generic interface for:
 * actions description and execution which manipulate multiple workers,
 * workers description and execution which manipulate different tools such
as ffmpeg for example.


License
=======

python-toolbox2 is released under the `GNU LGPL 2.1 <http://www.gnu.org/licenses/lgpl-2.1.html>`_.


Build and installation
=======================

Bootstrapping
-------------

python-toolbox2 uses the autotools for its build system.

If you checked out code from the git repository, you will need
autoconf and automake to generate the configure script and Makefiles.

To generate them, simply run::

    $ autoreconf -fvi

Building
--------

python-toolbox2 builds like your typical autotools-based project::

    $ ./configure && make && make install


Development
===========

We use `semantic versioning <http://semver.org/>`_ for
versioning. When working on a development release, we append ``~dev``
to the current version to distinguish released versions from
development ones. This has the advantage of working well with Debian's
version scheme, where ``~`` is considered smaller than everything (so
version 1.10.0 is more up to date than 1.10.0~dev).


Authors
=======

python-toolbox2 was created at SmartJog by Matthieu Bouron.

* Matthieu Bouron <matthieu.bouron@smartjog.com>
