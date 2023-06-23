//! Defines a simple interface between getting connections from a state transfer actor storing those connections. These async functions merely act as an interface with the state transfer actor.
//! You will see that there are no unit tests in this module, this is because the async function are
//! defining the types for generic functions and calling them. These generic functions have been unit
//! tested in the state transfer actor module.
use std::fmt::{Display, Formatter};

use tokio::sync::mpsc::{Receiver, Sender};

use surrealdb::Surreal;
use surrealdb::engine::remote::http::Client as HttpClient;
use surrealdb::engine::remote::ws::Client as WsClient;

use super::components::state_transfer_actor::{
    StateTransferActor,
    StateTransferMessage,
    run_state_transfer_actor,
    WrappedValue,
    get_value,
    return_value,
};

pub type ConnectionMessage = StateTransferMessage<String, WrappedConnection>;
pub type GetConnectionMessage = WrappedValue<WrappedConnection>;


/// A tag to aid in error messages for the generic functions that access the state transfer actor.
struct ConnectionActorTag;

impl Display for ConnectionActorTag {
    fn fmt(&self, f: &mut Formatter<'_>) -> std::fmt::Result {
        write!(f, "CONNECTION_ACTOR")
    }
}


/// Starts running the connection manager.
/// 
/// # Arguments
/// * `rx` - The receiver for the connection manager to accept requests.
pub async fn track_connections(rx: Receiver<ConnectionMessage>) {
    let actor = StateTransferActor::new(rx);
    run_state_transfer_actor(actor).await;
}

/// Gets a connection from the connection manager.
/// 
/// # Arguments
/// * `connection_id` - The id of the connection to get.
/// * `sender` - The sender to send the request to the connection manager.
/// 
/// # Usage
/// It must be stressed that errors need to be handled when using this function. If the connection is retrieved
/// using the `get_connection` function, it must be returned using the `return_connection` function. If the
/// connection is not returned, the connection will be lost. This means that if an error occurs before the
/// `return_connection` function is called, the connection will be lost. We can handle the connection with
/// code like the following:
/// ```rust
/// let mut connection = get_connection(connection_id.clone(), tx).await?; // get the connection
/// let resource = Resource::from(table_name.clone());
/// 
/// let used_connection: WrappedConnection; // stash the connection that was used
/// let db_result: DbResult; // stash the result of the database operation
/// match connection.value.unwrap() {
///     WrappedConnection::WS(ws_connection) => {
///         db_result = ws_connection.create(resource).content(data).await.map_err(|e| e.to_string());
///         used_connection = WrappedConnection::WS(ws_connection);
///     },
///     WrappedConnection::HTTP(http_connection) => {
///         db_result = http_connection.create(resource).content(data).await.map_err(|e| e.to_string());
///         used_connection = WrappedConnection::HTTP(http_connection);
///     },
/// }   
/// connection.value = Some(used_connection); // return the connection to the WrappedValue to be sent back
/// return_connection(connection).await?; // return the connection to the connection manager
/// db_result?; // handle the result of the database operation
/// Ok(())
/// ```
/// # Improvements
/// the author (Maxwell Flitton) appreciates that this is not ideal but luckily rust is safe and handling such errors
/// is not too difficult. With testing and the right error handling, this can be a very safe and reliable way to 
/// handle connections. However, the author is very open to suggestions on how to improve this and will look into
/// other methods once the basic infrastructure is working.
/// 
/// # Returns
/// * `GetConnectionMessage` - The connection message containing connection and sender to send the connection
///                            back to the connection manager.
pub async fn get_connection(connection_id: String, sender: Sender<ConnectionMessage>) -> Result<GetConnectionMessage, String> {
    get_value::<WrappedConnection, String, ConnectionActorTag>(
        connection_id, sender, ConnectionActorTag
    ).await
}


/// Returns a connection to the connection manager.
/// 
/// # Arguments
/// * `return_connection` - The connection message containing the connection and sender to send the connection
/// 
/// # Returns
/// * `Ok(())` - If the connection was returned successfully.
pub async fn return_connection(return_connection: GetConnectionMessage) -> Result<(), String> {
    return_value::<WrappedConnection, ConnectionActorTag>(
        return_connection, ConnectionActorTag
    ).await
}


/// Acts as an interface between the connection string passed in and the connection protocol.
/// 
/// # Variants 
/// * `WS` - Websocket protocol
/// * `HTTP` - HTTP protocol
#[derive(Debug, PartialEq)]
pub enum ConnectProtocol {
    WS,
    HTTP,
}

impl ConnectProtocol {

    /// Creates a new connection protocol enum variant from a string.
    /// 
    /// # Arguments
    /// * `protocol_type` - The type of protocol to use for the connection.
    /// 
    /// # Returns
    /// * `Ok(ConnectProtocol)` - The connection protocol enum variant.
    pub fn from_string(protocol_type: String) -> Result<Self, String> {
        match protocol_type.to_uppercase().as_str() {
            "WS" => Ok(Self::WS),
            "HTTP" => Ok(Self::HTTP),
            _ => Err(format!("Invalid protocol: {}", protocol_type)),
        }
    }

}


/// Acts as a wrapper for the open database connection to be stored in the `CONNECTION_STATE` hashmap.
/// 
/// # Variants
/// * `WS` - live Websocket connection
/// * `HTTP` - live HTTP connection
#[derive(Clone, Debug)]
pub enum WrappedConnection {
    WS(Surreal<WsClient>),
    HTTP(Surreal<HttpClient>),
}
