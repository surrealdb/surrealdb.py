//! Defines the core functions for the auth operations against the database.
use surrealdb::opt::auth::Scope;
use serde_json::value::Value;
use serde::Serialize;

use super::interface::WrappedJwt;
use crate::connection::interface::WrappedConnection;


#[derive(Debug, Serialize)]
struct AuthParams {
    email: String,
    password: String,
}


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
    use crate::test_url::get_test_connection;
    use surrealdb::opt::auth::Root;

    #[tokio::test]
    async fn test_sign_up() {
        let connection = get_test_connection().await;
        let jwt = connection.signin(Root {
            username: "root",
            password: "root",
        }).await.unwrap();
        connection.use_ns("namespace").use_db("database").await.unwrap();

        // Define the scope
        let sql = r#"
        DEFINE SCOPE user_scope SESSION 24h
        SIGNUP ( CREATE user SET email = $email, password = crypto::argon2::generate($password) )
        SIGNIN ( SELECT * FROM user WHERE email = $email AND crypto::argon2::compare(password, $password) )
        "#;
        connection.query(sql).await.unwrap().check().unwrap();

        let auth_params = AuthParams {
            email: "john.doe@example.com".to_string(), 
            password: "password123".to_string(),
        };
        let auth_params_json = serde_json::to_value(auth_params).unwrap();

        let wrapped_connection = WrappedConnection {connection};

        // to to directly unwrap to assure that the signup is working
        let _ = sign_up(
            wrapped_connection, 
            auth_params_json, 
            "namespace".to_string(), 
            "database".to_string(), 
            "user_scope".to_string()
        ).await.unwrap();
    }

}
