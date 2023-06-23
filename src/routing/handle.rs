use serde::{Serialize, Deserialize};
use tokio::sync::mpsc::Sender;
use crate::connection::state::ConnectionMessage;

use crate::connection::interface::{ConnectionRoutes, handle_connection_routes};
use crate::operations::create::interface::{CreateRoutes, handle_create_routes};


#[derive(Debug, PartialEq, Clone, Deserialize, Serialize)]
pub enum Routes {
    Connection(ConnectionRoutes),
    Create(CreateRoutes),
}


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
