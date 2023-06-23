//! Python entry point for creating a new record in the database.
use pyo3::prelude::*;
use pyo3::types::PyAny;
use serde_json::value::Value;

use crate::routing::enums::Message;
use crate::routing::handle::Routes;
use crate::runtime::send_message_to_runtime;

use super::interface::{
    CreateRoutes,
    CreateData,
    EmptyState
};


/// Creates a new record in the database in an non-async manner.
/// 
/// # Arguments
/// * `connection_id` - The ID of the connection being used for the operation
/// * `table_name` - The name of the table to create the record in
/// * `data` - The data to be inserted into the table
/// * `port` - The port for the connection to the runtime
/// 
/// # Returns
/// * `Ok(())` - The operation was successful
#[pyfunction]
pub fn blocking_create<'a>(connection_id: String, table_name: String, data: &'a PyAny, port: i32) -> Result<(), PyErr> {
    let data: Value = serde_json::from_str(&data.to_string()).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

    let route = CreateRoutes::Create(Message::<CreateData, EmptyState>::package_send(CreateData{connection_id, table_name, data}));
    let message = Routes::Create(route);

    let response_body = send_message_to_runtime(message, port).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string())
    })?;

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