use serde_json::value::Value;
use crate::connection::state::{
    WrappedConnection
};
use surrealdb::opt::Resource;
use tokio::sync::mpsc::Sender;
use crate::connection::state::TrackingMessage;
use crate::connection::state::get_connection;


pub async fn create(connection_id: String, table_name: String, data: Value, tx: Sender<TrackingMessage>) -> Result<(), String> {
    let connection = get_connection(connection_id.clone(), tx).await;
    println!("\n\n\nconnection: {:?}\n\n\n", connection);
    println!("\n\n\ntable_name: {:?}\n\n\n", table_name);
    println!("\n\n\ndata: {:?}\n\n\n", data);
    if connection.is_none() {
        return Err(format!("Connection {} does not exist", connection_id))
    }

    let resource = Resource::from(table_name.clone());

    match connection.unwrap() {
        WrappedConnection::WS(ws_connection) => {
                ws_connection.create(resource).content(data).await.map_err(|e| e.to_string())?;
        },
        WrappedConnection::HTTP(http_connection) => {
            http_connection.create(resource).content(data).await.map_err(|e| e.to_string())?;
        },
    }
    Ok(())
}
