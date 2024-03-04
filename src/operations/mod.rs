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
    let _ = m.add_wrapped(wrap_pyfunction!(create::python::rust_create_future));
    let _ = m.add_wrapped(wrap_pyfunction!(create::python::rust_delete_future));
    let _ = m.add_wrapped(wrap_pyfunction!(set::python::rust_set_future));
    let _ = m.add_wrapped(wrap_pyfunction!(set::python::rust_unset_future));
    let _ = m.add_wrapped(wrap_pyfunction!(query::python::rust_query_future));
    let _ = m.add_wrapped(wrap_pyfunction!(query::python::rust_select_future));
    let _ = m.add_wrapped(wrap_pyfunction!(auth::python::rust_sign_up_future));
    let _ = m.add_wrapped(wrap_pyfunction!(auth::python::rust_invalidate_future));
    let _ = m.add_wrapped(wrap_pyfunction!(auth::python::rust_authenticate_future));
    let _ = m.add_wrapped(wrap_pyfunction!(update::python::rust_update_future));
    let _ = m.add_wrapped(wrap_pyfunction!(update::python::rust_merge_future));
    let _ = m.add_wrapped(wrap_pyfunction!(update::python::rust_patch_future));
}
