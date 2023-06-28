//! Defines the core functions for managing connections. These functions should not be called directly
//! from the Python API but rather from the TCP connection in the runtime module. In this
//! module we can do the following:
//! 
//! * Get a connection from the connection manager
//! * Make a connection to the database and store it in the connection manager
//! * Close a connection to the database and remove it from the connection manager
//! * Check if a connection exists in the connection manager
use crate::connection::interface::{
    WrappedConnection,
    ConnectProtocol,
    prep_connection_components
};
use surrealdb::engine::remote::{
    ws::Ws,
    http::Http,
};
use surrealdb::Surreal;
use surrealdb::opt::auth::Root;


/// Makes a connection to the database in an async manner.
/// 
/// # Arguments
/// * `url` - The URL for the connection
/// 
/// # Returns
/// * `Ok(String)` - The unique ID for the connection that was just made
pub async fn make_connection(url: String) -> Result<WrappedConnection, String> {
    let components = prep_connection_components(url)?;
    let protocol = components.0;
    let address = components.1;
    let database = components.2;
    let namespace = components.3;

    match protocol {
        ConnectProtocol::WS => {
            let connection = Surreal::new::<Ws>(address).await.map_err(|e| e.to_string()).map_err(|e| e.to_string())?;
            connection.use_ns(namespace).use_db(database).await.map_err(|e| e.to_string()).map_err(|e| e.to_string())?;
            return Ok(WrappedConnection {
                web_socket: Some(connection),
                http: None
            })
        },
        ConnectProtocol::HTTP => {
            let connection = Surreal::new::<Http>(address).await.map_err(|e| e.to_string()).unwrap();
            connection.use_ns(namespace).use_db(database).await.map_err(|e| e.to_string()).unwrap();
            return Ok(WrappedConnection {
                http: Some(connection),
                web_socket: None
            })
        },
    }
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
pub async fn sign_in(connection: WrappedConnection, username: String, password: String) -> Result<String, String> {
    if connection.web_socket.is_some() {
        let connection = connection.web_socket.unwrap();
        connection.signin(Root {
            username: username.as_str(),
            password: password.as_str(),
        }).await.map_err(|e| e.to_string())?;
    } else if connection.http.is_some() {
        let connection = connection.http.unwrap();
        connection.signin(Root {
            username: username.as_str(),
            password: password.as_str(),
        }).await.map_err(|e| e.to_string())?;
    } else {
        return Err("connection not found".to_string())
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