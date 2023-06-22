/// Handles operations to the database. 
use pyo3::prelude::{PyModule, wrap_pyfunction};
pub mod create;


/// Adds operations python entry points to a module handling this factory.
/// 
/// # Arguments
/// * `m` - The module to add the entry points to
/// 
/// # Returns
/// * `()` - Nothing
pub fn operations_module_factory(m: &PyModule) {
    let _ = m.add_wrapped(wrap_pyfunction!(create::python::blocking_create));
}
