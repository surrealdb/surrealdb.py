//! Python entry point for running a query.
use pyo3::prelude::*;
use pyo3::types::PyAny;
use pyo3::types::PyDict;
use serde_json::value::Value;
use serde_json::Value;

use super::core::{query, select};
use crate::connection::interface::WrappedConnection;
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
pub fn rust_query_future<'a>(
    py: Python<'a>,
    connection: WrappedConnection,
    sql: String,
    bindings: Option<&'a PyDict>,
) -> Result<&'a PyAny, PyErr> {
    let processed_bindings = bindings
        .map(|dict| {
            let value = dict.extract::<Value>().map_err(|e| {
                PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                    "Failed to convert bindings to Value: {}",
                    e
                ))
            })?;
            Ok(value)
        })
        .transpose()?;

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
