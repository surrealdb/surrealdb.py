//! Defines the core functions for setting key values. These functions should not be called directly
//! from the Python API but rather from the TCP connection in the runtime module. In this
//! module we can do the following:
//! 
//! * Set a key value in the database
use serde_json::value::Value;

use crate::connection::interface::WrappedConnection;


/// Sets a key value in the database.
/// 
/// # Arguments
/// * `conection` - the connnection to set the key value in
/// * `key` - The key to set
/// * `value` - The value to set
/// 
/// # Returns
/// * `Ok(())` - The key value was set successfully
pub async fn set(connection: WrappedConnection, key: String, value: Value) -> Result<(), String> {
    connection.connection.set(key, value).await.map_err(|e| e.to_string())?;
    Ok(())
}