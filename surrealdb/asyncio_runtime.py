import asyncio


class AsyncController(type):

    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


class AsyncioRuntime(metaclass=AsyncController):
    """
    The AsyncioRuntime class is a singleton class that is responsible for
    managing the asyncio event loop and running the SurrealDB instance.
    """

    def __init__(self) -> None:
        """
        The constructor for the AsyncioRuntime class.
        """
        self.loop = self._init_runtime()

    @staticmethod
    def _init_runtime():
        """
        Defines the asyncio event loop.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop
