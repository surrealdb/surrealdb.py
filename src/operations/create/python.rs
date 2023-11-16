//! Python entry point for creating a new record in the database.
use pyo3::prelude::*;
use pyo3::types::PyAny;
use serde_json::value::Value;

use crate::connection::interface::WrappedConnection;
use super::core::{create, delete};
use crate::py_future_wrapper;


/// Creates a new record in the database in an non-async manner.
/// 
/// # Arguments
/// * `connection` - The database connection being used for the operation
/// * `table_name` - The name of the table to create the record in
/// * `data` - The data to be inserted into the table
/// * `port` - The port for the connection to the runtime
/// 
/// # Returns
/// * `Ok(())` - The operation was successful
#[pyfunction]
pub fn rust_create_future<'a>(py: Python<'a>, connection: WrappedConnection, table_name: String, data: &'a PyAny) -> Result<&'a PyAny, PyErr> {
    let data: Value = serde_json::from_str(&data.to_string()).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
    py_future_wrapper!(py, create(connection, table_name, data))
}


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
