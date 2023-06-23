//! Routes incoming messages to the write module of operations.
use serde::{Serialize, Deserialize};
use tokio::sync::mpsc::Sender;
use crate::connection::state::ConnectionMessage;

use crate::connection::interface::{ConnectionRoutes, handle_connection_routes};
use crate::operations::create::interface::{CreateRoutes, handle_create_routes};


/// Defines the operation modules that are supported.
/// 
/// # Variants
/// * `Connection` - Managing connections. 
/// * `Create` - Creating new data.
#[derive(Debug, PartialEq, Clone, Deserialize, Serialize)]
pub enum Routes {
    Connection(ConnectionRoutes),
    Create(CreateRoutes),
}


/// Accepts a message for a connection operation and routes it to the appropiate connection operation.
/// 
/// # Arguments
/// * `message` - The message to be routed.
/// * `tx` - The channel needed to access the connection state.
/// 
/// # Returns
/// * `Result<Routes, String>` - The result of the operation.
pub async fn handle_routes(message: Routes, tx: Sender<ConnectionMessage>) -> Result<Routes, String> {
    match message {
        Routes::Connection(message) => {
            let outcome = handle_connection_routes(message, tx).await?;
            return Ok(Routes::Connection(outcome))
        },
        Routes::Create(message) => {
            let outcome = handle_create_routes(message, tx).await?;
            return Ok(Routes::Create(outcome))
        },
    }
}
