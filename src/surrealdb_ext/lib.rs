use pyo3::prelude::*;

mod async_db;
mod sync_db;

#[pymodule]
fn _surrealdb_ext(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<async_db::AsyncEmbeddedDB>()?;
    m.add_class::<sync_db::SyncEmbeddedDB>()?;
    Ok(())
}
