import pathlib
from typing import List
from .parsers import Parser, OBJParser
from ..solids.solid import Solid
from ..geometry import Vector, Polygon, Triangle


class Loader:
    """
    Base class to manage the conversion between files and Scene() or Solid() from
    various types of files.
    """
    def __init__(self):
        self._filepath: str = ""
        self._fileExtension: str = ""
        self._parser = None

    def _getFileExtension(self) -> str:
        return pathlib.Path(self._filepath).suffix

    def _selectParser(self):
        ext = self._fileExtension
        if ext == ".obj":
            self._parser = OBJParser(self._filepath)

        elif ext == ".dae":
            raise NotImplementedError

        elif ext == ".zmx":
            raise NotImplementedError

        else:
            raise ValueError("This format is not supported.")

    def _convert(self) -> List[Solid]:
        solids = []
        vertices = []
        for vertex in self._parser.vertices:
            vertices.append(Vector(*vertex))

        for objectName in self._parser.objects:
            surfacesGroups = {}

            for group in self._parser.objects[objectName]["Groups"]:
                surfacesGroups[group] = []

                for polygonIndices in self._parser.objects[objectName]["Groups"][group]["Polygons"]:

                    if len(polygonIndices) == 3:
                        ai, bi, ci = polygonIndices
                        surfacesGroups[group].append(Triangle(vertices[ai], vertices[bi], vertices[ci]))

                    elif len(polygonIndices) == 4:
                        ai, bi, ci, di = polygonIndices
                        surfacesGroups[group].append(Triangle(vertices[ai], vertices[bi], vertices[ci]))
                        surfacesGroups[group].append(Triangle(vertices[ai], vertices[ci], vertices[di]))

                    elif len(polygonIndices) > 4:
                        trianglesIndices = self._splitPolygonIndices(polygonIndices)
                        print(f"Multipolygon:{len(trianglesIndices)}")
                        for triangleIndex in trianglesIndices:
                            ai, bi, ci = triangleIndex
                            surfacesGroups[group].append(Triangle(vertices[ai], vertices[bi], vertices[ci]))

            solids.append(Solid(position=Vector(0, 0, 0), vertices=vertices, surfaceDict=surfacesGroups))

        return solids

    @staticmethod
    def _splitPolygonIndices(polygonIndices: List[int]) -> List[List[int]]:
        trianglesIndices = []
        for i in range(len(polygonIndices)-2):
            trianglesIndices.append([polygonIndices[0], polygonIndices[i+1], polygonIndices[i+2]])
        return trianglesIndices

    def load(self, filepath: str) -> List[Solid]:
        self._filepath = filepath
        self._fileExtension = self._getFileExtension()
        self._selectParser()
        return self._convert()
