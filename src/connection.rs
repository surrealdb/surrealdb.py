//! Defines the methods of connecting to the database.
//! This module is currently written in short functions in order to help with the testing. Transition to structs with traits can be an
//! approach to take when async functions in traits become part of the std library. For now we are keeping the interactions with other
//! modules in short async functions.
use pyo3::prelude::*;
use std::{sync::Mutex, collections::HashMap};
use once_cell::sync::Lazy;
use uuid::Uuid;

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


/// Checks and splits the connection string into its components.
/// 
/// # Arguments
/// * `url` - The URL for the connection to be checked and split
/// 
/// # Returns
/// * `Ok((ConnectProtocol, String))` - The connection protocol and the address
pub fn prep_connection_components(url: String) -> Result<(ConnectProtocol, String), String> {
    let parts: Vec<&str> = url.split("://").collect();
    let protocol = ConnectProtocol::from_string(parts[0].to_string())?;
    let address = parts[1];
    return Ok((protocol, address.to_string()))
}


/// Makes a connection to the database in an async manner.
/// 
/// # Arguments
/// * `url` - The URL for the connection
/// 
/// # Returns
/// * `Ok(String)` - The unique ID for the connection that was just made
pub async fn make_connection(url: String) -> Result<String, String> {
    let components = prep_connection_components(url)?;
    let protocol = components.0;
    let address = components.1;

    let wrapped_connection: WrappedConnection;
    match protocol {
        ConnectProtocol::WS => {
            wrapped_connection = WrappedConnection::WS(
                Surreal::new::<Ws>(address).await.map_err(|e| e.to_string())?
            );
        },
        ConnectProtocol::HTTP => {
            wrapped_connection = WrappedConnection::HTTP(
                Surreal::new::<Http>(address).await.map_err(|e| e.to_string())?
            );
        },
    }

    // update the connection state
    let mut connection_state = CONNECTION_STATE.lock().unwrap();
    let connection_id = Uuid::new_v4().to_string();
    connection_state.insert(connection_id.clone(), wrapped_connection);
    println!("Connection state: {:?}", connection_state.keys().len());
    return Ok(connection_id)
}


/// Closes a connection to the database in an async manner.
/// 
/// # Arguments
/// * `connection_id` - The unique ID for the connection to be closed
pub async fn close_connection(connection_id: String) -> Result<(), String> {
    let mut connection_state = CONNECTION_STATE.lock().unwrap();
    connection_state.remove(&connection_id);
    println!("Connection state: {:?}", connection_state.keys().len());
    return Ok(())
}


// ============================================== interfaces for the module below ==============================================


/// Makes a connection to the database in an non-async manner.
/// 
/// # Arguments
/// * `url` - The URL for the connection
/// 
/// # Returns
/// * `Ok(String)` - The unique ID for the connection that was just made
#[pyfunction]
pub fn blocking_make_connection(url: String) -> Result<String, PyErr> {
    let rt = tokio::runtime::Runtime::new().unwrap();
    rt.block_on(async {
        let unique_id = make_connection(url).await.map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))?;
        return Ok(unique_id)
    })
}


/// Closes a connection to the database in an non-async manner.
/// 
/// # Arguments
/// * `connection_id` - The unique ID for the connection to be closed
#[pyfunction]
pub fn blocking_close_connection(connection_id: String) -> Result<(), PyErr> {
    let rt = tokio::runtime::Runtime::new().unwrap();
    rt.block_on(async {
        let _ = close_connection(connection_id).await.map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))?;
        return Ok(())
    })
}


/// Checks if a connection is still open.
/// 
/// # Arguments
/// * `connection_id` - The unique ID for the connection to be checked
/// 
/// # Returns
/// * `Ok(bool)` - Whether or not the connection is still open
#[pyfunction]
pub fn blocking_check_connection(connection_id: String) -> Result<bool, PyErr> {
    let connection_state = CONNECTION_STATE.lock().unwrap();
    Ok(connection_state.contains_key(&connection_id))
}


// pub async fn close_connection(connection_id: String) -> Result<(), String> {
//     Ok(())
// }


#[cfg(test)]
mod tests {

    use super::*;

    /// Resets the connection state to an empty hashmap.
    fn reset_connection_state() {
        let mut connection_state = CONNECTION_STATE.lock().unwrap();
        connection_state.clear();
    }


    #[test]
    fn test_connect_protocol_from_string() {
        let protocol = ConnectProtocol::from_string("WS".to_string()).unwrap();
        match protocol {
            ConnectProtocol::WS => (),
            _ => panic!("Expected ConnectProtocol::WS(_)"),
        }
        let protocol = ConnectProtocol::from_string("HTTP".to_string()).unwrap();
        match protocol {
            ConnectProtocol::HTTP => (),
            _ => panic!("Expected ConnectProtocol::HTTP(_)"),
        }
        let protocol = ConnectProtocol::from_string("INVALID".to_string());
        match protocol {
            Ok(_) => panic!("Expected Err(_)"),
            Err(_) => (),
        }
    }

    #[test]
    fn test_connection_components() {
        let components = prep_connection_components("ws://localhost:8000".to_string()).unwrap();
        assert_eq!(components.0, ConnectProtocol::WS);
        assert_eq!(components.1, "localhost:8000".to_string());

        let components = prep_connection_components("http://localhost:8000".to_string()).unwrap();
        assert_eq!(components.0, ConnectProtocol::HTTP);
        assert_eq!(components.1, "localhost:8000".to_string());

        let components = prep_connection_components("invalid://localhost:8000".to_string());
        match components {
            Ok(_) => panic!("Expected Err(_)"),
            Err(_) => (),
        }
    }

}
