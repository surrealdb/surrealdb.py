use pyo3::prelude::*;
use pyo3::types::PyAny;
use serde_json::value::Value;

use std::io::{Read, Write};
use std::net::TcpStream;

use crate::routing::enums::Message;
use crate::routing::handle::Routes;

use super::interface::{
    CreateRoutes,
    CreateData,
    EmptyState
};


#[pyfunction]
pub fn blocking_create<'a>(connection_id: String, table_name: String, data: &'a PyAny, port: i32) -> Result<(), PyErr> {
    let data: Value = serde_json::from_str(&data.to_string()).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

    let route = CreateRoutes::Create(Message::<CreateData, EmptyState>::package_send(CreateData{connection_id, table_name, data}));
    let message = Routes::Create(route);

    let outgoing_json = serde_json::to_string(&message).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
    let mut stream = TcpStream::connect(format!("127.0.0.1:{}", port)).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
    stream.write_all(outgoing_json.as_bytes()).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

    let mut response_buffer = [0; 1024];
    // Read the response from the listener
    let bytes_read = stream.read(&mut response_buffer).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

    // Deserialize the response from JSON
    let response_json = &response_buffer[..bytes_read];
    let response_body: Routes = serde_json::from_slice(response_json).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

    let response = match response_body {
        Routes::Create(message) => message,
        _ => return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Invalid response from listener"))
    };
    let _ = match response {
        CreateRoutes::Create(message) => {
            message.handle_recieve().map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))?
        },
        _ => return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Invalid response from listener"))
    };
    Ok(())
}