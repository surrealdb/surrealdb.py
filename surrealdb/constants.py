import os

REQUEST_ID_LENGTH = 10

# Connection
HTTP_CONNECTION_SCHEMES = ["http", "https"]
WS_CONNECTION_SCHEMES = ["ws", "wss"]
CLIB_CONNECTION_SCHEMES = ["memory", "surrealkv"]
ALLOWED_CONNECTION_SCHEMES = (
    HTTP_CONNECTION_SCHEMES + WS_CONNECTION_SCHEMES + CLIB_CONNECTION_SCHEMES
)

DEFAULT_CONNECTION_URL = "http://127.0.0.1:8000"

# Methods
UNSUPPORTED_HTTP_METHODS = ["kill", "live"]

# Paths
ROOT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
CLIB_FOLDER_PATH = os.path.join(ROOT_DIR, "libsrc")

WS_REQUEST_TIMEOUT = 10  # seconds
