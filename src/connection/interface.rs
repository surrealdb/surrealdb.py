//! Defines the routing for a message accepted via TCP in the runtime to the appropiate connection
//! operation.
use serde::{Serialize, Deserialize};
use crate::routing::enums::Message;
use tokio::sync::mpsc::Sender;
use crate::connection::state::ConnectionMessage;

use super::core::{
    make_connection,
    close_connection,
    check_connection
};


/// Each field is an operation that can be performed on a connection. The left side
/// of the field type definition is the data needed to perform the operation and the
/// right side is the data returned from the operation.
/// 
/// # Variants
/// * `Create` - Create a connection. (Url is need and ConnectionId is returned)
/// * `Close` - Close a connection. (ConnectionId is needed and EmptyState is returned)
/// * `Check` - Check if a connection is open. (ConnectionId is needed and bool is returned)
#[derive(Debug, PartialEq, Clone, Deserialize, Serialize)]
pub enum ConnectionRoutes {
    Create(Message<Url, ConnectionId>),
    Close(Message<ConnectionId, EmptyState>),
    Check(Message<ConnectionId, bool>),
}


/// Accepts a message for a connection operation and routes it to the appropiate connection operation.
/// 
/// # Arguments
/// * `message` - The message to be routed.
/// * `tx` - The channel needed to access the connection state.
/// 
/// # Returns
/// * `Result<ConnectionRoutes, String>` - The result of the operation.
pub async fn handle_connection_routes(message: ConnectionRoutes, tx: Sender<ConnectionMessage>) -> Result<ConnectionRoutes, String> {
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


/// Data representing a url data schema
#[derive(Debug, PartialEq, Clone, Deserialize, Serialize)]
pub struct Url {
    pub url: String,
}

/// Data representing a connection id data schema
#[derive(Debug, PartialEq, Clone, Deserialize, Serialize)]
pub struct ConnectionId {
    pub connection_id: String,
}

/// Data representing an empty state data schema
#[derive(Debug, PartialEq, Clone, Deserialize, Serialize)]
pub struct EmptyState;


