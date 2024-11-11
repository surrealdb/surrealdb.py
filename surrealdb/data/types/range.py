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


class Range:
    def __init__(self, begin: Bound, end: Bound):
        self.begin = begin
        self.end = end
