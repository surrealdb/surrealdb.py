//! Defines the Tokio runtime to be referenced throughouth the program.
use once_cell::sync::Lazy;
use tokio::runtime::{Builder, Runtime};


/// The Tokio runtime is needed to run the async functions.
pub static RUNTIME: Lazy<Runtime> = Lazy::new(|| {
    Builder::new_current_thread()
        .enable_all()
        .build()
        .expect("Failed to create Tokio runtime.")
});
