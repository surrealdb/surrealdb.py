use serde_json::value::Value;
use surrealdb::sql::Range;
use surrealdb::opt::Resource;
use crate::connection::interface::WrappedConnection;




pub async fn update(connection: WrappedConnection, resource: String, data: Value) -> Result<Value, String> {
    // let resource = Resource::from(resource.clone());
    let update = match resource.parse::<Range>() {
        Ok(range) => connection.connection.update(Resource::from(range.tb)).range((range.beg, range.end)),
        Err(_) => connection.connection.update(Resource::from(resource)),
    };
    let response = update.content(data).await.map_err(|e| e.to_string())?;
    Ok(response.into_json())
}


pub async fn merge(connection: WrappedConnection, resource: String, data: Value) -> Result<Value, String> {
    let update = match resource.parse::<Range>() {
        Ok(range) => connection.connection.update(Resource::from(range.tb)).range((range.beg, range.end)),
        Err(_) => connection.connection.update(Resource::from(resource)),
    };
    let response = update.merge(data).await.map_err(|e| e.to_string())?;
    Ok(response.into_json())
}


// pub async fn patch(&self, resource: String, data: JsValue) -> Result<JsValue, Error> {
//     // Prepare the update request
//     let update = match resource.parse::<Range>() {
//         Ok(range) => self.db.update(Resource::from(range.tb)).range((range.beg, range.end)),
//         Err(_) => self.db.update(Resource::from(resource)),
//     };
//     let mut patches: VecDeque<Patch> = from_value(data)?;
//     // Extract the first patch
//     let mut patch = match patches.pop_front() {
//         // Setup the correct update type using the first patch
//         Some(p) => update.patch(match p {
//             Patch::Add {
//                 path,
//                 value,
//             } => PatchOp::add(&path, value),
//             Patch::Remove {
//                 path,
//             } => PatchOp::remove(&path),
//             Patch::Replace {
//                 path,
//                 value,
//             } => PatchOp::replace(&path, value),
//             Patch::Change {
//                 path,
//                 diff,
//             } => PatchOp::change(&path, diff),
//         }),
//         None => {
//             return Ok(to_value(&update.await?.into_json())?);
//         }
//     };
//     // Loop through the rest of the patches and append them
//     for p in patches {
//         patch = patch.patch(match p {
//             Patch::Add {
//                 path,
//                 value,
//             } => PatchOp::add(&path, value),
//             Patch::Remove {
//                 path,
//             } => PatchOp::remove(&path),
//             Patch::Replace {
//                 path,
//                 value,
//             } => PatchOp::replace(&path, value),
//             Patch::Change {
//                 path,
//                 diff,
//             } => PatchOp::change(&path, diff),
//         });
//     }
//     // Execute the update statement
//     let response = patch.await?;
//     Ok(to_value(&response.into_json())?)
// }