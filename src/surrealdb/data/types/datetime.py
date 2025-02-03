from datetime import datetime


class DatetimeWrapper:

    def __init__(self, dt: datetime):
        self.dt = dt

    @staticmethod
    def now() -> "DatetimeWrapper":
        return DatetimeWrapper(datetime.now())


class IsoDateTimeWrapper:

    def __init__(self, dt: str):
        self.dt = dt
