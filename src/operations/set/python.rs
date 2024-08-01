//! Python entry points for setting and unsetting keys against the connection.
use pyo3::prelude::*;
use pyo3::types::PyAny;
use serde_json::value::Value;

use crate::connection::interface::WrappedConnection;
use super::core::{
    set,
    unset
};
use crate::py_future_wrapper;


/// Creates a new record in the database connection in an non-async manner.
/// 
/// # Arguments
/// * `connection` - The database connection for the key to be set on
/// * `key` - The key to be set on the connection
/// * `value` - The value associated with the key
/// 
/// # Returns
/// * `Ok(())` - The operation was successful
#[pyfunction]
pub fn rust_set_future<'a>(py: Python<'a>, connection: WrappedConnection, key: String, value: &'a PyAny) -> Result<&'a PyAny, PyErr> {
    let value: Value = serde_json::from_str(&value.to_string()).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
    py_future_wrapper!(py, set(connection, key, value))
}


/// unsets a key in the database connection in an non-async manner.
/// 
/// # Arguments
/// * `connection` - The database connection for the key to be unset on
/// * `key` - The key to be unset on the connection
/// 
/// # Returns
/// * `Ok(())` - The operation was successful
#[pyfunction]
pub fn rust_unset_future(py: Python, connection: WrappedConnection, key: String) -> Result<&PyAny, PyErr> {
    py_future_wrapper!(py, unset(connection, key))
}
