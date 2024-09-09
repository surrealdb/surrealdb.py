//! Python entry point for creating a new record in the database.
use pyo3::prelude::*;
use pyo3::types::PyAny;
use serde_json::value::Value;

use crate::connection::interface::WrappedConnection;
use super::core::create;
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
