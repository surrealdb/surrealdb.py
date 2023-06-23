//! The runtime runs indefinitely to accept messages from the PyO3 functions and route them to the appropiate core operation.
//! The runtime has to run in the background in order to keep the connections open and to keep the state of the connections.
//! Without the runtime the connections would be created and stored but the channels would be closed. If we were to send the
//! connection structs over to the python side we would have complications with converting the connection structs to python 
//! objects. This would also highly couple the python side to the rust side. If the Rust client was to change, it would only
//! need to be changed on the Rust side as opposed to the Rust and Python side with all the new complications of converting
//! the functionality of the new Rust client to Python.
//! The runtime has the following layers:
//! 
//! 1. Python client calls a PyO3 function with a operation request and connection ID. 
//! 2. The PyO3 function sends the operation request and connection ID to the runtime via TCP. 
//! 3. The runtime accepts the message and routes it to the appropiate core operation which is found in the routing module.
//! 4. Once the message is routed, the message is going to be at the right core operation, this is where the DB connection is got and the operation is performed.
//! 
//! Once the operation is achieved, the result is then passed back to the runtime and sent back to the PyO3 function via TCP and then the python client.
use std::net::TcpStream;
use std::io::{Read, Write};
use pyo3::prelude::*;
use once_cell::sync::Lazy;
use tokio::runtime::{Builder, Runtime};
use tokio::sync::mpsc;

use tokio::net::TcpListener;
use tokio::io::{AsyncReadExt, AsyncWriteExt};

use crate::routing::handle::{Routes, handle_routes};
use crate::connection::state::{
    track_connections,
    ConnectionMessage,
};


/// The Tokio runtime is needed to run the async functions.
pub static RUNTIME: Lazy<Runtime> = Lazy::new(|| {
    Builder::new_current_thread()
        .enable_all()
        .build()
        .expect("Failed to create Tokio runtime.")
});


#[pyfunction]
pub fn start_background_thread(port: i32) -> PyResult<()> {
    let runtime = &RUNTIME;
    let (tx, rx) = mpsc::channel::<ConnectionMessage>(10);
    let _tracking_task = runtime.spawn(async move {
        track_connections(rx).await;
    });
    let task = runtime.spawn(async move {
        let listener = TcpListener::bind(format!("127.0.0.1:{}", port)).await.unwrap();
        loop {
            // Perform your desired task here
            let (mut socket, _) = listener.accept().await.unwrap();
            let transmitter = tx.clone();
            runtime.spawn(async move {
                let mut buffer = [0; 1024];
                loop {
                    let bytes_read = socket.read(&mut buffer).await.unwrap();
                    if bytes_read == 0 {
                        break;
                    }
                    let incoming_body: Routes = serde_json::from_slice(&buffer[..bytes_read]).unwrap();

                    let response_json = match handle_routes(incoming_body, transmitter.clone()).await {
                        Ok(response) => {
                            serde_json::to_string(&response).unwrap()
                        },
                        Err(e) => {
                            println!("{}", e);
                            serde_json::to_string(&e).unwrap()
                        }
                    };

                    // Write the response back to the client
                    if let Err(e) = socket.write_all(response_json.as_bytes()).await {
                        eprintln!("Failed to write to socket: {}", e);
                        break;
                    }
                }
            });
        }
    });
    let _ = runtime.block_on(task);
    Ok(())
}


/// Sends a message to the runtime and returns the response from the runtime.
/// 
/// # Arguments
/// * `message` - The message to be sent to the runtime.
/// * `port` - The port that the runtime is listening on.
/// 
/// # Returns
/// The response from the runtime.
pub fn send_message_to_runtime(message: Routes, port: i32) -> Result<Routes, String> {
    let outgoing_json = serde_json::to_string(&message).map_err(|e| e.to_string())?;
    let mut stream = TcpStream::connect(format!("127.0.0.1:{}", port)).map_err(|e| e.to_string())?;
    stream.write_all(outgoing_json.as_bytes()).map_err(|e| e.to_string())?;
    
    let mut response_buffer = [0; 1024];
    // Read the response from the listener
    let bytes_read = stream.read(&mut response_buffer).map_err(|e| e.to_string())?;

    // Deserialize the response from JSON
    let response_json = &response_buffer[..bytes_read];
    let response_body: Routes = serde_json::from_slice(response_json).map_err(|e| e.to_string())?;
    Ok(response_body)
}
