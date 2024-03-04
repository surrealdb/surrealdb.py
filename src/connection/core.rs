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
    extract_connection_components
};
use surrealdb::Surreal;
use surrealdb::opt::auth::Root;
use surrealdb::engine::any::connect;
use surrealdb::engine::any::Any;


/// Makes a connection to the database in an async manner adding namespace and database if in the URL.
/// 
/// # Arguments
/// * `url` - The URL for the connection
/// 
/// # Returns
/// * `Ok(String)` - The unique ID for the connection that was just made
pub async fn make_connection(url: String) -> Result<WrappedConnection, String> {
    if &url == "memory" {
        let connection: Surreal<Any> = connect(url).await.map_err(|e| e.to_string())?;
        return Ok(WrappedConnection {connection})
    }

    // TODO => allow for namespace and database to be optional
    let (url, namespace, database) = extract_connection_components(url)?;

    let connection: Surreal<Any> = connect(url).await.map_err(|e| e.to_string())?;
    if let Some(namespace) = namespace {
        connection.use_ns(namespace).await.map_err(|e| e.to_string())?;
    }
    if let Some(database) = database {
        connection.use_db(database).await.map_err(|e| e.to_string())?;
    }
    return Ok(WrappedConnection {connection})
}


/// Assigns a name to a connection in an async manner.
/// 
/// # Arguments
/// * `connection` - The connection for the name to be assigned to
/// * `namespace` - The namespace to be assigned to the connection
/// 
/// # Returns
/// * `Ok(String)` - Simple message that the connection has been assigned a namespace
pub async fn use_namespace(connection: WrappedConnection, namespace: String) -> Result<String, String> {
    connection.connection.use_ns(namespace).await.map_err(|e| e.to_string())?;
    return Ok("namespace changed".to_string())
}


/// Assigns a database to a connection in an async manner.
/// 
/// # Arguments
/// * `connection` - The connection for the database to be assigned to
/// * `database` - The database to be assigned to the connection
/// 
/// # Returns
/// * `Ok(String)` - Simple message that the connection has been assigned a database
pub async fn use_database(connection: WrappedConnection, database: String) -> Result<String, String> {
    connection.connection.use_db(database).await.map_err(|e| e.to_string())?;
    return Ok("database changed".to_string())
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
