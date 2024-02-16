//! Defines the core functions for creating records. These functions should not be called directly
//! from the Python API but rather from the TCP connection in the runtime module. In this
//! module we can do the following:
//! 
//! * Create a record in the database
use serde_json::value::Value;
use surrealdb::opt::Resource;
use surrealdb::sql::Range;
use crate::connection::interface::WrappedConnection;


/// Creates a record in the database.
/// 
/// # Arguments
/// * `connection` - The connection performing the operation on the database
/// * `table_name` - The name of the table to create the record in
/// 
/// # Returns
/// * `Ok(())` - The record was created successfully
pub async fn create(connection: WrappedConnection, table_name: String, data: Value) -> Result<String, String> {
    let resource = Resource::from(table_name.clone());
    let outcome = connection.connection.create(resource).content(data).await.map_err(|e| e.to_string())?;
    let outcome_string = outcome.into_json().to_string();
    Ok(outcome_string)
}


/// Delete all records, or a specific record
///
/// # Arguments
/// * `connection_id` - The connection performing the operation on the database
/// * `resource` - The resource to delete (can be a table or a range)
/// 
/// # Returns
/// 
pub async fn delete(connection: WrappedConnection, resource: String) -> Result<String, String> {
    let response = match resource.parse::<Range>() {
        Ok(range) => {
            connection.connection.delete(Resource::from(range.tb)).range((range.beg, range.end))
                                 .await.map_err(|e| e.to_string())?
        }
        Err(_) => connection.connection.delete(Resource::from(resource))
                                       .await.map_err(|e| e.to_string())?
    };
    Ok(response.into_json().to_string())
}


#[cfg(test)]
mod tests {

    use super::*;
    use crate::operations::query::core::query;
    use crate::connection::core::make_connection;
	use tokio::runtime::Runtime;
    use serde_json::{from_str, Value};


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


    async fn prime_database(connection: WrappedConnection) {
        query(connection.clone(), "CREATE user:1 SET name = 'Tobie', age = 1;".to_string(), None).await.unwrap();
        query(connection.clone(), "CREATE user:2 SET name = 'Jaime', age = 1;".to_string(), None).await.unwrap();
        query(connection.clone(), "CREATE user:3 SET name = 'Dave', age = 2;".to_string(), None).await.unwrap();
        query(connection.clone(), "CREATE user:4 SET name = 'Tom', age = 2;".to_string(), None).await.unwrap();
    }


    #[test]
    fn test_create() {
        let runtime = Runtime::new().unwrap();
        let json_value: Value = generate_json("John Doe", 43);

        let outcome = runtime.block_on(async {
            let connection = make_connection("memory".to_string()).await.unwrap();
			connection.connection.use_ns("test_namespace").await.unwrap();
			connection.connection.use_db("test_database").await.unwrap();
            create(connection.clone(), "user".to_string(), json_value).await
        });

        let outcome: Value = from_str(outcome.unwrap().as_str()).unwrap();
        assert_eq!(outcome.clone()["name"], "John Doe");
        assert_eq!(outcome["age"], 43);
    }

    #[test]
    fn test_create_multiple() {
        let runtime = Runtime::new().unwrap();
        let json_value: Value = generate_json("John Doe", 43);

        let outcome = runtime.block_on(async {
            let connection = make_connection("memory".to_string()).await.unwrap();
			connection.connection.use_ns("test_namespace").await.unwrap();
			connection.connection.use_db("test_database").await.unwrap();
            let _ = create(connection.clone(), "user".to_string(), json_value.clone()).await;
            let _ = create(connection.clone(), "user".to_string(), json_value).await;
            query(connection.clone(), "SELECT * FROM user;".to_string(), None).await.unwrap()
        });
        let outcome: Value = from_str(&outcome).unwrap();
        assert_eq!(outcome[0].as_array().unwrap().len(), 2);
    }

    #[test]
    fn test_all_records() {
        let runtime = Runtime::new().unwrap();

        let outcome = runtime.block_on(async {
            let connection = make_connection("memory".to_string()).await.unwrap();
			connection.connection.use_ns("test_namespace").await.unwrap();
			connection.connection.use_db("test_database").await.unwrap();
            prime_database(connection.clone()).await;

            let outcome: Value = from_str(delete(connection.clone(), "user".to_string()).await.unwrap().as_str()).unwrap();
            assert_eq!(outcome.as_array().unwrap().len(), 4);
            query(connection.clone(), "SELECT * FROM user;".to_string(), None).await.unwrap()
        });
        let outcome: Value = from_str(&outcome).unwrap();
        assert_eq!(outcome[0].as_array().unwrap().len(), 0);
    }

    #[test]
    fn test_range_of_records() {
        let runtime = Runtime::new().unwrap();

        let outcome = runtime.block_on(async {
            let connection = make_connection("memory".to_string()).await.unwrap();
			connection.connection.use_ns("test_namespace").await.unwrap();
			connection.connection.use_db("test_database").await.unwrap();
            prime_database(connection.clone()).await;

            let outcome: Value = from_str(delete(connection.clone(), "user:2..4".to_string()).await.unwrap().as_str()).unwrap();
            assert_eq!(outcome.as_array().unwrap().len(), 2);
            query(connection.clone(), "SELECT * FROM user;".to_string(), None).await.unwrap()
        });

        let outcome: Value = from_str(&outcome).unwrap();
        assert_eq!(outcome[0].as_array().unwrap().len(), 2);
        assert_eq!(outcome[0].as_array().unwrap()[0]["name"], "Tobie");
        assert_eq!(outcome[0].as_array().unwrap()[1]["name"], "Tom");
    }

    #[test]
    fn test_range_specific_record() {
        let runtime = Runtime::new().unwrap();

        let outcome = runtime.block_on(async {
            let connection = make_connection("memory".to_string()).await.unwrap();
			connection.connection.use_ns("test_namespace").await.unwrap();
			connection.connection.use_db("test_database").await.unwrap();
            prime_database(connection.clone()).await;

            let outcome: Value = from_str(delete(connection.clone(), "user:2".to_string()).await.unwrap().as_str()).unwrap();
            assert_eq!(outcome["name"], "Jaime");
            assert_eq!(outcome["age"], 1);
            assert_eq!(outcome["id"], "user:2");
            query(connection.clone(), "SELECT * FROM user;".to_string(), None).await.unwrap()
        });

        let outcome: Value = from_str(&outcome).unwrap();
        assert_eq!(outcome[0].as_array().unwrap().len(), 3);
    }

}
