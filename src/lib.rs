use pyo3::prelude::*;
use pyo3::wrap_pyfunction;

mod connection;

use connection::{blocking_make_connection, blocking_close_connection};



#[pymodule]
fn rust_surrealdb(_py: Python, m: &PyModule) -> PyResult<()> {
    let _ = m.add_wrapped(wrap_pyfunction!(blocking_make_connection));
    let _ = m.add_wrapped(wrap_pyfunction!(blocking_close_connection));
    Ok(())
}