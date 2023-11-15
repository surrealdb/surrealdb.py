#![recursion_limit = "256"]
use pyo3::prelude::*;
use pyo3::wrap_pyfunction;

mod connection;
mod operations;

use connection::python::{
    blocking_make_connection, 
    blocking_sign_in,
    blocking_use_database,
    blocking_use_namespace
};


/// Wraps a future into a python object. The example code is the following:
/// ```rust
/// pyo3_asyncio::tokio::future_into_py(py, async move {
///         let wrapped_connection = make_connection(url).await
///                                                      .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))?;
///         Ok(wrapped_connection)
///     })
/// ```
#[macro_export]
macro_rules! py_future_wrapper {
    ($py:expr, $func:ident($($arg:expr),*)) => {
        pyo3_asyncio::tokio::future_into_py($py, async move {
            let wrapped_connection = $func($($arg),*).await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("{:?}", e)))?;
            Ok(wrapped_connection)
        })
    };
}


#[pymodule]
fn rust_surrealdb(_py: Python, m: &PyModule) -> PyResult<()> {
    let _ = m.add_wrapped(wrap_pyfunction!(blocking_make_connection));
    let _ = m.add_wrapped(wrap_pyfunction!(blocking_sign_in));
    let _ = m.add_wrapped(wrap_pyfunction!(blocking_use_database));
    let _ = m.add_wrapped(wrap_pyfunction!(blocking_use_namespace));
    operations::operations_module_factory(m);
    Ok(())
}
