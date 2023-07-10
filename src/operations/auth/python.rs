//! Python entry points for the auth operations against the database.
use pyo3::prelude::*;
use pyo3::types::PyAny;
use serde_json::value::Value;

use crate::connection::interface::WrappedConnection;
use crate::runtime::RUNTIME;

use super::core::{sign_up, invalidate, authenticate};
use super::interface::WrappedJwt;


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
pub fn blocking_sign_up<'a>(connection: WrappedConnection, params: &'a PyAny, namespace: String, database: String, scope: String) -> Result<WrappedJwt, PyErr> {
    let params: Value = serde_json::from_str(&params.to_string()).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

    RUNTIME.block_on(async move{
        return sign_up(connection, params, namespace, database, scope).await.map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))
    })
}


/// Invalidates the authentication for the current connection.
/// 
/// # Arguments
/// * `connection` - The connection to be invalidated
/// 
/// # Returns
/// * `Ok(())` - The operation was successful
#[pyfunction]
pub fn blocking_invalidate(connection: WrappedConnection) -> Result<(), PyErr> {
    RUNTIME.block_on(async move{
        return invalidate(connection).await.map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))
    })
}


/// Authenticates the current connection with a JWT token.
/// 
/// # Arguments
/// * `connection` - The connection to be authenticated
/// * `jwt` - The JWT token to be used for authentication
/// 
/// # Returns
/// * `Ok(())` - The operation was successful
#[pyfunction]
pub fn blocking_authenticate(connection: WrappedConnection, jwt: WrappedJwt) -> Result<(), PyErr> {
    RUNTIME.block_on(async move{
        return authenticate(connection, jwt).await.map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))
    })
}
