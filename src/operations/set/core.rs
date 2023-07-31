//! Defines the core functions for setting key values.
use serde_json::value::Value;

use crate::connection::interface::WrappedConnection;


/// Sets a key for the connection.
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


/// Unsets a key value for the connection.
/// 
/// # Arguments
/// * `connection` - the connection to unset the key value in
/// * `key` - The key to unset
/// 
/// # Returns
/// * `Ok(())` - The key value was unset successfully
pub async fn unset(connection: WrappedConnection, key: String) -> Result<(), String> {
    connection.connection.unset(key).await.map_err(|e| e.to_string())?;
    Ok(())
}
