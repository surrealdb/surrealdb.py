#![recursion_limit = "256"]
use pyo3::prelude::*;
use pyo3::wrap_pyfunction;

mod connection;
mod operations;

use connection::python::{
    rust_make_connection_future, 
    rust_sign_in_future,
    rust_use_database_future,
    rust_use_namespace_future
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
    let _ = m.add_wrapped(wrap_pyfunction!(rust_make_connection_future));
    let _ = m.add_wrapped(wrap_pyfunction!(rust_sign_in_future));
    let _ = m.add_wrapped(wrap_pyfunction!(rust_use_database_future));
    let _ = m.add_wrapped(wrap_pyfunction!(rust_use_namespace_future));
    operations::operations_module_factory(m);
    Ok(())
}
