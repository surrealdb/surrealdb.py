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
        println!("Server started, listening on: {}", listener.local_addr().unwrap());
        loop {
            // Perform your desired task here
            let (mut socket, _) = listener.accept().await.unwrap();
            let transmitter = tx.clone();
            runtime.spawn(async move {
                let mut buffer = [0; 1024];
                loop {
                    println!("Waiting for message...");
                    let bytes_read = socket.read(&mut buffer).await.unwrap();
                    if bytes_read == 0 {
                        // Connection closed by the client
                        println!("Client disconnected: {}", socket.peer_addr().unwrap());
                        break;
                    }
                    println!("recieved message");
                    let incoming_body: Routes = serde_json::from_slice(&buffer[..bytes_read]).unwrap();
                    println!("Processeed message: {:?}", incoming_body);

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
