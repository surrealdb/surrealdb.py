use std::collections::BTreeMap;
use std::error;
use std::sync::RwLock;
use std::time::Duration;
use pyo3::pyclass;
use surrealdb;
use surrealdb::dbs::Session;
use surrealdb::kvs::Datastore;
use surrealdb::rpc::{Data, RpcContext};
use surrealdb::rpc::format::cbor;
use surrealdb::rpc::method::Method;
use surrealdb::sql;

#[derive(Debug)]
pub enum AdapterError {
    RuntimeInitFailedErr,
    ConnectionInitFailedErr,
}

struct SurrealRpc {
    kvs: Datastore,
    sess: Session,
    vars: BTreeMap<String, sql::Value>,
}

#[pyclass]
pub struct Adapter {
    rpc: RwLock<SurrealRpc>,
}

pub struct AdapterConfig {
    pub strict: bool,
    pub query_timeout: Option<Duration>,
    pub transaction_timeout: Option<Duration>,
}


impl RpcContext for SurrealRpc {
    fn kvs(&self) -> &Datastore {
        &self.kvs
    }

    fn session(&self) -> &Session {
        &self.sess
    }

    fn session_mut(&mut self) -> &mut Session {
        &mut self.sess
    }

    fn vars(&self) -> &std::collections::BTreeMap<String, sql::Value> {
        &self.vars
    }

    fn vars_mut(&mut self) -> &mut std::collections::BTreeMap<String, sql::Value> {
        &mut self.vars
    }

    fn version_data(&self) -> Data {
        let ver_str = surrealdb::env::VERSION.to_string();
        ver_str.into()
    }

    const LQ_SUPPORT: bool = true;
    async fn handle_live(&self, _lqid: &uuid::Uuid) {}
    async fn handle_kill(&self, _lqid: &uuid::Uuid) {}
}

pub async fn make_connection(address: &str, adapter_config: AdapterConfig) -> Result<Adapter, Box<dyn error::Error>> {
    let kvs = match Datastore::new(address).await {
        Ok(kvs) => {
            if let Err(error) = kvs.check_version().await {
                return Err(error.into())
            };
            if let Err(error) = kvs.bootstrap().await {
                return Err(error.into())
            }
            kvs
        }
        Err(error) => {
            return Err(error.into());
        }
    };

    let kvs = kvs
        .with_notifications()
        .with_strict_mode(adapter_config.strict)
        .with_query_timeout(adapter_config.query_timeout)
        .with_transaction_timeout(adapter_config.transaction_timeout);

    let rpc = SurrealRpc {
        kvs,
        sess: Session::default().with_rt(true),
        vars: BTreeMap::default(),
    };

    Ok(Adapter { rpc: RwLock::new(rpc) })
}

pub async fn execute(adapter: &Adapter, request_data: Vec<u8>) -> Result<Vec<u8>, Box<dyn error::Error>> {
    let in_data = cbor::req(request_data)?;

    let method = Method::parse(in_data.method);
    let res = match method.needs_mutability() {
        true => {
            adapter.rpc
                .read().unwrap()
                .execute_immutable(method, in_data.params)
                .await
        }
        false => {
            adapter.rpc
                .write().unwrap()
                .execute_mutable(method, in_data.params)
                .await
        }
    }?;

    let out = cbor::res(res)?;
    Ok(out)
}


#[cfg(test)]
mod tests {
    use std::time::Duration;
    use crate::connection::{make_connection, AdapterConfig};

    #[test]
    fn test_get_connection() {
        let con = make_connection("memory", AdapterConfig{
            strict: true,
            query_timeout: Option::from(Duration::new(10, 0)),
            transaction_timeout: Option::from(Duration::new(10, 0))
        }).unwrap();
    }
}