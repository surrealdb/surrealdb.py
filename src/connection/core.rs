//! Defines the core functions for managing connections. These functions should not be called directly
//! from the Python API but rather from the TCP connection in the runtime module. In this
//! module we can do the following:
//! 
//! * Get a connection from the connection manager
//! * Make a connection to the database and store it in the connection manager
//! * Close a connection to the database and remove it from the connection manager
//! * Check if a connection exists in the connection manager
use crate::connection::interface::{
    WrappedConnection,
    prep_connection_components
};
use surrealdb::Surreal;
use surrealdb::opt::auth::Root;
use surrealdb::engine::any::connect;
use surrealdb::engine::any::Any;


/// Makes a connection to the database in an async manner.
/// 
/// # Arguments
/// * `url` - The URL for the connection
/// 
/// # Returns
/// * `Ok(String)` - The unique ID for the connection that was just made
pub async fn make_connection(url: String) -> Result<WrappedConnection, String> {
    let components = prep_connection_components(url)?;
    let protocol = components.0;
    let address = components.1;
    let database = components.2;
    let namespace = components.3;

    let connection: Surreal<Any> = connect(format!("{}://{}", protocol.to_string(), address)).await.map_err(|e| e.to_string())?;
    connection.use_ns(namespace).use_db(database).await.map_err(|e| e.to_string()).map_err(|e| e.to_string())?;
    return Ok(WrappedConnection {connection})
}

/// Signs into the database in an async manner.
/// 
/// # Arguments
/// * `connection_id` - The unique ID for the connection to be signed into
/// * `username` - The username to be used for signing in
/// * `password` - The password to be used for signing in
/// 
/// # Returns
/// * `Ok(String)` - Simple message that the connection has been signed into
pub async fn sign_in(connection: WrappedConnection, username: String, password: String) -> Result<String, String> {
    connection.connection.signin(Root {
        username: username.as_str(),
        password: password.as_str(),
    }).await.map_err(|e| e.to_string())?;
    return Ok("signed in".to_string())
}
