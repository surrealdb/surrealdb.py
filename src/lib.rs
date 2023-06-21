use pyo3::prelude::*;
use pyo3::wrap_pyfunction;

mod connection;
mod operations;

use connection::{
    blocking_make_connection, 
    blocking_close_connection,
    blocking_check_connection
};



#[pymodule]
fn rust_surrealdb(_py: Python, m: &PyModule) -> PyResult<()> {
    let _ = m.add_wrapped(wrap_pyfunction!(blocking_make_connection));
    let _ = m.add_wrapped(wrap_pyfunction!(blocking_close_connection));
    let _ = m.add_wrapped(wrap_pyfunction!(blocking_check_connection));
    Ok(())
}