use pyo3::prelude::*;
use super::state::CONNECTION_STATE;
use super::core::{
    make_connection,
    close_connection
};


/// Makes a connection to the database in an non-async manner.
/// 
/// # Arguments
/// * `url` - The URL for the connection
/// 
/// # Returns
/// * `Ok(String)` - The unique ID for the connection that was just made
#[pyfunction]
pub fn blocking_make_connection(url: String) -> Result<String, PyErr> {
    let rt = tokio::runtime::Runtime::new().unwrap();
    rt.block_on(async {
        let unique_id = make_connection(url).await.map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))?;
        return Ok(unique_id)
    })
}


/// Closes a connection to the database in an non-async manner.
/// 
/// # Arguments
/// * `connection_id` - The unique ID for the connection to be closed
#[pyfunction]
pub fn blocking_close_connection(connection_id: String) -> Result<(), PyErr> {
    let rt = tokio::runtime::Runtime::new().unwrap();
    rt.block_on(async {
        let _ = close_connection(connection_id).await.map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))?;
        return Ok(())
    })
}


/// Checks if a connection is still open.
/// 
/// # Arguments
/// * `connection_id` - The unique ID for the connection to be checked
/// 
/// # Returns
/// * `Ok(bool)` - Whether or not the connection is still open
#[pyfunction]
pub fn blocking_check_connection(connection_id: String) -> Result<bool, PyErr> {
    let connection_state = CONNECTION_STATE.lock().unwrap();
    Ok(connection_state.contains_key(&connection_id))
}
