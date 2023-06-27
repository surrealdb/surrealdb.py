//! Defines the routing for a message accepted via TCP in the runtime to the appropiate connection
//! operation.
use serde::{Serialize, Deserialize};
use crate::routing::enums::Message;

use super::core::{
    make_connection,
    close_connection,
    check_connection,
    sign_in
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
    Close(Message<ConnectionId, BasicMessage>),
    Check(Message<ConnectionId, bool>),
    SignIn(Message<SignIn, BasicMessage>),
}


/// Accepts a message for a connection operation and routes it to the appropiate connection operation.
/// 
/// # Arguments
/// * `message` - The message to be routed.
/// * `tx` - The channel needed to access the connection state.
/// 
/// # Returns
/// * `Result<ConnectionRoutes, String>` - The result of the operation.
pub async fn handle_connection_routes(message: ConnectionRoutes) -> Result<ConnectionRoutes, String> {
    match message {
        ConnectionRoutes::Create(message) => {
            let data = message.handle_send()?;
            let outcome: String = make_connection(data.url).await?;
            let message = Message::<Url, ConnectionId>::package_receive(ConnectionId{connection_id: outcome});
            return Ok(ConnectionRoutes::Create(message))
        },
        ConnectionRoutes::Close(message) => {
            let data = message.handle_send()?;
            let outcome: String = close_connection(data.connection_id).await?;
            let message = Message::<ConnectionId, BasicMessage>::package_receive(BasicMessage{message: outcome});
            return Ok(ConnectionRoutes::Close(message))
        },
        ConnectionRoutes::Check(message) => {
            let data = message.handle_send()?;
            let outcome = check_connection(data.connection_id).await?;
            let message = Message::<ConnectionId, bool>::package_receive(outcome);
            return Ok(ConnectionRoutes::Check(message))
        },
        ConnectionRoutes::SignIn(message) => {
            let data = message.handle_send()?;
            let outcome: String = sign_in(data.connection_id, data.username, data.password).await?;
            let message = Message::<SignIn, BasicMessage>::package_receive(BasicMessage{message: outcome});
            return Ok(ConnectionRoutes::SignIn(message))
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

/// Data representing a basic message data schema
#[derive(Debug, PartialEq, Clone, Deserialize, Serialize)]
pub struct BasicMessage {
    pub message: String,
}

/// Data representing an signin data schema
#[derive(Debug, PartialEq, Clone, Deserialize, Serialize)]
pub struct SignIn {
    pub connection_id: String,
    pub username: String,
    pub password: String,
}

