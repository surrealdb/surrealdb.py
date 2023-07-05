//! Python entry points for the connection module enabling python to perform connection operations.
use pyo3::prelude::*;

use crate::runtime::{
    RUNTIME
};
use super::core::{
    make_connection,
    sign_in,
    use_database,
    use_namespace
};
use super::interface::WrappedConnection;


/// Makes a connection to the database in an non-async manner.
/// 
/// # Arguments
/// * `url` - The URL for the connection
/// * `port` - The port for the connection
/// 
/// # Returns
/// * `Ok(String)` - The unique ID for the connection that was just made
#[pyfunction]
pub fn blocking_make_connection(url: String) -> Result<WrappedConnection, PyErr> {
    let outcome = RUNTIME.block_on(async move{
        make_connection(url).await.map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))
    });
    outcome
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
pub fn blocking_use_namespace(connection: WrappedConnection, namespace: String) -> Result<String, PyErr> {
    let outcome = RUNTIME.block_on(async move{
        use_namespace(connection, namespace).await.map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))
    });
    outcome
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
pub fn blocking_use_database(connection: WrappedConnection, database: String) -> Result<String, PyErr> {
    let outcome = RUNTIME.block_on(async move{
        use_database(connection, database).await.map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))
    });
    outcome
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
pub fn blocking_sign_in(connection: WrappedConnection, username: String, password: String) -> Result<(), PyErr> {
    let outcome = RUNTIME.block_on(async move{
        sign_in(connection, username, password).await.map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))
    });
    outcome?;
    Ok(())
}
