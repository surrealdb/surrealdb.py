//! Defines the core functions for setting key values. These functions should not be called directly
//! from the Python API but rather from the TCP connection in the runtime module. In this
//! module we can do the following:
//! 
//! * Set a key value in the database
use serde_json::value::Value;

use crate::connection::state::{
    WrappedConnection,
    get_components,
    CONNECTION_POOL
};


/// Sets a key value in the database.
/// 
/// # Arguments
/// * `connection_id` - The unique ID for the connection
/// * `key` - The key to set
/// * `value` - The value to set
/// 
/// # Returns
/// * `Ok(())` - The key value was set successfully
pub async fn set(connection_id: String, key: String, value: Value) -> Result<(), String> {
    let (raw_index, connection_id) = get_components(connection_id)?;
    let mut connection_pool = CONNECTION_POOL[raw_index].lock().await;
    let connection = match connection_pool.get_mut(&connection_id) {
        Some(connection) => connection,
        None => return Err("connection does not exist".to_string()),
    };

    match connection {
        WrappedConnection::WS(ws_connection) => {
            ws_connection.set(key, value).await.map_err(|e| e.to_string())?;
        },
        WrappedConnection::HTTP(http_connection) => {
            http_connection.set(key, value).await.map_err(|e| e.to_string())?;
        },
        _ => return Err("connection is not a valid type".to_string()),
    }
    Ok(())
}