use serde_json::value::Value;
use surrealdb::sql::Range;
use surrealdb::opt::Resource;
use crate::connection::interface::WrappedConnection;


/// Performs an update on the database for a particular resource.
/// 
/// # Arguments
/// * `connection` - The connection to perform the update with
/// * `resource` - The resource to update (can be a table or a range)
/// * `data` - The data to update the resource with
/// 
/// # Returns
/// * `Ok(Value)` - The result of the update
pub async fn update(connection: WrappedConnection, resource: String, data: Value) -> Result<Value, String> {
    let update = match resource.parse::<Range>() {
        Ok(range) => connection.connection.update(Resource::from(range.tb)).range((range.beg, range.end)),
        Err(_) => connection.connection.update(Resource::from(resource)),
    };

    let outcome = match data {
        Value::Object(_) => update.content(data).await,
        _ => update.await,
    }.map_err(|e| e.to_string())?;
    Ok(outcome.into_json())
}


pub async fn merge(connection: WrappedConnection, resource: String, data: Value) -> Result<Value, String> {
    let update = match resource.parse::<Range>() {
        Ok(range) => connection.connection.update(Resource::from(range.tb)).range((range.beg, range.end)),
        Err(_) => connection.connection.update(Resource::from(resource)),
    };
    let response = update.merge(data).await.map_err(|e| e.to_string())?;
    Ok(response.into_json())
}

// /// Merge records in a table with specified data
// ///
// /// ```js
// /// // Merge all records in a table with specified data.
// /// const person = await db.merge('person', {
// ///     marketing: true
// /// });
// ///
// /// // Merge a range of records with the specified data.
// /// const person = await db.merge('person:jane..john', {
// ///     marketing: true
// /// });
// ///
// /// // Merge the current document / record data with the specified data.
// /// const person = await db.merge('person:tobie', {
// ///     marketing: true
// /// });
// /// ```
// pub async fn merge(&self, resource: String, data: JsValue) -> Result<JsValue, Error> {
//     let update = match resource.parse::<Range>() {
//         Ok(range) => self.db.update(Resource::from(range.tb)).range((range.beg, range.end)),
//         Err(_) => self.db.update(Resource::from(resource)),
//     };
//     let data: Json = from_value(data)?;
//     let response = update.merge(data).await?;
//     Ok(to_value(&response.into_json())?)
// }


#[cfg(test)]
mod tests {

    use super::*;
    use crate::operations::query::core::query;
    use crate::connection::core::make_connection;
	use tokio::runtime::Runtime;
    use serde_json::from_str;


    async fn prime_database(connection: WrappedConnection) {
        query(connection.clone(), "CREATE user:1 SET name = 'Tobie', age = 1;".to_string(), None).await.unwrap();
        query(connection.clone(), "CREATE user:2 SET name = 'Jaime', age = 1;".to_string(), None).await.unwrap();
        query(connection.clone(), "CREATE user:3 SET name = 'Dave', age = 2;".to_string(), None).await.unwrap();
        query(connection.clone(), "CREATE user:4 SET name = 'Tom', age = 2;".to_string(), None).await.unwrap();
    }

    async fn prime_merge_database(connection: WrappedConnection) {
        query(connection.clone(), "CREATE user:1 SET age = 1, name = {first: 'Tobie'};".to_string(), None).await.unwrap();
        query(connection.clone(), "CREATE user:2 SET age = 1, name = {first: 'Jaime'};".to_string(), None).await.unwrap();
        query(connection.clone(), "CREATE user:3 SET age = 2, name = {first: 'Dave'};".to_string(), None).await.unwrap();
        query(connection.clone(), "CREATE user:4 SET age = 2, name = {first: 'Tom'};".to_string(), None).await.unwrap();
    }

    fn generate_json() -> Value {
        let json_string = r#"
            {
                "name": "John Doe"
            } 
        "#;
        let json_value: Value = from_str(json_string).unwrap();
        json_value
    }

    fn generate_merge_json() -> Value {
        let json_string = r#"
            {
                "age": 2,
                "name": {"last": "Doe"}
            } 
        "#;
        let json_value: Value = from_str(json_string).unwrap();
        json_value
    }

