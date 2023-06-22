use serde::{Serialize, Deserialize};

use crate::routing::enums::Message;
use tokio::sync::mpsc::Sender;
use crate::connection::state::TrackingMessage;

use super::core::{
    create
};

// connection_id: String, table_name: String, data: Value

#[derive(Debug, PartialEq, Clone, Deserialize, Serialize)]
pub enum CreateRoutes {
    Create(Message<CreateData, EmptyState>),
}

#[derive(Debug, PartialEq, Clone, Deserialize, Serialize)]
pub struct CreateData {
    pub connection_id: String,
    pub table_name: String,
    pub data: serde_json::Value,
}

#[derive(Debug, PartialEq, Clone, Deserialize, Serialize)]
pub struct EmptyState;


pub async fn handle_create_routes(message: CreateRoutes, tx: Sender<TrackingMessage>) -> Result<CreateRoutes, String> {
    match message {
        CreateRoutes::Create(message) => {
            let data = message.handle_send()?;
            let _ = create(data.connection_id, data.table_name, data.data, tx).await?;
            let message = Message::<CreateData, EmptyState>::package_receive(EmptyState);
            return Ok(CreateRoutes::Create(message))
        },
    }
}
