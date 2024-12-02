import logging
import os
import ctypes
import platform

from surrealdb.errors import SurrealDbConnectionError
from surrealdb.connection import Connection, RequestData
from surrealdb.constants import CLIB_FOLDER_PATH, METHOD_USE, METHOD_SET, METHOD_UNSET


def get_lib_path() -> str:
    if platform.system() == "Linux":
        lib_extension = ".so"
    elif platform.system() == "Darwin":
        lib_extension = ".dylib"
    elif platform.system() == "Windows":
        lib_extension = ".dll"
    else:
        raise SurrealDbConnectionError("Unsupported operating system")

    lib_path = os.path.join(CLIB_FOLDER_PATH, f"libsurrealdb_c{lib_extension}")
    if os.path.isfile(lib_path) is not True:
        raise Exception(f"{lib_path} is missing")

    return lib_path


class sr_string_t(ctypes.c_char_p):
    pass


class sr_option_t(ctypes.Structure):
    _fields_ = [
        ("strict", ctypes.c_bool),
        ("query_timeout", ctypes.c_uint8),
        ("transaction_timeout", ctypes.c_uint8),
    ]


class sr_surreal_rpc_t(ctypes.Structure):
    pass


class sr_RpcStream(ctypes.Structure):
    pass


class sr_uuid_t(ctypes.Structure):
    _fields_ = [("_0", ctypes.c_uint8 * 16)]


class sr_value_t_Tag(ctypes.c_int):
    SR_VALUE_NONE = 0
    SR_VALUE_NULL = 1
    SR_VALUE_BOOL = 2
    SR_VALUE_NUMBER = 3
    SR_VALUE_STRAND = 4
    SR_VALUE_DURATION = 5
    SR_VALUE_DATETIME = 6
    SR_VALUE_UUID = 7
    SR_VALUE_ARRAY = 8
    SR_VALUE_OBJECT = 9
    SR_VALUE_BYTES = 10
    SR_VALUE_THING = 11


class sr_value_t(ctypes.Structure):
    _fields_ = [("tag", sr_value_t_Tag), ("sr_value_bool", ctypes.c_bool)]


class sr_notification_t(ctypes.Structure):
    _fields_ = [
        ("query_id", sr_uuid_t),
        ("action", ctypes.c_int),  # sr_action
        ("data", sr_value_t),
    ]


