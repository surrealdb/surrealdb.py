//! Defines the core functions for creating records. These functions should not be called directly
//! from the Python API but rather from the TCP connection in the runtime module. In this
//! module we can do the following:
//! 
//! * Create a record in the database
use serde_json::value::Value;
use surrealdb::opt::Resource;
use crate::connection::state::{
    WrappedConnection,
    get_components,
    CONNECTION_POOL
};


/// Creates a record in the database.
/// 
/// # Arguments
/// * `connection_id` - The unique ID for the connection
/// * `table_name` - The name of the table to create the record in
/// 
/// # Returns
/// * `Ok(())` - The record was created successfully
pub async fn create(connection_id: String, table_name: String, data: Value) -> Result<(), String> {
    let (raw_index, connection_id) = get_components(connection_id)?;
    let mut connection_pool = CONNECTION_POOL[raw_index].lock().await;
    let connection = match connection_pool.get_mut(&connection_id) {
        Some(connection) => connection,
        None => return Err("connection does not exist".to_string()),
    };

    let resource = Resource::from(table_name.clone());

    match connection {
        WrappedConnection::WS(ws_connection) => {
            ws_connection.create(resource).content(data).await.map_err(|e| e.to_string())?;
        },
        WrappedConnection::HTTP(http_connection) => {
            http_connection.create(resource).content(data).await.map_err(|e| e.to_string())?;
        },
        _ => return Err("connection is not a valid type".to_string()),
    }
    Ok(())
}
