# -*- coding: utf-8 -*-

import os
import sys

from toolbox2.action import Action
from toolbox2.exception import Toolbox2Exception

from toolbox2.action.extract import *
from toolbox2.action.rewrap import *
from toolbox2.action.transcode import *
from toolbox2.action.getcapability import *


__version__ = '0.10.3~dev'

_ROOT = os.path.abspath(os.path.dirname(__file__))


def get_internal_resource(category, resource):
    """Return the absolute path toward a resource"""
    # If installed properly on Unix
    path = os.path.join(sys.prefix, 'share', category, resource)
    if not os.path.exists(path):
        # If simply installed via the setup.py (no specific root/prefix)
        path = os.path.join(_ROOT,
                            os.pardir,
                            'share',
                            category,
                            resource)
    return path


def find_subclasses(cls, _seen=None):

    if not isinstance(cls, type):
        raise TypeError('find_subclasses must be called with new-style classes, not %.100r' % cls)

    if _seen is None:
        _seen = set()

    try:
        subs = cls.__subclasses__()
    except TypeError:
        subs = cls.__subclasses__(cls)

    for sub in subs:
        if sub not in _seen:
            _seen.add(sub)
            yield sub
            for sub in find_subclasses(sub, _seen):
                yield sub


class LoaderException(Toolbox2Exception):
    pass


class Loader(object):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Loader, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'actions'):
            self.actions = {}
            for cls in find_subclasses(Action):
                if cls.name in self.actions:
                    raise LoaderException('Identifier %s already used for class: %s' % (cls.name, cls))

                self.actions[cls.name] = {
                    'name': cls.name,
                    'description': cls.description,
                    'category': cls.category,
                    'required_params': cls.required_params,
                    'class': cls,
                }

    def get_class(self, name):
        try:
            return self.actions[name]['class']
        except KeyError:
            raise LoaderException('Action %s does not exist' % name)
