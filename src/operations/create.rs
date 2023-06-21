use pyo3::prelude::*;
use pyo3::types::PyAny;
use serde_json::value::Value;
use crate::connection::{
    CONNECTION_STATE,
    WrappedConnection
};


pub async fn create(connection_id: String, table_name: String, data: Value) -> Result<(), String> {
    let connection_state = CONNECTION_STATE.lock().unwrap();
    if !connection_state.contains_key(&connection_id) {
        return Err("Connection does not exist".to_string())
    }
    let connection = connection_state.get(&connection_id).unwrap();

    match connection {
        WrappedConnection::WS(ws_connection) => {
            ws_connection.create(table_name).content(data).await.map_err(|e| e.to_string())?;
        },
        WrappedConnection::HTTP(http_connection) => {
            http_connection.create(table_name).content(data).await.map_err(|e| e.to_string())?;
        },
    }
    Ok(())
}


#[pyfunction]
pub fn blocking_create<'a>(connection_id: String, table_name: String, data: &'a PyAny) -> Result<(), PyErr> {
    let data: Value = serde_json::from_str(&data.to_string()).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
    let rt = tokio::runtime::Runtime::new().unwrap();
    rt.block_on(async {
        let _ = create(connection_id, table_name, data).await.map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))?;
        return Ok(())
    })
}
