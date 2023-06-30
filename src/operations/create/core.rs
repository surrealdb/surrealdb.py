//! Defines the core functions for creating records. These functions should not be called directly
//! from the Python API but rather from the TCP connection in the runtime module. In this
//! module we can do the following:
//! 
//! * Create a record in the database
use serde_json::value::Value;
use surrealdb::opt::Resource;
use crate::connection::interface::WrappedConnection;


/// Creates a record in the database.
/// 
/// # Arguments
/// * `connection_id` - The unique ID for the connection
/// * `table_name` - The name of the table to create the record in
/// 
/// # Returns
/// * `Ok(())` - The record was created successfully
pub async fn create(connection: WrappedConnection, table_name: String, data: Value) -> Result<(), String> {
    let resource = Resource::from(table_name.clone());
    connection.connection.create(resource).content(data).await.map_err(|e| e.to_string())?;
    Ok(())
}
