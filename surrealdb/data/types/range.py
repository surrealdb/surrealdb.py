from dataclasses import dataclass


class Bound:
    def __init__(self):
        pass


@dataclass
class BoundIncluded(Bound):
    def __init__(self, value):
        super().__init__()
        self.value = value


@dataclass
class BoundExcluded(Bound):
    def __init__(self, value):
        super().__init__()
        self.value = value


@dataclass
class Range:
    begin: Bound
    end: Bound
