# -*- coding: utf-8 -*-

from toolbox2.action import Action

from toolbox2.action.extract import *
from toolbox2.action.rewrap import *
from toolbox2.action.transcode import *


def find_subclasses(cls, _seen=None):

    if not isinstance(cls, type):
        raise TypeError('find_subclasses must be called with new-style classes, not %.100r' % cls)

    if _seen is None: _seen = set()
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


class LoaderException(Exception):
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

                self.actions[cls.name] = {'name': cls.name,
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
