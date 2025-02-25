from pytissueoptics import *


class Geometry:
    def __init__(self, material=None, stats=None, label=""):
        self.material = material
        self.origin = Vector(0, 0, 0)
        self.stats = stats
        self.surfaces = []
        self.label = label
        self.inputWeight = 0

        self.epsilon = 1e-5
        self.startTime = None  # We are not calculating anything
        self.center = None

    def propagate(self, photon: Photon):
        photon.transformToLocalCoordinates(self.origin)
        self._scoreWhenStarting(photon)
        d = 0
        while photon.isAlive and self.contains(photon.r):
            # Pick distance to scattering point
            if d <= 0:
                d = self.material.getScatteringDistance()

            intersection = self.nextExitInterface(photon.r, photon.ez, d)

            if intersection is None:
                # If the scattering point is still inside, we simply move
                # Default is simply photon.moveBy(d) but other things 
                # would be here. Create a new material for other behaviour
                photon.moveBy(d)
                d = 0
                # Interact with volume: default is absorption only
                # Default is simply absorb energy. Create a Material
                # for other behaviour
                delta = photon.weight * self.material.albedo
                photon.decreaseWeightBy(delta)
                self._scoreInVolume(photon, delta)

                # Scatter within volume
                theta, phi = self.material.getScatteringAngles()
                photon.scatterBy(theta, phi)
            else:
                # If the photon crosses an interface, we move to the surface
                photon.moveBy(d=intersection.distance)

                # Determine if reflected or not with Fresnel coefficients
                if intersection.isReflected():
                    # reflect photon and keep propagating
                    photon.reflect(intersection)
                    photon.moveBy(d=1e-3)  # Move away from surface
                    d -= intersection.distance
                else:
                    # transmit, score, and leave
                    photon.refract(intersection)
                    self._scoreWhenExiting(photon)
                    photon.moveBy(d=1e-3)  # We make sure we are out
                    break

            # And go again
            photon.roulette()

        # Because the code will not typically calculate millions of photons, it is
        # inexpensive to keep all the propagated photons.  This allows users
        # to go through the list after the fact for a calculation of their choice
        self._scoreWhenFinal(photon)
        photon.transformFromLocalCoordinates(self.origin)

    def propagateMany(self, photons):
        """
        Photons represents a group of photons that will propagate in an object.
        We will treat photons as "groups": some will propagate unimpeded and some 
        will hit an obstacle.  Those that hit an obstacle may reflect or transmit through it.

        We continue until all photons have died within the geometry or transmitted through 
        some interface. We will return the photons that have exited the geometry.
        """

        photonsInside = photons
        photonsInside.transformToLocalCoordinates(self.origin)
        self._scoreManyWhenStarting(photonsInside)
        photonsExited = Photons()

        while not photonsInside.isEmpty:
            distances = self.material.getManyScatteringDistances(photonsInside)
            # Split photons into two groups: those freely propagating and those hitting some interface.
            # We determine the groups based on the photons (and their positions) and the interaction
            # distances (calculated above). For those hitting an interface, we provide a list of 
            # corresponding interfaces
            (unimpededPhotons, unimpededDistances), (impededPhotons, interfaces) = self._getPossibleIntersections(
                photonsInside, distances)

            # We now deal with both groups (unimpeded and impeded photons) independently
            # ==========================================
            # 1. Unimpeded photons: they simply propagate through the geometry without anything special
            unimpededPhotons.moveBy(unimpededDistances)
            deltas = unimpededPhotons.decreaseWeight(self.material.albedo)
            self._scoreManyInVolume(unimpededPhotons, deltas)  # optional
            thetas, phis = self.material.getManyScatteringAngles(unimpededPhotons)
            unimpededPhotons.scatterBy(thetas, phis)

            # 2. Impeded photons: they propagate to the interface, then will either be reflected or transmitted

            impededPhotons.moveBy(interfaces.distance)
            (reflectedPhotons, reflectedInterfaces), (
                transmittedPhotons, transmittedInterfaces) = impededPhotons.areReflected(interfaces)

            # 2.1 Reflected photons change their direction following Fresnel reflection, then move inside

            reflectedPhotons.reflect(reflectedInterfaces)
            # reflectedPhotons.moveBy(remainingDistances) #FIXME: there could be another interface

            # 2.2 Transmitted photons change their direction following the law of refraction, then move 
            #     outside the object and are stored to be returned and propagated into another object.
            transmittedPhotons.refract(transmittedInterfaces)
            transmittedPhotons.moveBy(1e-6)
            self._scoreManyWhenExiting(transmittedPhotons, interfaces)  # optional

            photonsInside = Photons()
            photonsInside.append(unimpededPhotons)
            photonsInside.append(reflectedPhotons)

            # 3. Low-weight photons are randomly killed while keeping energy constant.
            photonsInside.roulette()
            photonsExited.append(transmittedPhotons)

        # Because the code will not typically calculate millions of photons, it is
        # inexpensive to keep all the propagated photons.  This allows users
        # to go through the list after the fact for a calculation of their choice
        # self.scoreWhenFinal(photons)
        photonsExited.transformFromLocalCoordinates(self.origin)

    def contains(self, position) -> bool:
        """ The base object is infinite. Subclasses override this method
        with their specific geometry. 

        It is important that this function be efficient: it is called
        very frequently. See implementations for Box, Sphere and Layer
        """
        return True

    def containsMany(self, finalPositions, photons):
        return Scalars([True] * len(photons))

    def nextEntranceInterface(self, position, direction, distance) -> FresnelIntersect:
        """ Is this line segment from position to distance*direction crossing
        any surface elements of this object? Valid from outside the object.

        This will be very slow: going through all elements to check for
        an intersection is abysmally slow
        and increases linearly with the number of surface elements
        There are tons of strategies to improve this (axis-aligned boxes,
        oriented boxes but most importantly KDTree and OCTrees).
        It is not done here, we are already very slow: what's more slowdown
        amongst friends? """

        minDistance = distance
        intersectSurface = None
        for surface in self.surfaces:
            if direction.dot(surface.normal) >= 0:
                # Parallel or outward, does not apply
                continue
            # Going inward, against surface normal
            isIntersecting, distanceToSurface = surface.intersection(position, direction, distance)
            if isIntersecting and distanceToSurface < minDistance:
                intersectSurface = surface
                minDistance = distanceToSurface

        if intersectSurface is None:
            return None
        return FresnelIntersect(direction, intersectSurface, minDistance, self)

    def scoreWhenEntering(self, photon, surface):
        return

    def validateGeometrySurfaceNormals(self):
        manyPhotons = IsotropicSource(maxCount=10000)
        assert (self.contains(self.center))
        maxDist = 1000000
        for photon in manyPhotons:
            direction = Vector(photon.ez)
            origin = Vector(self.center)
            final = origin + direction * maxDist

            # We trace a line from the center to far away.
            intersect = self.nextEntranceInterface(position=origin, direction=direction, distance=maxDist)
            assert (intersect is None)  # Because we are leaving, not entering

            intersect = self.nextExitInterface(position=origin, direction=direction, distance=maxDist)
            assert (intersect is not None)
            assert (intersect.surface.contains(self.center + intersect.distance * direction))
            assert (intersect.indexIn == intersect.surface.indexInside)
            assert (intersect.indexOut == 1.0)
            assert (intersect.geometry == self)

            # We trace a line from far away to the center
            origin = final
            direction = -direction

            intersect = self.nextExitInterface(position=origin, direction=direction, distance=maxDist)
            assert (intersect is None)  # Because we are entering, not leaving

            intersect = self.nextEntranceInterface(position=origin, direction=direction, distance=maxDist)
            assert (intersect is not None)
            assert (intersect.surface.contains(origin + intersect.distance * direction))
            assert (intersect.indexIn == intersect.surface.indexOutside)
            assert (intersect.indexOut == intersect.surface.indexInside)
            assert (intersect.geometry == self)

    def report(self, totalSourcePhotons, graphs=True):
        print("{0}".format(self.label))
        print("=====================\n")
        print("Geometry and material")
        print("---------------------")
        print(self)

        print("\nPhysical quantities")
        print("---------------------")
        if self.stats is not None:
            for i, surface in enumerate(self.surfaces):
                print("Transmittance [{0}] : {1:.1f}% of propagating light".format(surface,
                                                                                   100 * self.stats.transmittance(
                                                                                       [surface], geometryOrigin=self.origin)))
                print("Transmittance [{0}] : {1:.1f}% of total power".format(surface,
                                                                             100 * self.stats.transmittance(
                                                                                 [surface],
                                                                                 referenceWeight=totalSourcePhotons,
                                                                                 geometryOrigin=self.origin)))

            print("Absorbance : {0:.1f}% of propagating light".format(100 * self.stats.absorbance()))
            print("Absorbance : {0:.1f}% of total power".format(100 * self.stats.absorbance(totalSourcePhotons)))

            totalCheck = self.stats.totalWeightAcrossAllSurfaces(self.surfaces, geometryOrigin=self.origin) + self.stats.totalWeightAbsorbed()
            print("Absorbance + Transmittance = {0:.1f}%".format(100 * totalCheck / self.stats.inputWeight))

            if graphs:
                self.stats.showEnergy2D(plane='xz', integratedAlong='y', title="Final photons", realtime=False)
                if len(self.surfaces) != 0:
                    self.stats.showSurfaceIntensities(self.surfaces, maxPhotons=totalSourcePhotons, geometryOrigin=self.origin)

    def nextExitInterface(self, position, direction, distance) -> FresnelIntersect:
        """ Is this line segment from position to distance*direction leaving
        the object through any surface elements? Valid only from inside the object.
        
        This function is a very general function
        to find if a photon will leave the object.  `contains` is called
        repeatedly, is geometry-specific, and must be high performance. 
        It may be possible to write a specialized version for a subclass,
        but this version will work by default for all objects and is 
        surprisingly efficient.
        """

        finalPosition = Vector.fromScaledSum(position, direction, distance)
        if self.contains(finalPosition):
            return None

        # At this point, we know we will cross an interface: position is inside
        # finalPosition is outside.
        wasInside = True
        finalPosition = Vector(position)  # Copy
        delta = 0.5 * distance

        while abs(delta) > 0.00001:
            finalPosition += delta * direction
            isInside = self.contains(finalPosition)

            if isInside != wasInside:
                delta = -delta * 0.5

            wasInside = isInside

        for surface in self.surfaces:
            if surface.normal.dot(direction) > 0:
                if surface.contains(finalPosition):
                    distanceToSurface = (finalPosition - position).abs()
                    return FresnelIntersect(direction, surface, distanceToSurface)

        return None

    def _getPossibleIntersections(self, photons, distances):
        if photons.isRowOptimized:
            unimpededPhotons = Photons()
            impededPhotons = Photons()
            interfaces = FresnelIntersects()
            unimpededDistances = Scalars()

            for i, p in enumerate(photons):
                interface = self.nextExitInterface(p.r, p.ez, distances[i])
                if interface is not None:
                    interfaces.append(interface)
                    impededPhotons.append(p)

                else:
                    unimpededPhotons.append(p)
                    unimpededDistances.append(distances[i])

            return (unimpededPhotons, unimpededDistances), (impededPhotons, interfaces)

        elif photons.isColumnOptimized:
            unimpededPhotons = Photons()
            impededPhotons = Photons()
            interfaces = FresnelIntersects()
            unimpededDistances = Scalars()

            for i, p in enumerate(photons):
                interface = self.nextExitInterface(p.r, p.ez, distances[i])
                if interface is not None:
                    interfaces.append(interface)
                    impededPhotons.append(p)

                else:
                    unimpededPhotons.append(p)
                    unimpededDistances.append(distances[i])

            return (unimpededPhotons, unimpededDistances), (impededPhotons, interfaces)

    def _scoreWhenStarting(self, photon):
        if self.stats is not None:
            self.stats.scoreWhenStarting(photon)

    def _scoreManyWhenStarting(self, photons):
        if self.stats is not None:
            for photon in photons:
                self._scoreWhenStarting(photon)
        # if self.stats is not None:
        #     map(lambda photon, delta: self.scoreWhenStarting(photon), photons)

    def _scoreInVolume(self, photon, delta):
        if self.stats is not None:
            self.stats.scoreInVolume(photon, delta)

    def _scoreManyInVolume(self, photons, deltas):
        if self.stats is not None:
            for photon, delta in zip(photons, deltas):
                self._scoreInVolume(photon, delta)
        # map(lambda photon, delta: self.scoreWhenStarting(photon), photons)

    def _scoreWhenExiting(self, photon):
        if self.stats is not None:
            self.stats.scoreWhenCrossing(photon)

    def _scoreManyWhenExiting(self, photons, intersects):
        if self.stats is not None:
            for photon, intersect in zip(photons, intersects):
                self._scoreWhenExiting(photon)
        # if self.stats is not None:
        #     map(lambda photon, delta: self.scoreWhenExiting(photon), photons)

    def _scoreWhenFinal(self, photon):
        if self.stats is not None:
            self.stats.scoreWhenFinal(photon)

    def __repr__(self):
        return "{0}".format(self)

    def __str__(self):
        string = "'{0}' {2} with surfaces {1}\n".format(self.label, self.surfaces, self.origin)
        string += "{0}".format(self.material)
        return string


