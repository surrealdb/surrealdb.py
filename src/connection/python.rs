//! Python entry points for the connection module enabling python to perform connection operations.
use pyo3::prelude::*;

use super::core::{
    make_connection,
    sign_in,
    use_database,
    use_namespace
};
use super::interface::WrappedConnection;
use crate::py_future_wrapper;


/// Makes a connection to the database in an non-async manner.
/// 
/// # Arguments
/// * `url` - The URL for the connection
/// * `port` - The port for the connection
/// 
/// # Returns
/// * `Ok(String)` - The unique ID for the connection that was just made
#[pyfunction]
pub fn rust_make_connection_future(py: Python, url: String) -> PyResult<&PyAny> {
    py_future_wrapper!(py, make_connection(url))
}


/// Assigns a namespace to a connection in an non-async manner.
/// 
/// # Arguments
/// * `connection` - The connection for the namespace to be assigned to
/// * `namespace` - The namespace to be assigned to the connection
/// 
/// # Returns
/// * `Ok(String)` - Simple message that the connection has been assigned a namespace
#[pyfunction]
pub fn rust_use_namespace_future(py: Python, connection: WrappedConnection, namespace: String) -> Result<&PyAny, PyErr> {
    py_future_wrapper!(py, use_namespace(connection, namespace))
}


/// Assigns a database to a connection in an non-async manner.
/// 
/// # Arguments
/// * `connection` - The connection for the database to be assigned to
/// * `database` - The database to be assigned to the connection
/// 
/// # Returns
/// * `Ok(String)` - Simple message that the connection has been assigned a database
#[pyfunction]
pub fn rust_use_database_future(py: Python, connection: WrappedConnection, database: String) -> Result<&PyAny, PyErr> {
    py_future_wrapper!(py, use_database(connection, database))
}


/// Signs in to a connection.
/// 
/// # Arguments
/// * `connection_id` - The unique ID for the connection to be signed in to
/// * `username` - The username to be used for signing in
/// * `password` - The password to be used for signing in
/// 
/// # Returns
/// * `Ok(())` - If the sign in was successful
#[pyfunction]
pub fn rust_sign_in_future(py: Python, connection: WrappedConnection, username: String, password: String) -> Result<&PyAny, PyErr> {
    py_future_wrapper!(py, sign_in(connection, username, password))
}
