//! Python entry point for setting a new key.
use pyo3::prelude::*;
use pyo3::types::PyAny;
use serde_json::value::Value;

use crate::routing::enums::Message;
use crate::routing::handle::Routes;
use crate::runtime::send_message_to_runtime;

use super::interface::{
    SetRoutes,
    SetData,
    BasicMessage
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
pub fn blocking_set<'a>(connection_id: String, key: String, value: &'a PyAny, port: i32) -> Result<(), PyErr> {
    let value: Value = serde_json::from_str(&value.to_string()).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

    let route = SetRoutes::Set(Message::<SetData, BasicMessage>::package_send(SetData{connection_id, key, value}));
    let message = Routes::Set(route);

    let response_body = send_message_to_runtime(message, port).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string())
    })?;

    let response = match response_body {
        Routes::Set(message) => message,
        _ => return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Invalid response from listener"))
    };
    let _ = match response {
        SetRoutes::Set(message) => {
            message.handle_recieve().map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))?
        },
    };
    Ok(())
}
