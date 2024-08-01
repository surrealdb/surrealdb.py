//! Defines the functions that perform update operations on the database.
use serde_json::value::Value;
use surrealdb::sql::Range;
use surrealdb::opt::Resource;
use surrealdb::opt::PatchOp;
use crate::connection::interface::WrappedConnection;
use serde::Deserialize;
use std::collections::VecDeque;
use serde_json::from_str;
use std::fmt;

#[derive(Clone, PartialEq)]
pub struct Diff {
    pub operation: i32,
    pub text: String,
}

impl Diff {
    /// A new diff diff object created.
    pub fn new(operation: i32, text: String) -> Diff {
        Diff { operation, text }
    }
}

impl fmt::Debug for Diff {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "\n  {{ {}: {} }}", self.operation, self.text)
    }
}


/// Performs an update on the database for a particular resource.
/// 
/// # Arguments
/// * `connection` - The connection to perform the update with
/// * `resource` - The resource to update (can be a table or a range)
/// * `data` - The data to update the resource with
/// 
/// # Returns
/// * `Ok(Value)` - The result of the update
pub async fn update(connection: WrappedConnection, resource: String, data: Value) -> Result<String, String> {
    let update = match resource.parse::<Range>() {
        Ok(range) => connection.connection.update(Resource::from(range.tb)).range((range.beg, range.end)),
        Err(_) => connection.connection.update(Resource::from(resource)),
    };
    let outcome = match data {
        Value::Object(_) => update.content(data).await,
        _ => update.await,
    }.map_err(|e| e.to_string())?;
    Ok(outcome.into_json().to_string())
}


/// Performs a merge on the database for a particular resource.
/// 
/// # Arguments
/// * `connection` - The connection to perform the merge with
/// * `resource` - The resource to merge (can be a table or a range)
/// 
/// # Returns
/// * `Ok(Value)` - The result of the merge
pub async fn merge(connection: WrappedConnection, resource: String, data: Value) -> Result<String, String> {
    let update = match resource.parse::<Range>() {
        Ok(range) => connection.connection.update(Resource::from(range.tb)).range((range.beg, range.end)),
        Err(_) => connection.connection.update(Resource::from(resource)),
    };
    let response = update.merge(data).await.map_err(|e| e.to_string())?;
    Ok(response.into_json().to_string())
}


/// Performs a patch on the database for a particular resource.
/// 
/// # Arguments
/// * `connection` - The connection to perform the patch with
/// * `resource` - The resource to patch (can be a table or a range)
/// * `data` - The data to patch the resource with
/// 
/// # Data Examples
/// For instance, if you wanted to update the last name of the user for all users in the `users` table,
/// you would do the following:
/// ```json
/// [{
///    "op": "replace",
///    "path": "/users/last_name",
///    "value": "Smith"
/// }]
/// ```
/// # Returns
/// an array of the results of the patch for each row that was updated with the patch operation.
pub async fn patch(connection: WrappedConnection, resource: String, data: Value) -> Result<String, String> {
    let patch = match resource.parse::<Range>() {
        Ok(range) => connection.connection.update(Resource::from(range.tb)).range((range.beg, range.end)),
        Err(_) => connection.connection.update(Resource::from(resource))
    };
    let data_str = serde_json::to_string(&data).map_err(|e| e.to_string())?;

    let mut patches: VecDeque<Patch> = from_str(&data_str).map_err(|e| e.to_string())?;
    let mut patch = match patches.pop_front() {
        Some(p) => patch.patch(match p {
            Patch::Add {
                path,
                value,
            } => PatchOp::add(&path, value),
            Patch::Remove {
                path,
            } => PatchOp::remove(&path),
            Patch::Replace {
                path,
                value,
            } => PatchOp::replace(&path, value),
            // Patch::Change {
            //     path,
            //     diff,
            // } => PatchOp::change(&path, diff),
        }),
        None => {
            let response = patch.await.map_err(|e| e.to_string())?;
            return Ok(response.into_json().to_string())
        }
    };
    for p in patches {
        patch = patch.patch(match p {
            Patch::Add {
                path,
                value,
            } => PatchOp::add(&path, value),
            Patch::Remove {
                path,
            } => PatchOp::remove(&path),
            Patch::Replace {
                path,
                value,
            } => PatchOp::replace(&path, value),
            // Patch::Change {
            //     path,
            //     diff,
            // } => PatchOp::change(&path, diff),
        });
    }
    let response = patch.await.map_err(|e| e.to_string())?;
    Ok(response.into_json().to_string())
}


#[derive(Deserialize)]
#[serde(remote = "Diff")]
struct DiffDef {
	operation: i32,
	text: String,
}

#[derive(Deserialize)]
#[serde(tag = "op")]
#[serde(rename_all = "lowercase")]
pub enum Patch {
	Add {
		path: String,
		value: Value,
	},
	Remove {
		path: String,
	},
	Replace {
		path: String,
		value: Value,
	},
	// Change {
	// 	path: String,
	// 	// #[serde(with = "DiffDef")]
	// 	diff: Diff,
	// },
}


#[cfg(test)]
mod tests {

    use super::*;
    use crate::operations::query::core::query;
    use crate::connection::core::make_connection;
	use tokio::runtime::Runtime;
    use serde_json::{from_str, Value};


    async fn prime_database(connection: WrappedConnection) {
        query(connection.clone(), "CREATE user:1 SET name = 'Tobie', age = 1;".to_string(), None).await.unwrap();
        query(connection.clone(), "CREATE user:2 SET name = 'Jaime', age = 1;".to_string(), None).await.unwrap();
        query(connection.clone(), "CREATE user:3 SET name = 'Dave', age = 2;".to_string(), None).await.unwrap();
        query(connection.clone(), "CREATE user:4 SET name = 'Tom', age = 2;".to_string(), None).await.unwrap();
    }

