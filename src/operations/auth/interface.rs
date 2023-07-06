//! Defines structs, enums, and functions that aid in the passing of data between the Python API and auth core.
use pyo3::prelude::*;
use surrealdb::opt::auth::Jwt;


#[derive(Debug, Clone)]
#[pyclass]
pub struct WrappedJwt {
    pub jwt: Jwt,
}
