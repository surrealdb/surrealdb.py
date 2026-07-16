import json


class Datetime:
    def __init__(self, dt: str):
        self.dt = dt

    def __str__(self) -> str:
        """
        Renders the datetime as a valid SurrealQL datetime literal, e.g.
        ``d"2025-02-03T12:30:45.123456Z"``. The ISO string is JSON-encoded to
        get proper double-quote/backslash escaping.

        Returns:
            The SurrealQL string representation of the datetime.
        """
        return f"d{json.dumps(self.dt)}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.dt!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Datetime):
            return self.dt == other.dt
        return False

    def __hash__(self) -> int:
        return hash(self.dt)
