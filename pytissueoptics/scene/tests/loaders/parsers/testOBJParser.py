import unittest
from pytissueoptics.scene.loaders import OBJParser


class TestOBJParser(unittest.TestCase):
    def testWhenCreatedEmpty_shouldRaiseError(self):
        with self.assertRaises(Exception):
            parser = OBJParser()

