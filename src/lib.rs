use pyo3::prelude::*;
use pyo3::wrap_pyfunction;

#[macro_use]
mod connection;

mod operations;
mod runtime;
mod routing;


use connection::python::{
    blocking_make_connection, 
    blocking_close_connection,
    blocking_check_connection,
    blocking_sign_in,
    blocking_make_connection_pass,
    blocking_sign_in_pass
};


#[pymodule]
fn rust_surrealdb(_py: Python, m: &PyModule) -> PyResult<()> {
    let _ = m.add_wrapped(wrap_pyfunction!(blocking_make_connection));
    let _ = m.add_wrapped(wrap_pyfunction!(blocking_close_connection));
    let _ = m.add_wrapped(wrap_pyfunction!(blocking_check_connection));
    let _ = m.add_wrapped(wrap_pyfunction!(blocking_sign_in));
    let _ = m.add_wrapped(wrap_pyfunction!(blocking_make_connection_pass));
    let _ = m.add_wrapped(wrap_pyfunction!(blocking_sign_in_pass));
    operations::operations_module_factory(m);
    let _ = m.add_wrapped(wrap_pyfunction!(runtime::start_background_thread));
    Ok(())
}
