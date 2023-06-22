use serde::{Serialize, Deserialize};
use crate::routing::enums::Message;
use tokio::sync::mpsc::Sender;
use crate::connection::state::TrackingMessage;

use super::core::{
    make_connection,
    close_connection,
    check_connection
};

#[derive(Debug, PartialEq, Clone, Deserialize, Serialize)]
pub enum ConnectionRoutes {
    Create(Message<Url, ConnectionId>),
    Close(Message<ConnectionId, EmptyState>),
    Check(Message<ConnectionId, bool>),
}


pub async fn handle_connection_routes(message: ConnectionRoutes, tx: Sender<TrackingMessage>) -> Result<ConnectionRoutes, String> {
    match message {
        ConnectionRoutes::Create(message) => {
            let data = message.handle_send()?;
            let outcome: String = make_connection(data.url, tx).await?;
            let message = Message::<Url, ConnectionId>::package_receive(ConnectionId{connection_id: outcome});
            return Ok(ConnectionRoutes::Create(message))
        },
        ConnectionRoutes::Close(message) => {
            let data = message.handle_send()?;
            let _ = close_connection(data.connection_id, tx).await;
            let message = Message::<ConnectionId, EmptyState>::package_receive(EmptyState);
            return Ok(ConnectionRoutes::Close(message))
        },
        ConnectionRoutes::Check(message) => {
            let data = message.handle_send()?;
            let outcome = check_connection(data.connection_id, tx).await?;
            let message = Message::<ConnectionId, bool>::package_receive(outcome);
            return Ok(ConnectionRoutes::Check(message))
        },
    }
}


#[derive(Debug, PartialEq, Clone, Deserialize, Serialize)]
pub struct Url {
    pub url: String,
}

#[derive(Debug, PartialEq, Clone, Deserialize, Serialize)]
pub struct ConnectionId {
    pub connection_id: String,
}

#[derive(Debug, PartialEq, Clone, Deserialize, Serialize)]
pub struct EmptyState;


