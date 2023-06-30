//! Defines the core functions for making queries. These functions should not be called directly
//! from the Python API but rather from the TCP connection in the runtime module. In this
//! module we can do the following:
//! 
//! * Perform a query on the database
use serde_json::value::Value;
use crate::connection::interface::WrappedConnection;
use surrealdb::sql::Value as SurrealValue;


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

pub async fn query(connection: WrappedConnection, sql: String, bindings: Option<Value>) -> Result<Value, String> {
	let mut response = match bindings {
		Some(bind) => {connection.connection.query(sql).bind(bind).await},
		None => {connection.connection.query(sql).await}
	}.map_err(|e| e.to_string())?;

	// extract data needed from the Response struct
	let num_statements = response.num_statements();
	let mut output = Vec::<Value>::with_capacity(num_statements);

	// converting SurrealValue items into serde_json::Value items
	for index in 0..num_statements {
		let value: SurrealValue = response.take(index).map_err(|x| x.to_string())?;
		output.push(value.into_json());
	}
	let json_value: Value = Value::Array(output);
	Ok(json_value)
}
