use std::{sync::Mutex, collections::HashMap, sync::Arc};
use tokio::sync::mpsc::{Receiver, Sender};
use tokio::sync::oneshot;
use once_cell::sync::Lazy;
use tokio::sync::mpsc;

use surrealdb::Surreal;
use surrealdb::engine::remote::http::Client as HttpClient;
use surrealdb::engine::remote::ws::Client as WsClient;


// Keeps track of the connections that are currently open
pub static CONNECTION_STATE: Lazy<Arc<Mutex<HashMap<String, WrappedConnection>>>> = Lazy::new(|| {
    Arc::new(Mutex::new(HashMap::new()))
});


#[derive(Debug)]
pub enum TrackingMessage {
    Create(CreateConnection),
    Get(GetConnection),
    Delete(DeleteConnection)
}

#[derive(Debug)]
pub struct CreateConnection {
    pub connection_id: String,
    pub connection: WrappedConnection,
}

#[derive(Debug)]
pub struct GetConnection {
    pub connection_id: String,
    pub response_sender: oneshot::Sender<Option<WrappedConnection>>
}

#[derive(Debug)]
pub struct DeleteConnection {
    pub connection_id: String
}


pub async fn track_connections(mut rx: Receiver<TrackingMessage>) {
    let mut state: HashMap<String, WrappedConnection> = HashMap::new();

    loop {
        if let Some(message) = rx.recv().await {
            match message {
                TrackingMessage::Create(create) => {
                    // Handle CreateConnection message
                    state.insert(create.connection_id, create.connection);
                }
                TrackingMessage::Get(get) => {
                    // Handle GetConnection message
                    let connection = state.get(&get.connection_id).cloned();
                    get.response_sender.send(connection).unwrap();
                }
                TrackingMessage::Delete(delete) => {
                    // Handle DeleteConnection message
                    state.remove(&delete.connection_id);
                }
            }
            // Perform any additional logic or processing based on the received message
            // ...
        }
    }
}


pub async fn get_connection(connection_id: String, sender: Sender<TrackingMessage>) -> Option<WrappedConnection> {
    let (response_sender, response_receiver) = oneshot::channel::<Option<WrappedConnection>>();
    let message = TrackingMessage::Get(GetConnection {
        connection_id,
        response_sender
    });
    sender.send(message).await.unwrap();

    // Wait for the response
    let response = response_receiver.await.unwrap();

    // Process the response
    match response {
        Some(connection) => {
            // Handle the case when the connection is found
            return Some(connection)
        }
        None => {
            // Handle the case when the connection is not found
            return None
        }
    }
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
