//! Python entry points for performing update operations against the database.
use pyo3::prelude::*;
use pyo3::types::PyAny;
use serde_json::value::Value;

use crate::connection::interface::WrappedConnection;
use crate::runtime::RUNTIME;
use super::core::{
    update,
    merge
};


/// Performs an update operation against the database in a blocking manner.
/// 
/// # Arguments
/// * `connection` - The connection to be used for the update
/// * `resource` - The resource to be updated
/// * `data` - The data to be used for the update
/// 
/// # Returns
/// * `Ok(String)` - The outcome of the update operation
#[pyfunction]
pub fn blocking_update<'a>(connection: WrappedConnection, resource: String, data: &'a PyAny) -> Result<String, PyErr> {
    let data: Value = serde_json::from_str(&data.to_string()).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
    let outcome = RUNTIME.block_on(async move{
        return update(connection, resource, data).await.map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))
    }).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))?;
    Ok(outcome.to_string())
}


/// Performs a merge operation against the database in a blocking manner.
/// 
/// # Arguments
/// * `connection` - The connection to be used for the merge
/// * `resource` - The resource to be merged
/// * `data` - The data to be used for the merge
/// 
/// # Returns
/// * `Ok(String)` - The outcome of the merge operation
#[pyfunction]
pub fn blocking_merge<'a>(connection: WrappedConnection, resource: String, data: &'a PyAny) -> Result<String, PyErr> {
    let data: Value = serde_json::from_str(&data.to_string()).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
    let outcome = RUNTIME.block_on(async move{
        return merge(connection, resource, data).await.map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))
    }).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))?;
    Ok(outcome.to_string())
}
