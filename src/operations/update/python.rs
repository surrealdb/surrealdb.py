//! Python entry points for performing update operations against the database.
use pyo3::prelude::*;
use pyo3::types::PyAny;
use serde_json::value::Value;

use crate::connection::interface::WrappedConnection;
use super::core::{
    update,
    merge,
    patch
};
use crate::py_future_wrapper;


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
pub fn rust_update_future<'a>(py: Python<'a>, connection: WrappedConnection, resource: String, data: &'a PyAny) -> Result<&'a PyAny, PyErr> {
    let data = data.to_string();
    // data.replace("None", "null");
    let data = data.replace("True", "true");
    let data = data.replace("False", "false");
    let data: Value = serde_json::from_str(&data).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
    py_future_wrapper!(py, update(connection, resource, data))
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
pub fn rust_merge_future<'a>(py: Python<'a>, connection: WrappedConnection, resource: String, data: &'a PyAny) -> Result<&'a PyAny, PyErr> {
    let data: Value = serde_json::from_str(&data.to_string()).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
    py_future_wrapper!(py, merge(connection, resource, data))
}


/// Performs a patch operation against the database in a blocking manner.
/// 
/// # Arguments
/// * `connection` - The connection to be used for the patch
/// * `resource` - The resource to be patched
/// * `data` - The data to be used for the patch
/// 
/// # Returns
/// * `Ok(String)` - The outcome of the patch operation
#[pyfunction]
pub fn rust_patch_future<'a>(py: Python<'a>, connection: WrappedConnection, resource: String, data: &'a PyAny) -> Result<&'a PyAny, PyErr> {
    let data: Value = serde_json::from_str(&data.to_string()).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
    py_future_wrapper!(py, patch(connection, resource, data))
}
