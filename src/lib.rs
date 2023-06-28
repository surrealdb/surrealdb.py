use pyo3::prelude::*;
use pyo3::wrap_pyfunction;


mod connection;

mod operations;
mod runtime;


use connection::python::{
    blocking_make_connection, 
    blocking_sign_in,
};


#[pymodule]
fn rust_surrealdb(_py: Python, m: &PyModule) -> PyResult<()> {
    let _ = m.add_wrapped(wrap_pyfunction!(blocking_make_connection));
    let _ = m.add_wrapped(wrap_pyfunction!(blocking_sign_in));
    operations::operations_module_factory(m);
    Ok(())
}