    #[test]
    fn test_replace_all_records() {
        let runtime = Runtime::new().unwrap();
        let json_value = generate_json();

        let outcome = runtime.block_on(async {
            let connection = make_connection("memory".to_string()).await.unwrap();
			connection.connection.use_ns("test_namespace").await.unwrap();
			connection.connection.use_db("test_database").await.unwrap();
            prime_database(connection.clone()).await;
            update(connection.clone(), "user".to_string(), json_value).await.unwrap()
        });

        assert_eq!(outcome.as_array().unwrap().len(), 4);
        assert_eq!(outcome[0]["name"], "John Doe");
		assert_eq!(outcome[1]["name"], "John Doe");
		assert_eq!(outcome[2]["name"], "John Doe");
        assert_eq!(outcome[3]["name"], "John Doe");
    }

    #[test]
    fn test_replace_range_of_records() {
        let runtime = Runtime::new().unwrap();
        let json_value = generate_json();

        let outcome = runtime.block_on(async {
            let connection = make_connection("memory".to_string()).await.unwrap();
			connection.connection.use_ns("test_namespace").await.unwrap();
			connection.connection.use_db("test_database").await.unwrap();
            prime_database(connection.clone()).await;
            let _ = update(connection.clone(), "user:2..4".to_string(), json_value).await.unwrap();
            query(connection.clone(), "SELECT * FROM user;".to_string(), None).await.unwrap()
        });

        assert_eq!(outcome[0].as_array().unwrap().len(), 4);
        assert_eq!(outcome[0].as_array().unwrap()[0]["name"], "Tobie");
		assert_eq!(outcome[0].as_array().unwrap()[1]["name"], "John Doe");
		assert_eq!(outcome[0].as_array().unwrap()[2]["name"], "John Doe");
        assert_eq!(outcome[0].as_array().unwrap()[3]["name"], "Tom");
    }

    #[test]
    fn test_indivudal_record() {
        let runtime = Runtime::new().unwrap();
        let json_value = generate_json();

        let outcome = runtime.block_on(async {
            let connection = make_connection("memory".to_string()).await.unwrap();
			connection.connection.use_ns("test_namespace").await.unwrap();
			connection.connection.use_db("test_database").await.unwrap();
            prime_database(connection.clone()).await;
            let _ = update(connection.clone(), "user:2".to_string(), json_value).await.unwrap();
            query(connection.clone(), "SELECT * FROM user;".to_string(), None).await.unwrap()
        });

        assert_eq!(outcome[0].as_array().unwrap().len(), 4);
        assert_eq!(outcome[0].as_array().unwrap()[0]["name"], "Tobie");
		assert_eq!(outcome[0].as_array().unwrap()[1]["name"], "John Doe");
		assert_eq!(outcome[0].as_array().unwrap()[2]["name"], "Dave");
        assert_eq!(outcome[0].as_array().unwrap()[3]["name"], "Tom");
    }


    #[test]
    fn test_merge_records_in_a_tables() {
        let runtime = Runtime::new().unwrap();
        let json_value = generate_merge_json();

        let outcome = runtime.block_on(async {
            let connection = make_connection("memory".to_string()).await.unwrap();
			connection.connection.use_ns("test_namespace").await.unwrap();
			connection.connection.use_db("test_database").await.unwrap();
            prime_merge_database(connection.clone()).await;
            merge(connection.clone(), "user".to_string(), json_value).await.unwrap()
        });

        for i in outcome.as_array().unwrap() {
            println!("{:?}", i);
            assert_eq!(i["name"]["last"], "Doe".to_string());
        }
    }

}



// /// Merge records in a table with specified data
// ///
// /// ```js
// /// // Merge all records in a table with specified data.
// /// const person = await db.merge('person', {
// ///     marketing: true
// /// });
// ///
// /// // Merge a range of records with the specified data.
// /// const person = await db.merge('person:jane..john', {
// ///     marketing: true
// /// });
// ///
// /// // Merge the current document / record data with the specified data.
// /// const person = await db.merge('person:tobie', {
// ///     marketing: true
// /// });
// /// ```