    async fn prime_merge_database(connection: WrappedConnection) {
        query(connection.clone(), "CREATE user:1 SET age = 1, name = {first: 'Tobie', last: 'one'};".to_string(), None).await.unwrap();
        query(connection.clone(), "CREATE user:2 SET age = 1, name = {first: 'Jaime', last: 'two'};".to_string(), None).await.unwrap();
        query(connection.clone(), "CREATE user:3 SET age = 2, name = {first: 'Dave', last: 'three'};".to_string(), None).await.unwrap();
        query(connection.clone(), "CREATE user:4 SET age = 2, name = {first: 'Tom', last: 'four'};".to_string(), None).await.unwrap();
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

        let outcome: Value = from_str(&outcome).unwrap();
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

        let outcome: Value = from_str(&outcome).unwrap();
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

        let outcome: Value = from_str(&outcome).unwrap();
        assert_eq!(outcome[0].as_array().unwrap().len(), 4);
        assert_eq!(outcome[0].as_array().unwrap()[0]["name"], "Tobie");
		assert_eq!(outcome[0].as_array().unwrap()[1]["name"], "John Doe");
		assert_eq!(outcome[0].as_array().unwrap()[2]["name"], "Dave");
        assert_eq!(outcome[0].as_array().unwrap()[3]["name"], "Tom");
    }


    #[test]
    fn test_merge_all_records() {
        let runtime = Runtime::new().unwrap();
        let json_value = generate_merge_json();

        let outcome = runtime.block_on(async {
            let connection = make_connection("memory".to_string()).await.unwrap();
			connection.connection.use_ns("test_namespace").await.unwrap();
			connection.connection.use_db("test_database").await.unwrap();
            prime_merge_database(connection.clone()).await;
            merge(connection.clone(), "user".to_string(), json_value).await.unwrap()
        });

        let outcome: Value = from_str(&outcome).unwrap();
        assert_eq!(outcome[0]["name"]["last"], "Doe".to_string());
        assert_eq!(outcome[1]["name"]["last"], "Doe".to_string());
        assert_eq!(outcome[2]["name"]["last"], "Doe".to_string());
        assert_eq!(outcome[3]["name"]["last"], "Doe".to_string());
        assert_eq!(outcome.as_array().unwrap().len(), 4);
    }


    #[test]
    fn test_merge_some() {
        let runtime = Runtime::new().unwrap();
        let json_value = generate_merge_json();

        let outcome = runtime.block_on(async {
            let connection = make_connection("memory".to_string()).await.unwrap();
			connection.connection.use_ns("test_namespace").await.unwrap();
			connection.connection.use_db("test_database").await.unwrap();
            prime_merge_database(connection.clone()).await;
            let _ = merge(connection.clone(), "user:2..4".to_string(), json_value).await.unwrap();
            query(connection.clone(), "SELECT * FROM user;".to_string(), None).await.unwrap()
        });

        let outcome: Value = from_str(&outcome).unwrap();
        assert_eq!(outcome[0].as_array().unwrap()[0]["name"]["last"], "one".to_string());
        assert_eq!(outcome[0].as_array().unwrap()[1]["name"]["last"], "Doe".to_string());
        assert_eq!(outcome[0].as_array().unwrap()[2]["name"]["last"], "Doe".to_string());
        assert_eq!(outcome[0].as_array().unwrap()[3]["name"]["last"], "four".to_string());
        assert_eq!(outcome[0].as_array().unwrap().len(), 4);
    }

    #[test]
    fn test_merge_specific() {
        let runtime = Runtime::new().unwrap();
        let json_value = generate_merge_json();

        let outcome = runtime.block_on(async {
            let connection = make_connection("memory".to_string()).await.unwrap();
			connection.connection.use_ns("test_namespace").await.unwrap();
			connection.connection.use_db("test_database").await.unwrap();
            prime_merge_database(connection.clone()).await;
            let _ = merge(connection.clone(), "user:2".to_string(), json_value).await.unwrap();
            query(connection.clone(), "SELECT * FROM user;".to_string(), None).await.unwrap()
        });

        let outcome: Value = from_str(&outcome).unwrap();
        assert_eq!(outcome[0].as_array().unwrap()[0]["name"]["last"], "one".to_string());
        assert_eq!(outcome[0].as_array().unwrap()[1]["name"]["last"], "Doe".to_string());
        assert_eq!(outcome[0].as_array().unwrap()[2]["name"]["last"], "three".to_string());
        assert_eq!(outcome[0].as_array().unwrap()[3]["name"]["last"], "four".to_string());
        assert_eq!(outcome[0].as_array().unwrap().len(), 4);
    }


    #[test]
    fn test_patch() {

        let json_string = r#"
            [{
                "op": "replace",
                "path": "/name/last",
                "value": "Doe"
            }]
        "#;
        let json_value: Value = from_str(json_string).unwrap();

        let runtime = Runtime::new().unwrap();

        let outcome = runtime.block_on(async {
            let connection = make_connection("memory".to_string()).await.unwrap();
			connection.connection.use_ns("test_namespace").await.unwrap();
			connection.connection.use_db("test_database").await.unwrap();

            prime_merge_database(connection.clone()).await;
            let outcome = patch(connection.clone(), "user".to_string(), json_value).await.unwrap();
            println!("{:?}", outcome);
            query(connection.clone(), "SELECT * FROM user;".to_string(), None).await.unwrap()
        });

        let outcome: Value = from_str(&outcome).unwrap();
        for i in outcome[0].as_array().unwrap() {
            assert_eq!(i["name"]["last"], "Doe".to_string());
        }
    }

}
