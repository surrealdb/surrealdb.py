/// Handles operations to the database. 
use pyo3::prelude::{PyModule, wrap_pyfunction};
pub mod create;
pub mod set;
pub mod query;
pub mod update;
pub mod auth;


/// Adds operations python entry points to a module handling this factory.
/// 
/// # Arguments
/// * `m` - The module to add the entry points to
/// 
/// # Returns
/// * `()` - Nothing
pub fn operations_module_factory(m: &PyModule) {
    let _ = m.add_wrapped(wrap_pyfunction!(create::python::blocking_create));
    let _ = m.add_wrapped(wrap_pyfunction!(create::python::blocking_delete));
    let _ = m.add_wrapped(wrap_pyfunction!(set::python::blocking_set));
    let _ = m.add_wrapped(wrap_pyfunction!(set::python::blocking_unset));
    let _ = m.add_wrapped(wrap_pyfunction!(query::python::blocking_query));
    let _ = m.add_wrapped(wrap_pyfunction!(query::python::blocking_select));
    let _ = m.add_wrapped(wrap_pyfunction!(auth::python::blocking_sign_up));
    let _ = m.add_wrapped(wrap_pyfunction!(auth::python::blocking_invalidate));
    let _ = m.add_wrapped(wrap_pyfunction!(auth::python::blocking_authenticate));
    let _ = m.add_wrapped(wrap_pyfunction!(update::python::blocking_update));
    let _ = m.add_wrapped(wrap_pyfunction!(update::python::blocking_merge));
    let _ = m.add_wrapped(wrap_pyfunction!(update::python::blocking_patch));
}
