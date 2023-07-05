//! Python entry point for running a query.
use pyo3::prelude::*;
use pyo3::types::PyAny;
use serde_json::value::Value;

use crate::connection::interface::WrappedConnection;
use crate::runtime::RUNTIME;
use super::core::{query, select};


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
pub fn blocking_query<'a>(connection: WrappedConnection, sql: String, bindings: Option<&'a PyAny>) -> Result<String, PyErr> {

    let processed_bindings = match bindings {
        Some(bindings) => {
            let bindings: Value = serde_json::from_str(&bindings.to_string()).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
            Some(bindings)
        },
        None => None
    };

    let outcome = RUNTIME.block_on(async move{
        return query(connection, sql, processed_bindings).await.map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))
    }).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))?;
    Ok(outcome.to_string())
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
pub fn blocking_select(connection: WrappedConnection, resource: String) -> Result<String, PyErr> {
    let outcome = RUNTIME.block_on(async move{
        return select(connection, resource).await
    }).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))?;
    Ok(outcome.to_string())
}
