//! Defines the core functions for the auth operations against the database.
use surrealdb::opt::auth::Scope;
use serde_json::value::Value;

use super::interface::WrappedJwt;
use crate::connection::interface::WrappedConnection;


/// Signs up to a specific authentication scope in an async manner.
/// 
/// # Arguments
/// * `connection` - The connection that will be performing the signup
/// * `params` - The auth parameters to be used for the signup such as email and password
/// * `namespace` - The namespace to be used for the signup
/// * `database` - The database to be used for the signup
/// 
/// # Returns
/// * `Ok(String)` - The token for the signup
pub async fn sign_up(connection: WrappedConnection, params: Value, namespace: String, database: String, scope: String) -> Result<WrappedJwt, String> {
    let token = connection.connection.signup(Scope {
        namespace: namespace.as_str(),
        database: database.as_str(),
        scope: scope.as_str(),
        params: params,
    }).await.map_err(|e| e.to_string())?;
    let token = WrappedJwt {jwt: token};
    return Ok(token)
}


/// Invalidates the authentication for the current connection in an async manner.
/// 
/// # Arguments
/// * `connection` - The connection to be invalidated
/// 
/// # Returns
/// * `Ok(())` - The operation was successful
pub async fn invalidate(connection: WrappedConnection) -> Result<(), String> {
    connection.connection.invalidate().await.map_err(|e| e.to_string())?;
    return Ok(())
}


/// Authenticates the current connection with a JWT token in an async manner.
/// 
/// # Arguments
/// * `connection` - The connection to be authenticated
/// * `jwt` - The JWT token to be used for authentication
/// 
/// # Returns
/// * `Ok(())` - The operation was successful
pub async fn authenticate(connection: WrappedConnection, jwt: WrappedJwt) -> Result<(), String> {
    connection.connection.authenticate(jwt.jwt).await.map_err(|e| e.to_string())?;
    return Ok(())
}


#[cfg(test)]
mod tests {

    use super::*;
    // use crate::operations::query::core::query;
    use crate::connection::core::{make_connection, sign_in};
    use crate::operations::query::core::query;
	use tokio::runtime::Runtime;
    use serde_json::from_str;

    use std::thread;
    use std::time::Duration;

    use crate::docker_engine::{start, shutdown, DOCKER_ENGINE};

    fn generate_json(name: &str, age: i32) -> Value {
        let json_string = format!(r#"
            {{
                "name": "{}",
                "age": {}
            }}
        "#, name, age);
        let json_value: Value = from_str(&json_string).unwrap();
        json_value
    }

    fn generate_sql() -> String {
        let sql_string = r#"
            USE NAMESPACE namespace;
            USE DATABASE database;
            DEFINE SCOPE allusers SESSION 24h
                SIGNUP ( CREATE user SET user = $user, pass = crypto::argon2::generate($pass))
                SIGNIN ( SELECT * FROM user where email = $user AND crypto::argon2::compare(pass, $pass));
        "#;
        sql_string.to_string()
    }

    async fn create_conn(count: i32) -> Result<WrappedConnection, ()> {
        let mut counter = 0;
        loop {
            match make_connection("ws://localhost:8001/namespace/database".to_string()).await {
                Ok(conn) => {
                    return Ok(conn)
                },
                Err(_) => {
                    counter += 1;
                    if counter == count {
                        return Err(())
                    }
                    thread::sleep(Duration::from_millis(1000));
                }
            }
        }
    }

    #[test]
    fn test_sign_up() {
        let runtime = Runtime::new().unwrap();

        let outcome = runtime.block_on(async {
            let mut engine = DOCKER_ENGINE.lock().unwrap();
            start(&mut engine).await;

            let connection: WrappedConnection;
            match create_conn(20).await {
                Ok(conn) => {
                    connection = conn;
                },
                Err(_) => {
                    shutdown(&mut engine).await;
                    return Err("could not connect".to_string())
                }
            }
            // let connection = make_connection("ws://localhost:8000/namespace/database".to_string()).await.unwrap();
            sign_in(connection.clone(), "root".to_string(), "root".to_string()).await.unwrap();
            query(connection.clone(), generate_sql(), None).await.unwrap();

            let outcome = sign_up(
                connection, 
                generate_json("test_user", 20), 
                "namespace".to_string(), 
                "database".to_string(),
                "allusers".to_string()
            ).await;

            shutdown(&mut engine).await;

            return outcome
        });
        let _ = outcome.unwrap();
    }

    #[test]
    fn test_authenticate() {
        let runtime = Runtime::new().unwrap();

        let outcome = runtime.block_on(async {

            let mut engine = DOCKER_ENGINE.lock().unwrap();
            start(&mut engine).await;

            let connection: WrappedConnection;
            match create_conn(20).await {
                Ok(conn) => {
                    connection = conn;
                },
                Err(_) => {
                    shutdown(&mut engine).await;
                    return Err("could not connect".to_string())
                }
            }
            sign_in(connection.clone(), "root".to_string(), "root".to_string()).await.unwrap();
            query(connection.clone(), generate_sql(), None).await.unwrap();

            let signup_outcome = sign_up(
                connection.clone(), 
                generate_json("test_user", 20), 
                "namespace".to_string(), 
                "database".to_string(),
                "allusers".to_string()
            ).await.unwrap();

            let outcome = authenticate(
                connection, 
                signup_outcome
            ).await;

            shutdown(&mut engine).await;

            return outcome
        });
        let _ = outcome.unwrap();
    }

}