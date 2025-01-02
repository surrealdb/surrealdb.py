use crate::connection::{execute, make_connection, Adapter, AdapterConfig};
use pyo3::exceptions::PyTypeError;
use pyo3::prelude::*;
use std::time::Duration;

/// Formats the sum of two numbers as string.
#[pyfunction]
pub fn sum_as_string(a: usize, b: usize) -> PyResult<String> {
    Ok((a + b).to_string())
}

#[pyfunction]
pub fn rust_connect(_py: Python, address: &str) -> PyResult<Adapter> {
    let connect = tokio::runtime::Runtime::new()
        .unwrap()
        .block_on(make_connection(
            address,
            AdapterConfig {
                strict: true,
                query_timeout: std::option::Option::from(Duration::new(10, 0)),
                transaction_timeout: std::option::Option::from(Duration::new(10, 0)),
            },
        ))
        .map_err(|e| {
            println!("{}", e);
            PyErr::new::<PyTypeError, _>("error")
        })?;

    Ok(connect)
}

#[pyfunction]
pub fn rust_execute(_py: Python, adapter: &Adapter, request_data: Vec<u8>) -> PyResult<Vec<u8>> {
    let connect = tokio::runtime::Runtime::new()
        .unwrap()
        .block_on(execute(adapter, request_data))
        .map_err(|e| {
            println!("{}", e);
            PyErr::new::<PyTypeError, _>("error")
        })?;

    Ok(connect)
}