class Box(Geometry):
    def __init__(self, size, material, stats=None, label="Box"):
        super(Box, self).__init__(material, stats, label)
        self.size = size
        self.surfaces = [-XYPlane(atZ=-self.size[2] / 2, description="Front"),
                         XYPlane(atZ=self.size[2] / 2, description="Back"),
                         -YZPlane(atX=-self.size[0] / 2, description="Left"),
                         YZPlane(atX=self.size[0] / 2, description="Right"),
                         -ZXPlane(atY=-self.size[1] / 2, description="Bottom"),
                         ZXPlane(atY=self.size[1] / 2, description="Top")]
        self.center = ConstVector(0, 0, 0)

    def contains(self, localPosition) -> bool:
        if abs(localPosition.z) > self.size[2] / 2:
            return False
        if abs(localPosition.y) > self.size[1] / 2:
            return False
        if abs(localPosition.x) > self.size[0] / 2:
            return False

        return True


class Cube(Box):
    def __init__(self, side, material, stats=None, label="Cube"):
        super(Cube, self).__init__((side, side, side), material, stats, label)


class Layer(Geometry):
    def __init__(self, thickness, material, stats=None, label="Layer"):
        super(Layer, self).__init__(material, stats, label)
        self.thickness = thickness
        self.surfaces = [-XYPlane(atZ=0, description="Front"),
                         XYPlane(atZ=self.thickness, description="Back")]
        self.center = ConstVector(0, 0, thickness / 2)

    def contains(self, localPosition) -> bool:
        if localPosition.z < 0:
            return False
        if localPosition.z > self.thickness:
            return False

        return True

    def nextExitInterface(self, position, direction, distance) -> FresnelIntersect:
        finalPosition = Vector.fromScaledSum(position, direction, distance)
        if self.contains(finalPosition):
            return None
        # assert(self.contains(position) == True)

        if direction.z > 0:
            d = (self.thickness - position.z) / direction.z
            if d <= distance:
                s = self.surfaces[1]
                intersect = FresnelIntersect(direction, self.surfaces[1], d, geometry=self)
                # assert(s.indexInside)
                # print(s.indexInside, s.indexOutside)
                # print(intersect.indexIn, intersect.indexOut)
                return intersect
        elif direction.z < 0:
            d = - position.z / direction.z
            if d <= distance:
                s = self.surfaces[0]
                intersect = FresnelIntersect(direction, self.surfaces[0], d, geometry=self)
                # print(s.indexInside, s.indexOutside)
                # print(intersect.indexIn, intersect.indexOut)
                return intersect

        return None


