//! Python entry point for setting a new key.
use pyo3::prelude::*;
use pyo3::types::PyAny;
use serde_json::value::Value;

use crate::connection::interface::WrappedConnection;
use crate::runtime::RUNTIME;
use super::core::set;


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
pub fn blocking_set<'a>(connection: WrappedConnection, key: String, value: &'a PyAny) -> Result<(), PyErr> {
    let value: Value = serde_json::from_str(&value.to_string()).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

    let outcome = RUNTIME.block_on(async move{
        return set(connection, key, value).await.map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))
    });
    outcome?;
    Ok(())
}
