use uuid::Uuid;

use surrealdb::engine::remote::{
    ws::Ws,
    http::Http,
};
use surrealdb::Surreal;
use super::state::{
    WrappedConnection,
    ConnectProtocol,
    TrackingMessage,
    CreateConnection,
    DeleteConnection,
    get_connection
};
use tokio::sync::mpsc::Sender;


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
pub async fn make_connection(url: String, tx: Sender<TrackingMessage>) -> Result<String, String> {
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
    let connection_id = Uuid::new_v4().to_string();
    // let mut lock = CONNECTION_STATE.lock().unwrap();
    // lock.insert(connection_id.clone(), wrapped_connection.clone());
    tx.send(TrackingMessage::Create(CreateConnection {
        connection_id: connection_id.clone(),
        connection: wrapped_connection.clone(),
    })).await.map_err(|e| e.to_string())?;
    return Ok(connection_id)
}


/// Closes a connection to the database in an async manner.
/// 
/// # Arguments
/// * `connection_id` - The unique ID for the connection to be closed
pub async fn close_connection(connection_id: String, tx: Sender<TrackingMessage>) -> Result<(), String> {
    // let mut lock = CONNECTION_STATE.lock().unwrap();
    // lock.remove(&connection_id);
    tx.send(TrackingMessage::Delete(DeleteConnection {
        connection_id: connection_id.clone(),
    })).await.map_err(|e| e.to_string())?;
    return Ok(())
}

/// Checks if a connection is still open.
/// 
/// # Arguments
/// * `connection_id` - The unique ID for the connection to be checked
/// 
/// # Returns
/// * `Ok(bool)` - Whether or not the connection is still open
pub async fn check_connection(connection_id: String, tx: Sender<TrackingMessage>) -> Result<bool, String> {
    let connection = get_connection(connection_id.clone(), tx).await;
    if connection.is_none() {
        return Ok(false)
    }
    // let lock = CONNECTION_STATE.lock().unwrap();
    // if !lock.contains_key(&connection_id) {
    //     return Ok(false)
    // }
    return Ok(true)
}


#[cfg(test)]
mod tests {

    use super::*;

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