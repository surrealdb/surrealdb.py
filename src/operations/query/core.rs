//! Defines the core functions for making queries. These functions should not be called directly
//! from the Python API but rather from the TCP connection in the runtime module. In this
//! module we can do the following:
//! 
//! * Perform a query on the database
use serde_json::value::Value;
use crate::connection::interface::WrappedConnection;
use surrealdb::sql::Value as SurrealValue;
use surrealdb::opt::Resource;
use surrealdb::sql::Range;


/// Performs a query on the database.
/// 
/// # Arguments
/// * `connection` - The connection to perform the query on
/// * `sql` - The SQL query to perform
/// * `bindings` - The bindings to use for the query
/// 
/// # Returns
/// * `Ok(Value)` - The result of the query
pub async fn query(connection: WrappedConnection, sql: String, bindings: Option<Value>) -> Result<String, String> {
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
	Ok(json_value.to_string())
}

/// Performs a select on the database.
/// 
/// # Arguments
/// * `connection` - The connection to perform the select with
/// * `resource` - The resource to select (can be a table or a range)
/// 
/// # Returns
/// * `Ok(Value)` - The result of the select
pub async fn select(connection: WrappedConnection, resource: String) -> Result<String, String> {
	let response = match resource.parse::<Range>() {
		Ok(range) => {
			connection.connection.select(Resource::from(range.tb)).range((range.beg, range.end))
								 .await.map_err(|e| e.to_string())?
		}
		Err(_) => connection.connection.select(Resource::from(resource))
									   .await.map_err(|e| e.to_string())?
	};
	Ok(response.into_json().to_string())
}


#[cfg(test)]
mod tests {
	use super::*;
	use crate::connection::core::make_connection;
	use tokio::runtime::Runtime;
	use serde_json::{from_str, Value};

	#[test]
	fn test_query() {

		let runtime = Runtime::new().unwrap();

		let outcome = runtime.block_on(async {
			let connection = make_connection("memory".to_string()).await.unwrap();
			connection.connection.use_ns("test_namespace").await.unwrap();
			connection.connection.use_db("test_database").await.unwrap();

			query(connection.clone(), "CREATE user:tobie SET name = 'Tobie';".to_string(), None).await.unwrap();
			query(connection.clone(), "CREATE user:jaime SET name = 'Jaime';".to_string(), None).await.unwrap();

			query(connection, "SELECT * FROM user;".to_string(), None).await.unwrap()
		});

		let outcome: Value = from_str(&outcome).unwrap();
		assert_eq!(outcome[0].as_array().unwrap()[0]["name"], "Jaime");
		assert_eq!(outcome[0].as_array().unwrap()[1]["name"], "Tobie");
	}


	#[test]
	fn test_select_all_users() {
		let runtime = Runtime::new().unwrap();

		let outcome = runtime.block_on(async {
			let connection = make_connection("memory".to_string()).await.unwrap();
			connection.connection.use_ns("test_namespace").await.unwrap();
			connection.connection.use_db("test_database").await.unwrap();

			query(connection.clone(), "CREATE user:1 SET name = 'Tobie';".to_string(), None).await.unwrap();
			query(connection.clone(), "CREATE user:2 SET name = 'Jaime';".to_string(), None).await.unwrap();
			query(connection.clone(), "CREATE user:3 SET name = 'Dave';".to_string(), None).await.unwrap();

			select(connection, "user".to_string()).await.unwrap()
		});

		let outcome: Value = from_str(&outcome).unwrap();
		assert_eq!(outcome.as_array().unwrap().len(), 3);
		assert_eq!(outcome[0]["name"], "Tobie");
		assert_eq!(outcome[1]["name"], "Jaime");
		assert_eq!(outcome[2]["name"], "Dave");
	}

	#[test]
	fn test_select_range_users() {
		let runtime = Runtime::new().unwrap();

		let outcome = runtime.block_on(async {
			let connection = make_connection("memory".to_string()).await.unwrap();
			connection.connection.use_ns("test_namespace").await.unwrap();
			connection.connection.use_db("test_database").await.unwrap();

			query(connection.clone(), "CREATE user:1 SET name = 'Tobie';".to_string(), None).await.unwrap();
			query(connection.clone(), "CREATE user:2 SET name = 'Jaime';".to_string(), None).await.unwrap();
			query(connection.clone(), "CREATE user:3 SET name = 'Dave';".to_string(), None).await.unwrap();
			query(connection.clone(), "CREATE user:4 SET name = 'Tom';".to_string(), None).await.unwrap();

			select(connection, "user:1..4".to_string()).await.unwrap()
		});

		let outcome: Value = from_str(&outcome).unwrap();
		assert_eq!(outcome.as_array().unwrap().len(), 3);
		assert_eq!(outcome[0]["name"], "Tobie");
		assert_eq!(outcome[1]["name"], "Jaime");
		assert_eq!(outcome[2]["name"], "Dave");
	}

	#[test]
	fn test_select_particular_user() {
		let runtime = Runtime::new().unwrap();

		let outcome = runtime.block_on(async {
			let connection = make_connection("memory".to_string()).await.unwrap();
			connection.connection.use_ns("test_namespace").await.unwrap();
			connection.connection.use_db("test_database").await.unwrap();

			query(connection.clone(), "CREATE user:1 SET name = 'Tobie';".to_string(), None).await.unwrap();
			query(connection.clone(), "CREATE user:2 SET name = 'Jaime';".to_string(), None).await.unwrap();
			query(connection.clone(), "CREATE user:3 SET name = 'Dave';".to_string(), None).await.unwrap();
			query(connection.clone(), "CREATE user:4 SET name = 'Tom';".to_string(), None).await.unwrap();

			select(connection, "user:2".to_string()).await.unwrap()
		});

		let outcome: Value = from_str(&outcome).unwrap();
		assert_eq!(outcome["name"], "Jaime");
		assert_eq!(outcome["id"], "user:2");
	}

}