class CLibConnection(Connection):
    def __init__(self, base_url: str, logger: logging.Logger, encoder, decoder):
        super().__init__(base_url, logger, encoder, decoder)

        lib_path = get_lib_path()
        self._lib = ctypes.CDLL(lib_path)

        self._c_surreal_rpc = None
        self._c_surreal_stream = None

    def set_up_lib(self):
        # int sr_surreal_rpc_new(
        #   sr_string_t *err_ptr,
        #   struct sr_surreal_rpc_t **surreal_ptr,
        #   const char *endpoint,
        #   struct sr_option_t options);
        self._lib.sr_surreal_rpc_new.argtypes = [
            ctypes.POINTER(sr_string_t),  # sr_string_t *err_ptr
            ctypes.POINTER(
                ctypes.POINTER(sr_surreal_rpc_t)
            ),  # struct sr_surreal_rpc_t **surreal_ptr
            ctypes.c_char_p,  # const char *endpoint
            sr_option_t,  # struct sr_option_t options
        ]
        self._lib.sr_surreal_rpc_new.restype = ctypes.c_int

        # int sr_surreal_rpc_notifications(
        #   const struct sr_surreal_rpc_t *self,
        #   sr_string_t *err_ptr,
        #   struct sr_RpcStream **stream_ptr);
        self._lib.sr_surreal_rpc_notifications.argtypes = [
            ctypes.POINTER(sr_surreal_rpc_t),  # const sr_surreal_rpc_t *self
            ctypes.POINTER(sr_string_t),  # sr_string_t *err_ptr
            ctypes.POINTER(
                ctypes.POINTER(sr_RpcStream)
            ),  # struct sr_RpcStream **stream_ptr
        ]
        self._lib.sr_surreal_rpc_notifications.restype = ctypes.c_int

        # int sr_surreal_rpc_execute(
        #   const struct sr_surreal_rpc_t *self,
        #   sr_string_t *err_ptr,
        #   uint8_t **res_ptr,
        #   const uint8_t *ptr,
        #   int len
        # );
        self._lib.sr_surreal_rpc_execute.argtypes = [
            ctypes.POINTER(sr_surreal_rpc_t),  # const sr_surreal_rpc_t *self
            ctypes.POINTER(sr_string_t),  # sr_string_t *err_ptr
            ctypes.POINTER(ctypes.POINTER(ctypes.c_uint8)),  # uint8_t **res_ptr
            ctypes.POINTER(ctypes.c_uint8),  # const uint8_t *ptr
            ctypes.c_int,  # int len
        ]
        self._lib.sr_surreal_rpc_execute.restype = ctypes.c_int

        # sr_stream_next
        self._lib.sr_stream_next.argtypes = [
            ctypes.POINTER(sr_RpcStream),  # const sr_stream_t *self
            ctypes.POINTER(sr_notification_t),  # sr_notification_t *notification_ptr
        ]
        self._lib.sr_stream_next.restype = ctypes.c_int

        # sr_stream_kill
        self._lib.sr_stream_kill.argtypes = [ctypes.POINTER(sr_RpcStream)]
        self._lib.sr_stream_kill.restype = None

        # sr_free_string
        self._lib.sr_free_string.argtypes = [sr_string_t]
        self._lib.sr_free_string.restype = None

        # sr_free_byte_arr
        self._lib.sr_free_byte_arr.argtypes = [
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_int,
        ]
        self._lib.sr_free_byte_arr.restype = None

    async def connect(self):
        c_err = sr_string_t()
        c_rpc_connection = ctypes.POINTER(sr_surreal_rpc_t)()
        c_endpoint = bytes(self._base_url, "utf-8")
        c_options = sr_option_t(strict=True, query_timeout=10, transaction_timeout=20)

        try:
            if (
                self._lib.sr_surreal_rpc_new(
                    ctypes.byref(c_err),
                    ctypes.byref(c_rpc_connection),
                    c_endpoint,
                    c_options,
                )
                < 0
            ):
                raise SurrealDbConnectionError(
                    f"Error connecting to RPC. {c_err.value.decode()}"
                )
            self._c_surreal_rpc = c_rpc_connection

        except Exception as e:
            raise SurrealDbConnectionError("cannot connect db server", e)
        finally:
            self._lib.sr_free_string(c_err)

    async def close(self):
        pass

    async def use(self, namespace: str, database: str) -> None:
        self._namespace = namespace
        self._database = database

        await self.send(METHOD_USE, namespace, database)

    async def set(self, key: str, value):
        await self.send(METHOD_SET, key, value)

    async def unset(self, key: str):
        await self.send(METHOD_UNSET, key)

    async def _make_request(self, request_data: RequestData):
        request_payload = self._encoder(
            {
                "id": request_data.id,
                "method": request_data.method,
                "params": request_data.params,
            }
        )

        c_err = sr_string_t()
        c_res_ptr = ctypes.POINTER(ctypes.c_uint8)()
        payload_len = len(request_payload)

        # Call sr_surreal_rpc_execute
        result = self._lib.sr_surreal_rpc_execute(
            self._c_surreal_rpc,
            ctypes.byref(c_err),
            ctypes.byref(c_res_ptr),
            (ctypes.c_uint8 * payload_len)(*request_payload),
            payload_len,
        )

        if result < 0:
            raise SurrealDbConnectionError(
                f"Error executing RPC: {c_err.value.decode() if c_err.value else 'Unknown error'}"
            )

        # Convert the result pointer to a Python byte array
        response = ctypes.string_at(c_res_ptr, result)

        # Free the allocated byte array returned by the C library
        self._lib.sr_free_byte_arr(c_res_ptr, result)
        response_data = self._decoder(response)

        return response_data
