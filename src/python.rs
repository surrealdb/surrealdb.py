use std::convert::Into;
use std::time::Duration;
use pyo3::exceptions::PyTypeError;
use pyo3::prelude::*;
use crate::connection::{make_connection, Adapter, AdapterConfig};

/// Formats the sum of two numbers as string.
#[pyfunction]
pub fn sum_as_string(a: usize, b: usize) -> PyResult<String> {
    Ok((a + b).to_string())
}

#[pyfunction]
pub fn rust_connect(py: Python, address: &str) -> PyResult<Adapter> {
    let connect = tokio::runtime::Runtime::new()?
        .block_on(make_connection(address, AdapterConfig{
                strict: true,
                query_timeout: std::option::Option::from(Duration::new(10, 0)),
                transaction_timeout: std::option::Option::from(Duration::new(10, 0))
            })).map_err(|_| PyErr::new::<PyTypeError, _>("error") )?;

    Ok(connect)
}