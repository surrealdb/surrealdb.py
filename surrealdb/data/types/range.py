from dataclasses import dataclass


class Bound:
    def __init__(self):
        pass


class BoundIncluded(Bound):
    def __init__(self, value):
        super().__init__()
        self.value = value


class BoundExcluded(Bound):
    def __init__(self, value):
        super().__init__()
        self.value = value


@dataclass
class Range:
    begin: Bound
    end: Bound

