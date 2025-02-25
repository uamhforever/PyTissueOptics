from pytissueoptics import Geometry, Source, Detector, Material, Photon, Photons
from typing import List
import signal
import time

from pytissueoptics.intersectionFinder import SimpleIntersectionFinder


class World:
    def __init__(self):
        self.geometries: List[Geometry] = []
        self.sources: List[Source] = []
        self.verbose = False
        self.countNotSupposedToBeThere = 0

    def place(self, anObject, position):
        if isinstance(anObject, Geometry) or isinstance(anObject, Detector):
            anObject.origin = position
            self.geometries.append(anObject)
        elif isinstance(anObject, Source):
            anObject.origin = position
            self.sources.append(anObject)

    def oldCompute(self, graphs=True, progress=False):
        self._startCalculation()
        N = 0
        for source in self.sources:
            N += source.maxCount

            for i, photon in enumerate(source):
                currentGeometry = self._contains(photon.globalPosition)
                while photon.isAlive:
                    if currentGeometry is not None:
                        # We are in an object, propagate in it
                        currentGeometry.propagate(photon)
                        # Then check if we are in another adjacent object
                        currentGeometry = self._contains(photon.globalPosition)
                    else:
                        self._propagate(photon)
                if progress:
                    self._showProgress(i + 1, maxCount=source.maxCount, graphs=graphs)

        duration = self._completeCalculation()
        if progress:
            print("{0:.1f} ms per photon\n".format(duration * 1000 / N))

    def oldComputeMany(self, graphs=False):
        self._startCalculation()
        N = 0
        for source in self.sources:
            N += source.maxCount
            photons = Photons(list(source))

            while not photons.isEmpty:
                geometries = self.assignCurrentGeometries(photons)
                for i, geometry in enumerate(geometries):
                    if geometry is not None:
                        photonsInGeometry = photons.livePhotonsInGeometry(geometry)
                        print(photonsInGeometry.liveCount(), geometry)
                        geometry.propagateMany(photonsInGeometry)

        duration = self._completeCalculation()
        print("I should not be here: {}".format(self.countNotSupposedToBeThere))
        print("{0:.1f} ms per photon\n".format(duration * 1000 / N))

    def compute(self, stats: 'Stats' = None):
        """ New implementation of "compute" using richer domain.
            This method acts as an application context. """
        self._startCalculation()

        worldMaterial = Material()
        intersectionFinder = SimpleIntersectionFinder(geometries=self.geometries)

        for i, photon in enumerate(self.photons):
            photon.setContext(worldMaterial, intersectionFinder, stats)
            photon.propagate()

    @property
    def photons(self) -> List[Photon]:
        photons = []
        for source in self.sources:
            photons.extend(source.getPhotons())
        return photons

    def report(self, graphs=True):
        for geometry in self.geometries:
            geometry.report(totalSourcePhotons=self._totalSourcePhotons(), graphs=graphs)

    def _totalSourcePhotons(self) -> float:
        total = 0
        for source in self.sources:
            total += source.maxCount
        return total

    def _propagate(self, photon):
        if photon.currentGeometry != self:
            self.countNotSupposedToBeThere += 1
            photon.weight = 0
            return

        while photon.isAlive and photon.currentGeometry == self:
            intersection = self._nextObstacle(photon)
            if intersection is not None:
                # We are hitting something, moving to surface
                photon.moveBy(intersection.distance)
                # At surface, determine if reflected or not
                if intersection.isReflected():
                    # reflect photon and keep propagating
                    photon.reflect(intersection)
                    # Move away from surface to avoid getting stuck there
                    photon.moveBy(d=1e-3)
                else:
                    # transmit, score, and enter (at top of this loop)
                    photon.refract(intersection)
                    intersection.geometry.scoreWhenEntering(photon, intersection.surface)
                    # Move away from surface to avoid getting stuck there
                    photon.moveBy(d=1e-3)
                    photon.currentGeometry = intersection.geometry
            else:
                photon.weight = 0

    def _contains(self, worldCoordinates):
        for geometry in self.geometries:
            localCoordinates = worldCoordinates - geometry.origin
            if geometry.contains(localCoordinates):
                return geometry
        return None

    def _nextObstacle(self, photon):
        if not photon.isAlive:
            return None
        distance = 1e7
        shortestDistance = distance
        closestIntersect = None
        for geometry in self.geometries:
            photon.transformToLocalCoordinates(geometry.origin)
            someIntersection = geometry.nextEntranceInterface(photon.r, photon.ez, distance=shortestDistance)
            if someIntersection is not None:
                if someIntersection.distance < shortestDistance:
                    shortestDistance = someIntersection.distance
                    closestIntersect = someIntersection

            photon.transformFromLocalCoordinates(geometry.origin)

        return closestIntersect

    def assignCurrentGeometries(self, photons):
        geometries = set()
        for photon in photons:
            currentGeometry = self.assignCurrentGeometry(photon)
            geometries.add(currentGeometry)

        return list(geometries)

    def _startCalculation(self):
        if 'SIGUSR1' in dir(signal) and 'SIGUSR2' in dir(signal):
            # Trick to send a signal to code as it is running on Unix and derivatives
            # In the shell, use `kill -USR1 processID` to get more feedback
            # use `kill -USR2 processID` to force a save
            signal.signal(signal.SIGUSR1, self._processSignal)
            signal.signal(signal.SIGUSR2, self._processSignal)

        if len(self.geometries) == 0:
            raise SyntaxError("No geometries: you must create objects")

        for geometry in self.geometries:
            for surface in geometry.surfaces:
                surface.indexInside = geometry.material.index
                surface.indexOutside = 1.0  # Index outside
            try:
                geometry.validateGeometrySurfaceNormals()
            except Exception as err:
                print("The geometry {0} appears invalid. Advancing cautiously.".format(geometry, err))

        if len(self.sources) == 0:
            raise SyntaxError("No sources: you must create sources")

        self.startTime = time.time()

    def _completeCalculation(self) -> float:
        if 'SIGUSR1' in dir(signal) and 'SIGUSR2' in dir(signal):
            signal.signal(signal.SIGUSR1, signal.SIG_DFL)
            signal.signal(signal.SIGUSR2, signal.SIG_DFL)

        elapsed = time.time() - self.startTime
        self.startTime = None
        return elapsed

    def _processSignal(self, signum, frame):
        if signum == signal.SIGUSR1:
            self.verbose = not self.verbose
            print('Toggling verbose to {0}'.format(self.verbose))
        elif signum == signal.SIGUSR2:
            print("Requesting save (not implemented)")

    def _showProgress(self, i, maxCount, graphs=False):
        steps = 100

        if not self.verbose:
            while steps < i:
                steps *= 10

        if i % steps == 0:
            print("{2} Photon {0}/{1}".format(i, maxCount, time.ctime()))

            if graphs:
                for geometry in self.geometries:
                    if geometry.stats is not None:
                        geometry.stats.showEnergy2D(plane='xz', integratedAlong='y', title="{0} photons".format(i))
