//! The operations for storing, getting, and deleting connections from the connection pool.
use pyo3::prelude::*;
use core::fmt::Debug;
use std::collections::HashMap;
use std::sync::Arc;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::num::ParseIntError;

use surrealdb::Surreal;
use surrealdb::engine::remote::http::Client as HttpClient;
use surrealdb::engine::remote::ws::Client as WsClient;

use once_cell::sync::Lazy;
use tokio::sync::Mutex;
use uuid::Uuid;


// ==================================== static data ====================================


/// Due to connections needed to be cached in order to stay alive, this struct is used to store connections to the database
/// once they are opened. Whilst Mutexes are not the most efficient way to store connections, they are the easiest to implement
/// and are the most reliable. To reduce the penalty that Mutexes have on performance, the connection pool is split into 10
/// different pools, each with their own Mutex. This reduces the number of connections that will be denied once a mutex is
/// locked. Getting a connection can be done with the following code:
/// 
/// ```rust
/// let (raw_index, connection_id) = get_components(connection_id).unwrap();
/// let mut connection_pool = CONNECTION_POOL[raw_index].lock().await;
/// let connection = connection_pool.get_mut(&connection_id).unwrap();
/// ```
/// 
pub static CONNECTION_POOL: Lazy<[Arc<Mutex<HashMap<String, WrappedConnection>>>; 10]> = Lazy::new(|| {
    [
        Arc::new(Mutex::new(HashMap::new())),
        Arc::new(Mutex::new(HashMap::new())),
        Arc::new(Mutex::new(HashMap::new())),
        Arc::new(Mutex::new(HashMap::new())),
        Arc::new(Mutex::new(HashMap::new())),
        Arc::new(Mutex::new(HashMap::new())),
        Arc::new(Mutex::new(HashMap::new())),
        Arc::new(Mutex::new(HashMap::new())),
        Arc::new(Mutex::new(HashMap::new())),
        Arc::new(Mutex::new(HashMap::new())),
    ]
});


/// The index of the pool that the connection will be stored in.
pub static POOL_INDEX: AtomicUsize = AtomicUsize::new(0);


// ==================================== enums ====================================


/// Acts as a wrapper for the open database connection to be stored in the `CONNECTION_POOL`.
/// 
/// # Variants
/// * `WS` - live Websocket connection
/// * `HTTP` - live HTTP connection
#[derive(Clone, Debug)]
pub enum WrappedConnection {
    WS(Surreal<WsClient>),
    HTTP(Surreal<HttpClient>),
    #[cfg(test)]
    DummyInt(i32)
}


#[pyclass]
#[derive(Clone, Debug)]
pub struct WrappedConnectionStruct {
    pub web_socket: Option<Surreal<WsClient>>,
    pub http: Option<Surreal<HttpClient>>,
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


// ==================================== operation functions ====================================


/// Gets the index of the pool that the connection will be stored in in an atomic way.
/// 
/// # Returns
/// * `usize` - The index of the pool that the connection will be stored in.
pub fn get_index() -> usize {
    
    loop {
        // load the current value
        let current_value = POOL_INDEX.load(Ordering::SeqCst);

        if current_value >= 9 {
            // if the current value is greater than 10, then we need to reset it to 0 but we need an 
            match POOL_INDEX.compare_exchange(current_value, 0, Ordering::SeqCst, Ordering::SeqCst) {
                Ok(_) => {
                    // if we successfully reset the value, then we can return the current value
                    return current_value;
                },
                Err(_) => {
                    // if we failed to reset the value, then we need to try again
                    continue;
                }
            }
        }
        else {
            // if the current value is less than 10, then we need to increment it by 1 but we need an 
            match POOL_INDEX.compare_exchange(current_value, current_value + 1, Ordering::SeqCst, Ordering::SeqCst) {
                Ok(_) => {
                    // if we successfully incremented the value, then we can return the current value
                    return current_value;
                },
                Err(_) => {
                    // if we failed to increment the value, then we need to try again
                    continue;
                }
            }
        }
    }
}


/// Stores a connection in the connection pool.
/// 
/// # Arguments
/// * `connection` - The connection to store in the connection pool.
/// 
/// # Returns
/// * `String` - The connection ID of the connection that was stored.
pub async fn store_connection(connection: WrappedConnection) -> String {
    let index = get_index();
    let connection_id = Uuid::new_v4().to_string();
    let mut pool = CONNECTION_POOL[index].lock().await;
    pool.insert(connection_id.clone(), connection);
    return format!("{}://{}", index, connection_id);
}


/// Closes a connection in the connection pool.
/// 
/// # Arguments
/// * `connection_id` - The connection ID of the connection to close.
/// 
/// # Returns
/// * `Result<(), String>` - The result of the operation.
pub async fn close_connection(connection_id: String) -> Result<(), String> {
    let (raw_index, connection_id) = get_components(connection_id)?;
    let mut guard = CONNECTION_POOL[raw_index].lock().await;
    guard.remove(&connection_id);
    Ok(())
}


/// Splits the connection ID into its components.
/// 
/// # Arguments
/// * `connection_id` - The connection ID to split.
/// 
/// # Returns
/// * `Result<(usize, String), String>` - The index where the connection is stored in the connection pool and the connection ID.
pub fn get_components(connection_id: String) -> Result<(usize, String), String> {
    let components = connection_id.split("://").collect::<Vec<&str>>();
    if components.len() != 2 {
        return Err(format!("Invalid: connection ID '{}' is not valid", connection_id));
    }
    let raw_index: usize = components[0].parse().map_err(|e: ParseIntError| {e.to_string()})?;
    if &raw_index > &9 || &raw_index < &0 {
        return Err(format!("Invalid: connection ID: {} is out of bounds", raw_index));
    }
    return Ok((raw_index, components[1].to_string()));
}


#[cfg(test)]
mod tests {

