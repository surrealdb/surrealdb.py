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
blocking_make_connection = MagicMock()
blocking_use_namespace = MagicMock()
blocking_use_database = MagicMock()

# auth mixins
blocking_sign_in = MagicMock()
blocking_authenticate = MagicMock()
blocking_sign_up = MagicMock()

# create mixins
blocking_create = MagicMock()
blocking_delete = MagicMock()

# query mixins 
blocking_query= MagicMock()
blocking_select = MagicMock()

# set mixins
blocking_set = MagicMock()

# update mixins
blocking_merge = MagicMock()
blocking_update = MagicMock()
blocking_patch = MagicMock()
