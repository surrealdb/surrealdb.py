//! Routes incoming messages to the write module of operations.
use serde::{Serialize, Deserialize};

use crate::connection::interface::{ConnectionRoutes, handle_connection_routes};
use crate::operations::create::interface::{CreateRoutes, handle_create_routes};
use crate::operations::set::interface::{SetRoutes, handle_set_routes};


/// Defines the operation modules that are supported.
/// 
/// # Variants
/// * `Connection` - Managing connections. 
/// * `Create` - Creating new data.
#[derive(Debug, PartialEq, Clone, Deserialize, Serialize)]
pub enum Routes {
    Connection(ConnectionRoutes),
    Create(CreateRoutes),
    Set(SetRoutes),
}


/// Accepts a message for a connection operation and routes it to the appropiate connection operation.
/// 
/// # Arguments
/// * `message` - The message to be routed.
/// * `tx` - The channel needed to access the connection state.
/// 
/// # Returns
/// * `Result<Routes, String>` - The result of the operation.
pub async fn handle_routes(message: Routes) -> Result<Routes, String> {
    match message {
        Routes::Connection(message) => {
            let outcome = handle_connection_routes(message).await?;
            return Ok(Routes::Connection(outcome))
        },
        Routes::Create(message) => {
            let outcome = handle_create_routes(message).await?;
            return Ok(Routes::Create(outcome))
        },
        Routes::Set(message) => {
            let outcome = handle_set_routes(message).await?;
            return Ok(Routes::Set(outcome))
        },
    }
}
