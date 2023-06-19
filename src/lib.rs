use pyo3::prelude::*;
use tokio::task::block_in_place;

use serde::{Deserialize, Serialize};
use surrealdb::engine::remote::ws::Ws;
use surrealdb::opt::auth::Root;
use surrealdb::sql::Thing;
use surrealdb::Surreal;


#[pyfunction]
fn say_hello() {
    println!("saying hello from Rust!");
}


#[pyfunction]
fn get_connection() {
    let rt = tokio::runtime::Runtime::new().unwrap();
    rt.block_on(async {
        let db = Surreal::new::<Ws>("127.0.0.1:8000").await;
        match db {
            Ok(_) => println!("Connected to server"),
            Err(e) => println!("Error connecting to server: {}", e),
        }
    });
}


#[pymodule]
fn rust_surrealdb(_py: Python, m: &PyModule) -> PyResult<()> {
    let _ = m.add_wrapped(wrap_pyfunction!(say_hello));
    let _ = m.add_wrapped(wrap_pyfunction!(get_connection));
    Ok(())
}