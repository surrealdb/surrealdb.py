//! Routes the operation message to the appropiate create operation.
use serde::{Serialize, Deserialize};

use crate::routing::enums::Message;

use super::core::{
    set
};


/// The available set operations.
/// 
/// # Variants
/// * `Set` - Create a row in a table. (CreateData is needed and EmptyState is returned)
#[derive(Debug, PartialEq, Clone, Deserialize, Serialize)]
pub enum SetRoutes {
    Set(Message<SetData, BasicMessage>),
}


/// Accepts a message for a set operation and routes it to the appropiate set operation.
/// 
/// # Arguments
/// * `message` - The message to be routed.
/// 
/// # Returns
/// * `Result<SetRoutes, String>` - The result of the operation.
pub async fn handle_set_routes(message: SetRoutes) -> Result<SetRoutes, String> {
    match message {
        SetRoutes::Set(message) => {
            let data = message.handle_send()?;
            let _ = set(data.connection_id, data.key, data.value).await?;
            let message = Message::<SetData, BasicMessage>::package_receive(BasicMessage{
                message: "Set".to_string(),
            });
            return Ok(SetRoutes::Set(message))
        },
    }
}


/// Data representing the SetData schema
#[derive(Debug, PartialEq, Clone, Deserialize, Serialize)]
pub struct SetData {
    pub connection_id: String,
    pub key: String,
    pub value: serde_json::Value,
}


/// Data representing a basic message data schema
#[derive(Debug, PartialEq, Clone, Deserialize, Serialize)]
pub struct BasicMessage {
    pub message: String,
}
