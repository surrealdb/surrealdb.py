//! Python entry points for the connection module enabling python to perform connection operations.
use pyo3::prelude::*;

use crate::routing::enums::Message;
use crate::routing::handle::Routes;
use crate::runtime::{
    send_message_to_runtime,
    RUNTIME
};

use super::interface::{
    ConnectionRoutes,
    Url,
    ConnectionId,
    BasicMessage,
    SignIn
};

// below is experimental imports
use crate::connection::core::{
    prep_connection_components
};
use crate::connection::state::{
    WrappedConnection,
    ConnectProtocol,
    WrappedConnectionStruct
};
use surrealdb::engine::remote::{
    ws::Ws,
    http::Http,
};
use surrealdb::Surreal;
use surrealdb::opt::auth::Root;


/// Makes a connection to the database in an non-async manner.
/// 
/// # Arguments
/// * `url` - The URL for the connection
/// * `port` - The port for the connection
/// 
/// # Returns
/// * `Ok(String)` - The unique ID for the connection that was just made
#[pyfunction]
pub fn blocking_make_connection(url: String, port: i32) -> Result<String, PyErr> {
    let route = ConnectionRoutes::Create(Message::<Url, ConnectionId>::package_send(Url{url: url}));
    let message = Routes::Connection(route);

    let response_body = send_message_to_runtime(message, port).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string())
    })?;

    let response = match response_body {
        Routes::Connection(message) => message,
        _ => return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Invalid response from listener"))
    };
    let unique_id = match response {
        ConnectionRoutes::Create(message) => {
            message.handle_recieve().map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))?
        },
        _ => return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Invalid response from listener"))
    };
    Ok(unique_id.connection_id)
}


#[pyfunction]
pub fn blocking_make_connection_pass(url: String) -> Result<WrappedConnectionStruct, PyErr> {
    let components = prep_connection_components(url).map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))?;
    let protocol = components.0;
    let address = components.1;
    let database = components.2;
    let namespace = components.3;

    let outcome = RUNTIME.block_on(async move{
        let wrapped_connection: WrappedConnection;
        match protocol {
            ConnectProtocol::WS => {
                let connection = Surreal::new::<Ws>(address).await.map_err(|e| e.to_string()).unwrap();
                connection.use_ns(namespace).use_db(database).await.map_err(|e| e.to_string()).unwrap();
                wrapped_connection = WrappedConnection::WS(connection);
            },
            ConnectProtocol::HTTP => {
                let connection = Surreal::new::<Http>(address).await.map_err(|e| e.to_string()).unwrap();
                connection.use_ns(namespace).use_db(database).await.map_err(|e| e.to_string()).unwrap();
                wrapped_connection = WrappedConnection::HTTP(connection);
            },
        }
        return wrapped_connection
    });
    let wrapped: WrappedConnectionStruct;
    match outcome {
        WrappedConnection::WS(connection) => {
            wrapped = WrappedConnectionStruct{
                web_socket: Some(connection),
                http: None
            };
        },
        WrappedConnection::HTTP(connection) => {
            wrapped = WrappedConnectionStruct{
                http: Some(connection),
                web_socket: None
            };
        },
        _ => return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Invalid response from listener"))
    }
    Ok(wrapped)
}


/// Signs in to a connection.
/// 
/// # Arguments
/// * `connection_id` - The unique ID for the connection to be signed in to
/// * `username` - The username to be used for signing in
/// * `password` - The password to be used for signing in
/// 
/// # Returns
/// * `Ok(())` - If the sign in was successful
#[pyfunction]
pub fn blocking_sign_in_pass(connection: WrappedConnectionStruct, username: String, password: String) -> Result<(), PyErr> {
    let ws_connection = connection.web_socket.unwrap();
    let _ = RUNTIME.block_on(async move{
        ws_connection.signin(Root {
            username: username.as_str(),
            password: password.as_str(),
        }).await.map_err(|e| e.to_string()).unwrap();
    });
    Ok(())
}


/// Closes a connection to the database in an non-async manner.
/// 
/// # Arguments
/// * `connection_id` - The unique ID for the connection to be closed
#[pyfunction]
pub fn blocking_close_connection(connection_id: String, port: i32) -> Result<(), PyErr> {
    let route = ConnectionRoutes::Close(Message::<ConnectionId, BasicMessage>::package_send(ConnectionId{connection_id: connection_id}));
    let message = Routes::Connection(route);

    let response_body = send_message_to_runtime(message, port).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string())
    })?;

    let response = match response_body {
        Routes::Connection(message) => message,
        _ => return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Invalid response from listener"))
    };
    let _ = match response {
        ConnectionRoutes::Close(message) => {
            message.handle_recieve().map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))?
        },
        _ => return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Invalid response from listener"))
    };
    Ok(())
}


/// Checks if a connection is still open.
/// 
/// # Arguments
/// * `connection_id` - The unique ID for the connection to be checked
/// 
/// # Returns
/// * `Ok(bool)` - Whether or not the connection is still open
#[pyfunction]
pub fn blocking_check_connection(connection_id: String, port: i32) -> Result<bool, PyErr> {
    let route = ConnectionRoutes::Check(Message::<ConnectionId, bool>::package_send(ConnectionId{connection_id: connection_id}));
    let message = Routes::Connection(route);

    let response_body = send_message_to_runtime(message, port).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string())
    })?;

    let response = match response_body {
        Routes::Connection(message) => message,
        _ => return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Invalid response from listener"))
    };
    let connection_state = match response {
        ConnectionRoutes::Check(message) => {
            message.handle_recieve().map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))?
        },
        _ => return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Invalid response from listener"))
    };
    Ok(connection_state)
}

/// Signs in to a connection.
/// 
/// # Arguments
/// * `connection_id` - The unique ID for the connection to be signed in to
/// * `username` - The username to be used for signing in
/// * `password` - The password to be used for signing in
/// 
/// # Returns
/// * `Ok(())` - If the sign in was successful
#[pyfunction]
pub fn blocking_sign_in(connection_id: String, username: String, password: String, port: i32) -> Result<(), PyErr> {
    let route = ConnectionRoutes::SignIn(Message::<SignIn, BasicMessage>::package_send(SignIn{
        connection_id, 
        username, 
        password
    }));
    let message = Routes::Connection(route);

    let response_body = send_message_to_runtime(message, port).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string())
    })?;

    let response = match response_body {
        Routes::Connection(message) => message,
        _ => return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Invalid response from listener"))
    };
    let _ = match response {
        ConnectionRoutes::SignIn(message) => {
            message.handle_recieve().map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))?
        },
        _ => return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Invalid response from listener"))
    };
    Ok(())
}
