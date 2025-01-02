use pyo3::prelude::*;
use pyo3::pymodule;

mod connection;
mod python;

/// A Python module implemented in Rust.
#[pymodule]
fn rust_surrealdb(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(python::sum_as_string, m)?)?;
    m.add_wrapped(wrap_pyfunction!(python::rust_connect)).expect("TODO: panic message");
    m.add_wrapped(wrap_pyfunction!(python::rust_execute)).expect("TODO: panic message");
    Ok(())
}

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
