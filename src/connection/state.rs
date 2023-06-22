use pyo3::prelude::*;
use std::{sync::Mutex, collections::HashMap};
use once_cell::sync::Lazy;
use uuid::Uuid;
use serde::{Serialize, Deserialize};

use surrealdb::engine::remote::{
    ws::Ws,
    http::Http,
};
use surrealdb::Surreal;
use surrealdb::engine::remote::http::Client as HttpClient;
use surrealdb::engine::remote::ws::Client as WsClient;


// Keeps track of the connections that are currently open
pub static CONNECTION_STATE: Lazy<Mutex<HashMap<String, WrappedConnection>>> = Lazy::new(|| {
    let m: HashMap<String, WrappedConnection> = HashMap::new();
    Mutex::new(m)
});


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
pub enum WrappedConnection {
    WS(Surreal<WsClient>),
    HTTP(Surreal<HttpClient>),
}
