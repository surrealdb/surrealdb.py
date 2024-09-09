//! Python entry point for deleting a record in the database.
use pyo3::prelude::*;
use pyo3::types::PyAny;

use crate::connection::interface::WrappedConnection;
use super::core::delete;
use crate::py_future_wrapper;


/// Deletes a record or range of records from the database in an non-async manner.
/// 
/// # Arguments
/// * `connection` - The database connection being used for the operation
/// * `resource` - The resource to delete (can be a table or a range)
/// 
/// # Returns
/// * `Ok(())` - The operation was successful
#[pyfunction]
pub fn rust_delete_future(py: Python, connection: WrappedConnection, resource: String) -> Result<&PyAny, PyErr> {
    py_future_wrapper!(py, delete(connection, resource))
}