class SemiInfiniteLayer(Geometry):
    """ This class is actually a bad idea: the photons don't exit
    on the other side and will just take a long time to propagate.
    It is better to use a finite layer with a thickness a bit larger
    than what you are interested in."""

    def __init__(self, material, stats=None, label="Semi-infinite layer"):
        super(SemiInfiniteLayer, self).__init__(material, stats, label)
        self.surfaces = [-XYPlane(atZ=0, description="Front")]
        self.center = ConstVector(0, 0, 1)

    def contains(self, localPosition) -> bool:
        if localPosition.z < 0:
            return False

        return True

    def nextExitInterface(self, position, direction, distance) -> FresnelIntersect:
        finalPosition = position + distance * direction
        if self.contains(finalPosition):
            return None
        assert self.contains(position)

        if direction.z < 0:
            d = - position.z / direction.z
            if d <= distance:
                return FresnelIntersect(direction, self.surfaces[0], d, geometry=self)

        return None


# class Sphere(Geometry):
#     def __init__(self, radius, material, stats=None, label="Sphere"):
#         super(Sphere, self).__init__(position, material, stats, label)
#         self.radius = radius

#     def contains(self, localPosition) -> bool:
#         if localPosition.abs() > self.radius + self.epsilon:
#             return False

#         return True

class KleinBottle(Geometry):
    def __init__(self, position, material, stats=None):
        super(KleinBottle, self).__init__(position, material, stats)

    def contains(self, localPosition) -> bool:
        raise NotImplementedError()
