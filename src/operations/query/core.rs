//! Defines the core functions for making queries. These functions should not be called directly
//! from the Python API but rather from the TCP connection in the runtime module. In this
//! module we can do the following:
//! 
//! * Perform a query on the database
use serde_json::value::Value;
use surrealdb::opt::Resource;
use crate::connection::state::{
    WrappedConnection,
    get_components,
    CONNECTION_POOL
};


	// /// Run a SurrealQL query against the database
	// ///
	// /// ```js
	// /// // Run a query without bindings
	// /// const people = await db.query('SELECT * FROM person');
	// ///
	// /// // Run a query with bindings
	// /// const people = await db.query('SELECT * FROM type::table($table)', { table: 'person' });
	// /// ```
	// pub async fn query(&self, sql: String, bindings: JsValue) -> Result<JsValue, Error> {
	// 	let bindings: Json = from_value(bindings)?;
	// 	let mut response = match bindings.is_null() {
	// 		true => self.db.query(sql).await?,
	// 		false => self.db.query(sql).bind(bindings).await?,
	// 	};
	// 	let num_statements = response.num_statements();
	// 	let response = if num_statements > 1 {
	// 		let mut output = Vec::<Value>::with_capacity(num_statements);
	// 		for index in 0..num_statements {
	// 			output.push(response.take(index)?);
	// 		}
	// 		Value::from(output)
	// 	} else {
	// 		response.take(0)?
	// 	};
	// 	Ok(to_value(&response.into_json())?)
	// }

pub async fn query(connection_id: String, sql: String, bindings: Option<Value>) -> Result<Value, String> {
    let (raw_index, connection_id) = get_components(connection_id)?;
    let mut connection_pool = CONNECTION_POOL[raw_index].lock().await;
    let connection = match connection_pool.get_mut(&connection_id) {
        Some(connection) => connection,
        None => return Err("connection does not exist".to_string()),
    };

    Err("not implemented".to_string())
    // let resource = Resource::from(sql.clone());

    // let response = match connection {
    //     WrappedConnection::WS(ws_connection) => {
    //         ws_connection.query(resource).content(bindings).await.map_err(|e| e.to_string())?
    //     },
    //     WrappedConnection::HTTP(http_connection) => {
    //         http_connection.query(resource).content(bindings).await.map_err(|e| e.to_string())?
    //     },
    //     _ => return Err("connection is not a valid type".to_string()),
    // };
    // Ok(response.into_json())
}
