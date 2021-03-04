import numpy as np
from .vectors import *

class Scalars:
    """ An array of scalars that is compatible with operations on Vectors 
    There is a reason for not using numpy.array directly: we want to
    add new functions that will be specific to our problem here,
    and Python does not allow us to extend system classes.

    The class works with float, int and bool.  With boolean values, True is 1.
    """
    def __init__(self, array=None, N=None):
        if array is not None:
            self.v = np.array(array)
        elif N is not None:
            self.v = np.array([0]*N)

        self._iteration = 0

    def __iter__(self):
        self._iteration = 0
        return self

    def __next__(self):
        if self._iteration < len(self):
            result = self.v[self._iteration]
            self._iteration += 1
            return result
        else:
            raise StopIteration

    def __len__(self):
        return len(self.v)

    def __mul__(self, scale):
        return Scalars(self.v*scale)

    def __rmul__(self, scale):
        return Scalars(self.v*scale)

    def __truediv__(self, scale):
        return Scalars(self.v/scale)

    def __add__(self, rhs):
        return Scalars([v1+v2 for (v1, v2) in list(zip(self.v, rhs.v))])

    def __neg__(self):
        return Scalars([-v1 for v1 in self.v])

    def __sub__(self, rhs):
        return Scalars([v1-v2 for (v1, v2) in list(zip(self.v, rhs.v))])

    def __getitem__(self, index):
        return self.v[index]

    def __setitem__(self, index, newvalue): 
        self.v[index] = newvalue

    def __eq__(self, rhs):
        if isinstance(rhs, Scalars):
            each = [v1 == v2 for (v1, v2) in list(zip(self.v, rhs.v))]
        else:
            each = [v1 == v2 for (v1, v2) in list(zip(self.v, rhs))]            
        return np.array(each).all()


class NumpyScalars:
    def __init__(self, array=None, N=None):
        if array is not None:
            self.v = np.asarray(array, dtype=np.float32)
        elif N is not None:
            self.v = np.zeros((1, N), dtype=np.float32)
            
        self._iteration = 0

    def __len__(self):
        return self.v.shape[1]

    def __add__(self, other):
        if isinstance(other, NumpyScalars):
            return NumpyScalars(np.add(self.v, other.v))
        else:
            return NumpyScalars(np.add(self.v, other))

    def __sub__(self, other):
        if isinstance(other, NumpyScalars):
            return NumpyScalars(np.subtract(self.v, other.v))
        else:
            return NumpyScalars(np.subtract(self.v, other))

    def __mul__(self, other):
        if isinstance(other, NumpyScalars):
            return NumpyScalars(np.multiply(self.v, other.v))
        elif isinstance(other, NumpyVectors):
            return NumpyScalars(np.multiply(self.v[:, None], other.v))
        else:
            return NumpyScalars(np.multiply(self.v, other))

    def __truediv__(self, other):
        if isinstance(other, NumpyScalars):
            return NumpyScalars(np.true_divide(self.v, other.v))
        elif isinstance(other, NumpyVectors):
            return NumpyScalars(np.multiply(self.v[:, None], other.v))
        else:
            return NumpyScalars(np.true_divide(self.v, other))

    def __neg__(self):
        return NumpyScalars(np.negative(self.v))

    def __getitem__(self, item):
        return self.v[:, item]

    def __setitem__(self, key, value: np.float32):
        self.v[:, key] = value

    def __eq__(self, other):
        if isinstance(other, NumpyScalars):
            return np.equal(self.v, other.v)
        else:
            return np.equal(self.v, other)

    def __iter__(self):
        self._iteration = 0
        return self

    def __next__(self):
        if self._iteration < len(self):
            result = self.v[:, self._iteration]
            self._iteration += 1
            return result
        else:
            raise StopIteration

    @classmethod
    def setAll(cls, value, N):
        return NumpyScalars(np.full((1, N), value))
        
    @classmethod
    def random(cls, N: int):
        return NumpyScalars(np.random.rand(1, N))

    @classmethod
    def random2(cls, N: int):
        return NumpyScalars((np.random.rand(1, N) * 2) - 1)
