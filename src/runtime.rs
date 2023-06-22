use pyo3::prelude::*;
use once_cell::sync::Lazy;
use tokio::runtime::{Builder, Runtime};

use crossbeam_channel::{bounded, Sender};

use tokio::net::{TcpListener, TcpStream};
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use serde::{Serialize, Deserialize};

use crate::routing::Routes;


pub static RUNTIME: Lazy<Runtime> = Lazy::new(|| {
    Builder::new_current_thread()
        .enable_all()
        .build()
        .expect("Failed to create Tokio runtime.")
});


pub static mut TRANSMITTER: Lazy<Sender<u32>> = Lazy::new(|| {
    let (tx, _) = bounded(10);
    tx
});


#[pyfunction]
pub fn start_background_thread(port: i32) -> PyResult<()> {
    let runtime = &RUNTIME;

    unsafe {
        let new_channel = bounded(10);
        let transmitter = Lazy::force_mut(&mut TRANSMITTER);
        *transmitter = new_channel.0;
    }
    let task = runtime.spawn(async move {
        let listener = TcpListener::bind(format!("127.0.0.1:{}", port)).await.unwrap();
        println!("Server started, listening on: {}", listener.local_addr().unwrap());
        loop {
            // Perform your desired task here
            let (mut socket, _) = listener.accept().await.unwrap();

            runtime.spawn(async move {
                let mut buffer = [0; 1024];
                loop {
                    let bytes_read = socket.read(&mut buffer).await.unwrap();
                    if bytes_read == 0 {
                        // Connection closed by the client
                        println!("Client disconnected: {}", socket.peer_addr().unwrap());
                        break;
                    }
                    let incoming_body: Routes = serde_json::from_slice(&buffer[..bytes_read]).unwrap();
                    println!("Received message: {:?}", incoming_body);
                    let response = "Message received successfully";
                    // Write the response back to the client
                    if let Err(e) = socket.write_all(response.as_bytes()).await {
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
