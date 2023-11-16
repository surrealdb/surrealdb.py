//! Python entry point for running a query.
use pyo3::prelude::*;
use pyo3::types::PyAny;
use serde_json::value::Value;

use crate::connection::interface::WrappedConnection;
use super::core::{query, select};
use crate::py_future_wrapper;


/// Creates a new record in the database in an non-async manner.
/// 
/// # Arguments
/// * `connection_id` - The database connection being used for the operation
/// * `table_name` - The name of the table to create the record in
/// * `data` - The data to be inserted into the table
/// 
/// # Returns
/// * `Ok(())` - The operation was successful
#[pyfunction]
pub fn rust_query_future<'a>(py: Python<'a>, connection: WrappedConnection, sql: String, bindings: Option<&'a PyAny>) -> Result<&'a PyAny, PyErr> {

    let processed_bindings = match bindings {
        Some(bindings) => {
            let bindings: Value = serde_json::from_str(&bindings.to_string()).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
            Some(bindings)
        },
        None => None
    };
    py_future_wrapper!(py, query(connection, sql, processed_bindings))
}


/// Performs a select on the database in an non-async manner.
/// 
/// # Arguments
/// * `connection` - The connection to perform the select with
/// * `resource` - The resource to select (can be a table or a range)
/// 
/// # Returns
/// * `Ok(String)` - The result of the select
#[pyfunction]
pub fn rust_select_future(py: Python, connection: WrappedConnection, resource: String) -> Result<&PyAny, PyErr> {
    py_future_wrapper!(py, select(connection, resource))
}
