import os

REQUEST_ID_LENGTH = 10

# methods
METHOD_USE = "use"
METHOD_SIGN_IN = "signin"
METHOD_SIGN_UP = "signup"
METHOD_INFO = "info"
METHOD_VERSION = "version"
METHOD_AUTHENTICATE = "authenticate"
METHOD_INVALIDATE = "invalidate"
METHOD_SET = "let"
METHOD_UNSET = "unset"
METHOD_SELECT = "select"
METHOD_QUERY = "query"
METHOD_CREATE = "create"
METHOD_INSERT = "insert"
METHOD_PATCH = "patch"
METHOD_MERGE = "merge"
METHOD_UPDATE = "update"
METHOD_UPSERT = "upsert"
METHOD_DELETE = "delete"
METHOD_LIVE = "live"
METHOD_KILL = "kill"

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
