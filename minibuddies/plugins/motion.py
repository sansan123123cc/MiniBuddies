"""Position and facing timelines shared by runtime playback and the editor."""

from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass, field


DISTANCE_LIMIT = 300
HEIGHT_LIMIT = 150
EASINGS = ("linear", "ease-in", "ease-out", "ease-in-out")
TURN_DIRECTIONS = ("left", "right", "flip", "target")
INTERACTION_GAP = 1.6
FOLLOW_SPEED_LIMIT = 10


@dataclass(frozen=True)
class Travel:
    distance: int
    height: int
    easing: str


@dataclass(frozen=True)
class Turn:
    direction: str
    target: str | None = None


@dataclass(frozen=True)
class Follow:
    target: str
    distance: int
    speed: int


@dataclass(frozen=True)
class MotionActor:
    x: float
    face: int
    size: float
    limits: tuple | None = None


@dataclass(frozen=True)
class MotionPose:
    x: float
    lift: float
    face: int


@dataclass(frozen=True)
class MotionSegment:
    start: float
    end: float
    ticks: int
    lift: float
    easing: str
    face: int
    follow: Follow | None
    positions: list = field(default_factory=list)


class MotionTrack:
    def __init__(self, actor):
        self.actor = actor
        self.starts = []
        self.segments = []

    def add(self, beat, target_x):
        current = self.pose(beat.at)
        face = current.face
        if beat.turn:
            direction = beat.turn.direction
            if direction == "target":
                if target_x != current.x:
                    face = 1 if target_x > current.x else -1
            else:
                face = {"left": -1, "right": 1, "flip": -face}[direction]
        move = beat.move
        scale = self.actor.size / 100
        end = current.x
        if move and move.distance:
            end = self.clamp(end + face * move.distance * scale)
        self.starts.append(beat.at)
        self.segments.append(MotionSegment(current.x, end, beat.ticks, move.height * scale if move else 0,
                                           move.easing if move else "linear", face, beat.follow, [current.x]))

    def clamp(self, x):
        if self.actor.limits is None:
            return x
        left, right = self.actor.limits
        return min(max(x, left), right)

    def follow_at(self, tick, positions):
        segment = self.segments[-1] if self.segments else None
        if segment is None or not segment.follow or tick - self.starts[-1] > segment.ticks:
            return
        follow = segment.follow
        x = segment.positions[-1]
        delta = positions[follow.target] - x
        scale = self.actor.size / 100
        distance = min(max(abs(delta) - follow.distance * scale, 0), follow.speed * scale)
        segment.positions.append(self.clamp(x + (distance if delta > 0 else -distance)))

    def pose(self, tick):
        index = bisect_right(self.starts, tick) - 1
        if index < 0:
            return MotionPose(self.actor.x, 0, self.actor.face)
        segment = self.segments[index]
        elapsed = tick - self.starts[index]
        if segment.follow:
            return MotionPose(segment.positions[min(elapsed, len(segment.positions) - 1)], 0, segment.face)
        progress = min(elapsed / segment.ticks, 1)
        eased = progress
        if segment.easing == "ease-in":
            eased = progress ** 2
        elif segment.easing == "ease-out":
            eased = 1 - (1 - progress) ** 2
        elif segment.easing == "ease-in-out":
            eased = progress ** 2 * (3 - 2 * progress)
        return MotionPose(segment.start + (segment.end - segment.start) * eased,
                          4 * segment.lift * progress * (1 - progress), segment.face)

    def extents(self):
        ends = [self.actor.x]
        for segment in self.segments:
            ends.extend((min(segment.positions), max(segment.positions)) if segment.follow else (segment.end,))
        return min(ends), max(ends), max((segment.lift for segment in self.segments), default=0)

    def displaces(self):
        left, right, lift = self.extents()
        return left != right or lift > 0


def compile_motion(actors, sequences):
    tracks = {key: MotionTrack(actor) for key, actor in actors.items()}
    beats = defaultdict(list)
    follow_until = 0
    for key, sequence in sequences.items():
        for beat in sequence:
            if beat.move or beat.turn or beat.follow:
                beats[beat.at].append((key, beat))
            if beat.follow:
                follow_until = max(follow_until, beat.at + beat.ticks)
    ticks = sorted(beats.keys() | set(range(1, follow_until + 1)))
    for tick in ticks:
        positions = {key: track.pose(tick).x for key, track in tracks.items()}
        if tick <= follow_until:
            for track in tracks.values():
                track.follow_at(tick, positions)
            positions = {key: track.pose(tick).x for key, track in tracks.items()}
        for key, beat in beats.get(tick, ()):
            target_x = positions[beat.turn.target] if beat.turn and beat.turn.target else None
            tracks[key].add(beat, target_x)
    return tracks


def grounded_actor(pet):
    screen = pet.scr()
    left, _, right = pet.surface
    low = max(left + 1, screen.left() + pet.S / 2)
    high = min(right - 1, screen.right() + 1 - pet.S / 2)
    limits = (low, high) if low <= high else (pet.cx, pet.cx)
    return MotionActor(pet.cx, pet.face, pet.S, limits)


def apply_motion(pet, track, tick):
    pose = track.pose(tick)
    pet.fx = pose.x - pet.S / 2
    pet.face = pose.face
    ground_y = pet.surface[1] - pet.S * pet.fbottom(pet.frame())
    lift = min(pose.lift, max(0, ground_y - pet.scr().top())) if pose.lift else 0
    pet.fy = ground_y - lift
