import unittest

import numpy as np

from pytissueoptics.scene.geometry.utils import eulerRotationMatrix


class TestEulerRotationMatrix(unittest.TestCase):
    def testGivenNoRotation_shouldNotRotate(self):
        noRotation = eulerRotationMatrix()
        p = [1, 1, 1]

        pRotated = np.dot(noRotation, p)

        self.assertTrue(np.allclose(p, pRotated))

    def testGivenXRotation_shouldRotateAroundX(self):
        xRotation = eulerRotationMatrix(xTheta=90)
        p = [1, 1, 1]

        pRotated = np.dot(xRotation, p)

        self.assertTrue(np.allclose([1, -1, 1], pRotated))

    def testGivenYRotation_shouldRotateAroundY(self):
        yRotation = eulerRotationMatrix(yTheta=90)
        p = [1, 1, 1]

        pRotated = np.dot(yRotation, p)

        self.assertTrue(np.allclose([1, 1, -1], pRotated))

    def testGivenZRotation_shouldRotateAroundZ(self):
        zRotation = eulerRotationMatrix(zTheta=90)
        p = [1, 1, 1]

        pRotated = np.dot(zRotation, p)

        self.assertTrue(np.allclose([-1, 1, 1], pRotated))

    def testGivenXYZRotation_shouldRotateAroundXYZInOrder(self):
        rotation = eulerRotationMatrix(xTheta=90, yTheta=90, zTheta=90)
        p = [1, 1, 1]

        pRotated = np.dot(rotation, p)

        self.assertTrue(np.allclose([1, 1, -1], pRotated))
