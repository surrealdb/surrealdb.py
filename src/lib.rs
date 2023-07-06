use pyo3::prelude::*;
use pyo3::wrap_pyfunction;


mod connection;

mod operations;
mod runtime;

#[cfg(test)]
mod docker_engine;


use connection::python::{
    blocking_make_connection, 
    blocking_sign_in,
    blocking_use_database,
    blocking_use_namespace
};


#[pymodule]
fn rust_surrealdb(_py: Python, m: &PyModule) -> PyResult<()> {
    let _ = m.add_wrapped(wrap_pyfunction!(blocking_make_connection));
    let _ = m.add_wrapped(wrap_pyfunction!(blocking_sign_in));
    let _ = m.add_wrapped(wrap_pyfunction!(blocking_use_database));
    let _ = m.add_wrapped(wrap_pyfunction!(blocking_use_namespace));
    operations::operations_module_factory(m);
    Ok(())
}
