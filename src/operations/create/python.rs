//! Python entry point for creating a new record in the database.
use pyo3::prelude::*;
use pyo3::types::PyAny;
use serde_json::value::Value;

use crate::connection::interface::WrappedConnection;
use crate::runtime::RUNTIME;
use super::core::{create, delete};


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
pub fn blocking_create<'a>(connection: WrappedConnection, table_name: String, data: &'a PyAny) -> Result<(), PyErr> {
    let data: Value = serde_json::from_str(&data.to_string()).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

    let outcome = RUNTIME.block_on(async move{
        return create(connection, table_name, data).await.map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))
    });
    outcome?;
    Ok(())
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
pub fn blocking_delete(connection: WrappedConnection, resource: String) -> Result<String, PyErr> {
    let outcome = RUNTIME.block_on(async move{
        return delete(connection, resource).await.map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))
    })?;
    Ok(outcome.to_string())
}
