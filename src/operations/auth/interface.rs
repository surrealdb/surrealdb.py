//! Defines structs, enums, and functions that aid in the passing of data between the Python API and auth core.
use pyo3::prelude::*;
use surrealdb::opt::auth::Jwt;


/// A wrapper for the Jwt struct that allows it to be passed to and from Python.
/// 
/// # Fields
/// * `jwt` - The Jwt struct to be wrapped
#[derive(Debug, Clone)]
#[pyclass]
pub struct WrappedJwt {
    pub jwt: Jwt,
}
