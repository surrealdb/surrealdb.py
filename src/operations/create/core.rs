use serde_json::value::Value;
use crate::connection::state::{
    WrappedConnection
};
use surrealdb::opt::Resource;
use tokio::sync::mpsc::Sender;
use crate::connection::state::ConnectionMessage;
use crate::connection::state::{get_connection, return_connection};


pub async fn create(connection_id: String, table_name: String, data: Value, tx: Sender<ConnectionMessage>) -> Result<(), String> {
    let mut connection = get_connection(connection_id.clone(), tx).await?;
    println!("\n\n\nconnection: {:?}\n\n\n", connection);
    println!("\n\n\ntable_name: {:?}\n\n\n", table_name);
    println!("\n\n\ndata: {:?}\n\n\n", data);

    let resource = Resource::from(table_name.clone());

    println!("\n\n\nresource: {:?}\n\n\n", resource);

    let used_connection: WrappedConnection;
    match connection.value.unwrap() {
        WrappedConnection::WS(ws_connection) => {
                ws_connection.create(resource).content(data).await.map_err(|e| e.to_string())?;
                println!("\n\n\nweb socket done\n\n\n");
                used_connection = WrappedConnection::WS(ws_connection);
        },
        WrappedConnection::HTTP(http_connection) => {
            http_connection.create(resource).content(data).await.map_err(|e| e.to_string())?;
            println!("\n\n\nHTTP done\n\n\n");
            used_connection = WrappedConnection::HTTP(http_connection);
        },
    }   
    connection.value = Some(used_connection);
    return_connection(connection).await?;
    Ok(())
}
