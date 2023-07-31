//! Python entry points for setting and unsetting keys against the connection.
use pyo3::prelude::*;
use pyo3::types::PyAny;
use serde_json::value::Value;

use crate::connection::interface::WrappedConnection;
use crate::runtime::RUNTIME;
use super::core::{
    set,
    unset
};


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
pub fn blocking_set<'a>(connection: WrappedConnection, key: String, value: &'a PyAny) -> Result<(), PyErr> {
    let value: Value = serde_json::from_str(&value.to_string()).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

    let outcome = RUNTIME.block_on(async move{
        return set(connection, key, value).await.map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))
    });
    outcome?;
    Ok(())
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
pub fn blocking_unset(connection: WrappedConnection, key: String) -> Result<(), PyErr> {
    let outcome = RUNTIME.block_on(async move{
        return unset(connection, key).await.map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))
    });
    outcome?;
    Ok(())
}
