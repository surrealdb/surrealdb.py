use serde::{Serialize, Deserialize};

// use crate::connection::ConnectionRoutes;
// use crate::operations::OperationRoutes;


#[derive(Debug, PartialEq, Clone, Deserialize, Serialize)]
pub enum Routes {
    placeholder(String)
    // Connection(ConnectionRoutes),
    // Operation(OperationRoutes),
}
