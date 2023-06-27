//! Defines the core functions for managing connections. These functions should not be called directly
//! from the Python API but rather from the TCP connection in the runtime module. In this
//! module we can do the following:
//! 
//! * Get a connection from the connection manager
//! * Make a connection to the database and store it in the connection manager
//! * Close a connection to the database and remove it from the connection manager
//! * Check if a connection exists in the connection manager
use surrealdb::engine::remote::{
    ws::Ws,
    http::Http,
};
use surrealdb::Surreal;
use surrealdb::opt::auth::Root;
use super::state::{
    WrappedConnection,
    ConnectProtocol,
    close_connection as close_connection_state,
    store_connection,
    get_components,
    CONNECTION_POOL
};


/// Checks and splits the connection string into its components.
/// 
/// # Arguments
/// * `url` - The URL for the connection to be checked and split
/// 
/// # Returns
/// * `Ok((ConnectProtocol, String))` - The connection protocol, addrss, database, and namespace
pub fn prep_connection_components(url: String) -> Result<(ConnectProtocol, String, String, String), String> {
    let parts: Vec<&str> = url.split("://").collect();
    let protocol = ConnectProtocol::from_string(parts[0].to_string())?;
    let address = parts[1];
    let address_parts: Vec<&str> = address.split("/").collect();

    if address_parts.len() != 3 {
        return Err("invalid address namespace and database need to be provided".to_string())
    }
    return Ok((protocol, address_parts[0].to_string(), address_parts[1].to_string(), address_parts[2].to_string()))
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
    let database = components.2;
    let namespace = components.3;

    let wrapped_connection: WrappedConnection;
    match protocol {
        ConnectProtocol::WS => {
            let connection = Surreal::new::<Ws>(address).await.map_err(|e| e.to_string())?;
            connection.use_ns(namespace).use_db(database).await.map_err(|e| e.to_string())?;
            wrapped_connection = WrappedConnection::WS(connection);
        },
        ConnectProtocol::HTTP => {
            let connection = Surreal::new::<Http>(address).await.map_err(|e| e.to_string())?;
            connection.use_ns(namespace).use_db(database).await.map_err(|e| e.to_string())?;
            wrapped_connection = WrappedConnection::HTTP(connection);
        },
    }

    // update the connection state
    let connection_id = store_connection(wrapped_connection).await;
    return Ok(connection_id)
}


/// Closes a connection to the database in an async manner.
/// 
/// # Arguments
/// * `connection_id` - The unique ID for the connection to be closed
pub async fn close_connection(connection_id: String) -> Result<String, String> {
    close_connection_state(connection_id).await?;
    return Ok("connection closed".to_string())
}

/// Checks if a connection is still open.
/// 
/// # Arguments
/// * `connection_id` - The unique ID for the connection to be checked
/// 
/// # Returns
/// * `Ok(bool)` - Whether or not the connection is still open
pub async fn check_connection(connection_id: String) -> Result<bool, String> {
    let (raw_index, connection_id) = get_components(connection_id)?;
    let connection_pool = CONNECTION_POOL[raw_index].lock().await;
    if !connection_pool.contains_key(&connection_id) {
        return Ok(false)
    }
    return Ok(true)
}


/// Signs into the database in an async manner.
/// 
/// # Arguments
/// * `connection_id` - The unique ID for the connection to be signed into
/// * `username` - The username to be used for signing in
/// * `password` - The password to be used for signing in
/// 
/// # Returns
/// * `Ok(String)` - Simple message that the connection has been signed into
pub async fn sign_in(connection_id: String, username: String, password: String) -> Result<String, String> {
    let (raw_index, connection_id) = get_components(connection_id)?;
    let mut connection_pool = CONNECTION_POOL[raw_index].lock().await;
    let connection = match connection_pool.get_mut(&connection_id) {
        Some(connection) => connection,
        None => return Err("connection does not exist".to_string())
    };

    match connection {
        WrappedConnection::WS(ws_connection) => {
            ws_connection.signin(Root {
                username: username.as_str(),
                password: password.as_str(),
            }).await.map_err(|e| e.to_string())?;
        },
        WrappedConnection::HTTP(http_connection) => {
            http_connection.signin(Root {
                username: username.as_str(),
                password: password.as_str(),
            }).await.map_err(|e| e.to_string())?;
        },
        _ => return Err("connection is not a valid type".to_string())
    }
    return Ok("signed in".to_string())
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
        let components = prep_connection_components("ws://localhost:8000/database/namespace".to_string()).unwrap();

        assert_eq!(components.0, ConnectProtocol::WS);
        assert_eq!(components.1, "localhost:8000".to_string());
        assert_eq!(components.2, "database".to_string());
        assert_eq!(components.3, "namespace".to_string());

        let components = prep_connection_components("http://localhost:8000/database/namespace".to_string()).unwrap();
        
        assert_eq!(components.0, ConnectProtocol::HTTP);
        assert_eq!(components.1, "localhost:8000".to_string());
        assert_eq!(components.2, "database".to_string());
        assert_eq!(components.3, "namespace".to_string());

        let components = prep_connection_components("invalid".to_string());
        match components {
            Ok(_) => panic!("Expected Err(_)"),
            Err(error) => {
                assert_eq!(error, "Invalid protocol: invalid".to_string());
            },
        }

        let components = prep_connection_components("invalid://localhost:8000/database/namespace".to_string());
        match components {
            Ok(_) => panic!("Expected Err(_)"),
            Err(error) => {
                assert_eq!(error, "Invalid protocol: invalid".to_string());
            },
        }

        let components = prep_connection_components("http://".to_string());
        match components {
            Ok(_) => panic!("Expected Err(_)"),
            Err(error) => {
                assert_eq!(error, "invalid address namespace and database need to be provided".to_string());
            },
        }

        let components = prep_connection_components("http://localhost:8000".to_string());
        match components {
            Ok(_) => panic!("Expected Err(_)"),
            Err(error) => {
                assert_eq!(error, "invalid address namespace and database need to be provided".to_string());
            },
        }
    }

}