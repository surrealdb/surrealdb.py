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
