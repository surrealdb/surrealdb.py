//! Defines structs, enums, and functions that aid in the passing of data between the Python API and connection core.
use pyo3::prelude::*;
use core::fmt::Debug;

use surrealdb::Surreal;
use surrealdb::engine::any::Any;


/// A wrapped connection that can be passed between the Python API and connection core.
/// 
/// # Fields
/// * `connection` - The connection to be wrapped
#[pyclass]
#[derive(Clone, Debug)]
pub struct WrappedConnection {
    pub connection: Surreal<Any>
}


/// Checks and splits the connection string into its components.
/// 
/// # Arguments
/// * `url` - The URL for the connection to be checked and split
/// 
/// # Returns
/// * `Ok((String, String, String))` - connection address, namespace, and database
pub fn extract_connection_components(url: String) -> Result<(String, String, String), String> {
    let parts: Vec<&str> = url.split("://").collect();
    if parts.len() != 2 {
        return Err("invalid url".to_string())
    }
    let protocol = parts[0];
    let address = parts[1];
    let mut address_parts: Vec<&str> = address.split("/").collect();

    let total_address_parts = address_parts.len();

    if &total_address_parts < &3 {
        return Err("invalid address namespace and database need to be provided".to_string())
    }

    let database = address_parts.pop().unwrap().to_string();
    let namespace = address_parts.pop().unwrap().to_string();
    let address = address_parts.join("/");

    Ok((
        format!("{}://{}", protocol, address), 
        namespace, 
        database
    ))
}


#[cfg(test)]
mod tests {

    use super::*;

    #[test]
    fn test_ws() {
        let url = "ws://localhost:8000/namespace/database".to_string();
        let (url, namespace, database) = extract_connection_components(url).unwrap();

        assert_eq!(url, "ws://localhost:8000".to_string());
        assert_eq!(database, "database".to_string());
        assert_eq!(namespace, "namespace".to_string());
    }

    #[test]
    fn test_http() {
        let url = "http://localhost:8000/namespace/database".to_string();
        let (url, namespace, database) = extract_connection_components(url).unwrap();

        assert_eq!(url, "http://localhost:8000".to_string());
        assert_eq!(database, "database".to_string());
        assert_eq!(namespace, "namespace".to_string());
    }

    #[test]
    fn test_rocksdb() {
        let url = "rocksdb:///tmp/test.db/namespace/database".to_string();
        let (url, namespace, database) = extract_connection_components(url).unwrap();

        assert_eq!(url, "rocksdb:///tmp/test.db".to_string());
        assert_eq!(database, "database".to_string());
        assert_eq!(namespace, "namespace".to_string());
    }

    #[test]
    fn test_rocksdb_three_lines() {
        let url = "rocksdb://tmp/test.db/namespace/database".to_string();
        let (url, namespace, database) = extract_connection_components(url).unwrap();

        assert_eq!(url, "rocksdb://tmp/test.db".to_string());
        assert_eq!(database, "database".to_string());
        assert_eq!(namespace, "namespace".to_string());
    }

}