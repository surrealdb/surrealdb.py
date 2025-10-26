use arc_swap::ArcSwap;
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use std::collections::BTreeMap;
use std::sync::Arc;
use surrealdb::dbs::Session;
use surrealdb::kvs::Datastore;
use surrealdb::rpc::format::cbor;
use surrealdb::rpc::{Data, RpcContext, RpcProtocolV1, RpcProtocolV2};
use surrealdb::sql::Value;
use tokio::runtime::Runtime;
use tokio::sync::Semaphore;
use uuid::Uuid;

#[pyclass]
pub struct SyncEmbeddedDB {
    runtime: Runtime,
    inner: SyncEmbeddedDBInner,
}

#[pymethods]
impl SyncEmbeddedDB {
    #[new]
    fn new(url: String) -> PyResult<Self> {
        // Determine endpoint
        let endpoint = if url.starts_with("mem://") {
            "memory".to_string()
        } else if url.starts_with("memory") {
            "memory".to_string()
        } else if url.starts_with("surrealkv://") {
            url
        } else if url.starts_with("file://") {
            url.replace("file://", "surrealkv://").to_string()
        } else {
            return Err(PyErr::new::<PyValueError, _>(format!(
                "Unsupported URL scheme: {url}. Use 'mem://' or 'file://'"
            )));
        };
        // Create the runtime
        let runtime = tokio::runtime::Builder::new_multi_thread()
            .enable_all()
            .build()
            .map_err(|e| {
                PyErr::new::<PyRuntimeError, _>(format!("Failed to create runtime: {e}"))
            })?;
        // Create the Datastore
        let kvs = runtime.block_on(async {
            Datastore::new(&endpoint).await.map_err(|e| {
                PyErr::new::<PyRuntimeError, _>(format!("Failed to create datastore: {e}"))
            })
        })?;
        // Create the default session
        let sess = Session::default().with_rt(true);
        // Return the embedded database
        Ok(SyncEmbeddedDB {
            runtime,
            inner: SyncEmbeddedDBInner {
                kvs: Arc::new(kvs),
                session: ArcSwap::new(Arc::new(sess.into())),
                lock: Arc::new(Semaphore::new(1)),
            },
        })
    }

    fn __enter__<'a>(slf: Bound<'a, Self>) -> PyResult<Bound<'a, Self>> {
        Ok(slf)
    }

    fn __exit__<'a>(
        &self,
        _exc_type: &Bound<'a, PyAny>,
        _exc_value: &Bound<'a, PyAny>,
        _traceback: &Bound<'a, PyAny>,
    ) -> PyResult<()> {
        self.close()
    }

    fn connect(&self) -> PyResult<()> {
        // Already connected in new(), this is a no-op for compatibility
        Ok(())
    }

    fn close(&self) -> PyResult<()> {
        // Datastore cleanup happens on drop, this is a no-op for compatibility
        Ok(())
    }

    fn execute(&self, py: Python, cbor_request: &[u8]) -> PyResult<Py<PyAny>> {
        // Convert the request to a vector
        let data = cbor_request.to_vec();
        // Execute the request synchronously
        let result = self.runtime.block_on(async move {
            // Decode CBOR request
            let req = cbor::req(data).map_err(|e| {
                PyErr::new::<PyValueError, _>(format!("Failed to decode CBOR request: {e}"))
            })?;
            // Extract the request ID
            let rid = req.id.clone().unwrap_or_else(|| Value::None);
            // Execute via RpcContext
            let res = RpcContext::execute(&self.inner, req.version, req.method, req.params)
                .await
                .map_err(|e| PyErr::new::<PyRuntimeError, _>(e.to_string()))?;
            // Convert response to Value
            let value: Value = res.try_into().map_err(|e| {
                PyErr::new::<PyRuntimeError, _>(format!("Failed to convert response: {e}"))
            })?;
            // Build the RPC response
            let mut out = BTreeMap::new();
            out.insert("id".to_string(), rid);
            out.insert("result".to_string(), value);
            // Convert to a SurrealDBValue
            let res = Value::from(out);
            // Encode response to CBOR
            let out = cbor::res(res).map_err(|e| {
                PyErr::new::<PyValueError, _>(format!("Failed to encode CBOR response: {e}"))
            })?;
            // Return the response
            Ok::<Vec<u8>, PyErr>(out)
        })?;
        // Return the response
        Ok(pyo3::types::PyBytes::new(py, &result).into())
    }
}

pub struct SyncEmbeddedDBInner {
    kvs: Arc<Datastore>,
    lock: Arc<Semaphore>,
    session: ArcSwap<Session>,
}

impl RpcContext for SyncEmbeddedDBInner {
    fn kvs(&self) -> &Datastore {
        &self.kvs
    }

    fn lock(&self) -> Arc<Semaphore> {
        self.lock.clone()
    }

    fn session(&self) -> Arc<Session> {
        self.session.load_full()
    }

    fn set_session(&self, session: Arc<Session>) {
        self.session.store(session);
    }

    fn version_data(&self) -> Data {
        Value::Strand(format!("surrealdb-{}", env!("CARGO_PKG_VERSION")).into()).into()
    }

    const LQ_SUPPORT: bool = true;

    fn handle_live(&self, _lqid: &Uuid) -> impl std::future::Future<Output = ()> + Send {
        async { () }
    }

    fn handle_kill(&self, _lqid: &Uuid) -> impl std::future::Future<Output = ()> + Send {
        async { () }
    }
}

impl RpcProtocolV1 for SyncEmbeddedDBInner {}
impl RpcProtocolV2 for SyncEmbeddedDBInner {}
