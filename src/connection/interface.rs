//! Defines structs, enums, and functions that aid in the passing of data between the Python API and connection core.
use pyo3::prelude::*;
use core::fmt::Debug;

use surrealdb::Surreal;
use surrealdb::engine::any::Any;


#[pyclass]
#[derive(Clone, Debug)]
pub struct WrappedConnection {
    pub connection: Surreal<Any>
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
    KV_MEM
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
            "MEMORY" => Ok(Self::KV_MEM),
            _ => Err(format!("Invalid protocol: {}", protocol_type)),
        }
    }

    pub fn to_string(&self) -> String {
        match self {
            Self::WS => "ws".to_string(),
            Self::HTTP => "http".to_string(),
            Self::KV_MEM => "memory".to_string(),
        }
    }

}


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