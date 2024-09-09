//! Defines some helper functions for tests.
use surrealdb::Surreal;
use surrealdb::engine::any::connect;
use surrealdb::engine::any::Any;


/// Returns a test URL for the connection.
/// 
/// # Returns
/// * `String` - The test URL for the connection
pub fn get_test_url() -> String {
    let port = std::env::var("CONNECTION_PORT").unwrap_or("8000".to_string());
    let protocol = std::env::var("CONNECTION_PROTOCOL").unwrap_or("http".to_string());
    format!("{}://localhost:{}", protocol, port)
}

pub async fn get_test_connection() -> Surreal<Any> {
    let url = get_test_url();
    let connection: Surreal<Any> = connect(url).await.unwrap();
    connection.use_db("database").await.unwrap();
    connection.use_ns("namespace").await.unwrap();
    connection
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_get_test_url() {
        let url = get_test_url();
        assert_eq!(url, "http://localhost:8000");
    }

    #[tokio::test]
    async fn test_get_test_connection() {
        // test to just check that the connection is working
        let _ = get_test_connection().await;
    }
}
