"""
This files adds a mocking interface for the rust interface. If you add a new function or object with Python
bindings in the rust module, you must add it here as well so python objects and interact with the rust module
without actually calling the rust module. This enables us to test edge cases quickly and inspect what is passed
to the rust module and how many times it is called. This also enables us to run the python tests with a
debugging tool. It must be stressed that this is not a replacement for integration tests, but rather an aid
for rapid python testing and development. If the rust code changes, the integration tests must be run to ensure
that the python bindings are still working as expected.
"""
from unittest.mock import MagicMock

# connection interface
rust_make_connection_future = MagicMock()
rust_use_namespace_future = MagicMock()
rust_use_database_future = MagicMock()

# auth mixins
rust_sign_in_future = MagicMock()
rust_authenticate_future = MagicMock()
rust_sign_up_future = MagicMock()

# create mixins
rust_create_future = MagicMock()
rust_delete_future = MagicMock()

# query mixins 
rust_query_future = MagicMock()
rust_select_future = MagicMock()

# set mixins
rust_set_future = MagicMock()

# update mixins
rust_merge_future = MagicMock()
rust_update_future = MagicMock()
rust_patch_future = MagicMock()
