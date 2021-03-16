#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""Test file for the toolbox2 module"""

import os
import unittest

import toolbox2


class Toolbox2TestCase(unittest.TestCase):
    """Test functions from the toolbox2 module"""

    def test_get_existing_resource_from_existing_category(self):
        """Test the get_internal_resource function

        Existing resource, existing category
        """
        path = toolbox2.get_internal_resource("fonts", "Vera.ttf")
        assert os.path.isfile(path), "The returned path does not exist."

    def test_get_non_existing_resource_from_existing_category(self):
        """Test the get_internal_resource function

        Non-existing resource, existing category
        """
        path = toolbox2.get_internal_resource("fonts", "foobar")
        assert not os.path.isfile(path), "The returned path should not exist."

    def test_get_existing_resource_from_non_existing_category(self):
        """Test the get_internal_resource function

        Existing resource, non-existing category
        """
        path = toolbox2.get_internal_resource("dummy", "Vera.ttf")
        assert not os.path.isfile(path), "The returned path should not exist."

    def test_get_non_existing_resource_from_non_existing_category(self):
        """Test the get_internal_resource function

        Non-existing resource, non-existing category
        """
        path = toolbox2.get_internal_resource("dummy", "foobar")
        assert not os.path.isfile(path), "The returned path should not exist."


if __name__ == "__main__":
    unittest.main()  # run all tests
