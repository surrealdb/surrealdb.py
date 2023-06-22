use uuid::Uuid;

use surrealdb::engine::remote::{
    ws::Ws,
    http::Http,
};
use surrealdb::Surreal;
use super::state::{
    CONNECTION_STATE,
    WrappedConnection,
    ConnectProtocol
};


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
    // surrealdb::Surreal::init();

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