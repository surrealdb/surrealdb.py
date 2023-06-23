//! Routes the operation message to the appropiate create operation.
use serde::{Serialize, Deserialize};

use crate::routing::enums::Message;
use tokio::sync::mpsc::Sender;
use crate::connection::state::ConnectionMessage;

use super::core::{
    create
};


/// The available create operations.
/// 
/// # Variants
/// * `Create` - Create a row in a table. (CreateData is needed and EmptyState is returned)
#[derive(Debug, PartialEq, Clone, Deserialize, Serialize)]
pub enum CreateRoutes {
    Create(Message<CreateData, EmptyState>),
}


/// Accepts a message for a create operation and routes it to the appropiate create operation.
/// 
/// # Arguments
/// * `message` - The message to be routed.
/// * `tx` - The channel needed to access the connection state.
/// 
/// # Returns
/// * `Result<CreateRoutes, String>` - The result of the operation.
pub async fn handle_create_routes(message: CreateRoutes, tx: Sender<ConnectionMessage>) -> Result<CreateRoutes, String> {
    match message {
        CreateRoutes::Create(message) => {
            let data = message.handle_send()?;
            let _ = create(data.connection_id, data.table_name, data.data, tx).await?;
            let message = Message::<CreateData, EmptyState>::package_receive(EmptyState);
            return Ok(CreateRoutes::Create(message))
        },
    }
}


/// Data representing the CreateData schema
#[derive(Debug, PartialEq, Clone, Deserialize, Serialize)]
pub struct CreateData {
    pub connection_id: String,
    pub table_name: String,
    pub data: serde_json::Value,
}


/// Data representing the EmptyState schema
#[derive(Debug, PartialEq, Clone, Deserialize, Serialize)]
pub struct EmptyState;