    use super::*;
    use tokio::runtime::{Builder, Runtime};

    fn create_multithread_test_runtime() -> Runtime {
        Builder::new_multi_thread()
            .enable_all()
            .build()
            .expect("Failed to create Tokio runtime.")
    }

    fn create_test_runtime() -> Runtime {
        Builder::new_current_thread()
            .enable_all()
            .build()
            .expect("Failed to create Tokio runtime.")
    }

    #[test]
    fn test_increase_ordering_single_threaded() {
        POOL_INDEX.store(0, Ordering::SeqCst);
        let expected_values = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 0, 1, 2, 3, 4];

        for i in expected_values {
            let new_value = get_index();
            assert_eq!(new_value, i);
        }
    }

    #[test]
    fn test_increase_ordering_multithreaded() {
        POOL_INDEX.store(0, Ordering::SeqCst);
        let runtime = create_multithread_test_runtime();

        let mut handles = Vec::new();

        for _ in 0..1000 {
            let task = runtime.spawn(async {
                let new_value = get_index();
                assert_eq!(new_value < 10, true);
            });
            handles.push(task);
        }

        for handle in handles {
            runtime.block_on(handle).unwrap();
        }
    }

    #[test]
    fn test_store_connection() {
        // create the test async runtime
        let runtime = create_test_runtime();

        // create the dummy connections
        let connection: WrappedConnection = WrappedConnection::DummyInt(1);
        let connection_two = WrappedConnection::DummyInt(2);

        // insert the connections into the connection pool
        let task = runtime.spawn(async {
            store_connection(connection).await
        });
        let task_two = runtime.spawn(async {
            store_connection(connection_two).await
        });
        let connection_id = runtime.block_on(task).unwrap();
        let connection_id_two = runtime.block_on(task_two).unwrap();

        // get the index and id of the connection
        let raw_id = connection_id.split("://").collect::<Vec<&str>>()[1];
        let raw_index: usize = connection_id.split("://").collect::<Vec<&str>>()[0].parse().unwrap();
        let raw_id_two = connection_id_two.split("://").collect::<Vec<&str>>()[1];
        let raw_index_two: usize = connection_id_two.split("://").collect::<Vec<&str>>()[0].parse().unwrap();

        // get the connection from the connection pool
        let value_one = runtime.block_on(async{
            let guard = CONNECTION_POOL[raw_index].lock().await;
            let wrapped_connection = guard.get(raw_id).unwrap();
            match wrapped_connection {
                WrappedConnection::DummyInt(value) => value.clone(),
                _ => panic!("Expected a WrappedConnection::DummyInt")
            }
        });
        let value_two = runtime.block_on(async{
            let guard = CONNECTION_POOL[raw_index_two].lock().await;
            let wrapped_connection = guard.get(raw_id_two).unwrap();
            match wrapped_connection {
                WrappedConnection::DummyInt(value) => value.clone(),
                _ => panic!("Expected a WrappedConnection::DummyInt")
            }
        });

        assert_eq!(value_one, 1);
        assert_eq!(value_two, 2);
    }

    #[test]
    fn test_close_connection() {
        let runtime = create_test_runtime();

        let connection: WrappedConnection = WrappedConnection::DummyInt(1);

        let task = runtime.spawn(async {
            store_connection(connection).await
        });
        let connection_id = runtime.block_on(task).unwrap();

        let raw_id = connection_id.split("://").collect::<Vec<&str>>()[1].to_string();
        let raw_index: usize = connection_id.split("://").collect::<Vec<&str>>()[0].parse().unwrap();

        let task = runtime.spawn(async {
            close_connection(connection_id).await
        });
        let outcome = runtime.block_on(task).unwrap();
        
        assert_eq!(outcome, Ok(()));
        let another_outcome = runtime.block_on(async{
            let guard = CONNECTION_POOL[raw_index].lock().await;
            match guard.get(&raw_id) {
                Some(_) => Err("Expected None".to_string()),
                None => Ok(())
            }
        });
        assert_eq!(another_outcome, Ok(()));
    }

    #[test]
    fn test_get_components() {
        let false_connection_id = "test".to_string();

        match get_components(false_connection_id) {
            Ok(_) => panic!("Expected an error"),
            Err(e) => assert_eq!(e.to_string(), "Invalid: connection ID 'test' is not valid".to_string())
        }

        let false_connection_id = "10://test".to_string();

        match get_components(false_connection_id) {
            Ok(_) => panic!("Expected an error"),
            Err(e) => assert_eq!(e.to_string(), "Invalid: connection ID: 10 is out of bounds".to_string())
        }
    }

}
