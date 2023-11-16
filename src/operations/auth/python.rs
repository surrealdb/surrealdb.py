//! Python entry points for the auth operations against the database.
use pyo3::prelude::*;
use pyo3::types::PyAny;
use serde_json::value::Value;

use crate::connection::interface::WrappedConnection;

use super::core::{sign_up, invalidate, authenticate};
use super::interface::WrappedJwt;
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
pub fn rust_sign_up_future<'a>(py: Python<'a>, connection: WrappedConnection, params: &'a PyAny, namespace: String, database: String, scope: String) -> Result<&'a PyAny, PyErr> {
    let params: Value = serde_json::from_str(&params.to_string()).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
    py_future_wrapper!(py, sign_up(connection, params, namespace, database, scope))
}


/// Invalidates the authentication for the current connection.
/// 
/// # Arguments
/// * `connection` - The connection to be invalidated
/// 
/// # Returns
/// * `Ok(())` - The operation was successful
#[pyfunction]
pub fn rust_invalidate_future(py: Python, connection: WrappedConnection) -> Result<&PyAny, PyErr> {
    py_future_wrapper!(py, invalidate(connection))
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
pub fn rust_authenticate_future(py: Python, connection: WrappedConnection, jwt: WrappedJwt) -> Result<&PyAny, PyErr> {
    py_future_wrapper!(py, authenticate(connection, jwt))
}
