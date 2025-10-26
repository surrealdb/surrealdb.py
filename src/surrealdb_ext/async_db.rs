use arc_swap::ArcSwap;
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3_async_runtimes::tokio::future_into_py;
use std::collections::BTreeMap;
use std::sync::Arc;
use surrealdb::dbs::Session;
use surrealdb::kvs::Datastore;
use surrealdb::rpc::format::cbor;
use surrealdb::rpc::{Data, RpcContext, RpcProtocolV1, RpcProtocolV2};
use surrealdb::sql::Value;
use tokio::sync::Semaphore;
use uuid::Uuid;

#[pyclass]
pub struct AsyncEmbeddedDB {
    inner: Arc<AsyncEmbeddedDBInner>,
}

#[pymethods]
impl AsyncEmbeddedDB {
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
        Ok(AsyncEmbeddedDB {
            inner: Arc::new(AsyncEmbeddedDBInner {
                kvs: Arc::new(kvs),
                session: ArcSwap::new(Arc::new(sess.into())),
                lock: Arc::new(Semaphore::new(1)),
            }),
        })
    }

    fn __aenter__<'a>(slf: Bound<'a, Self>) -> PyResult<Bound<'a, Self>> {
        Ok(slf)
    }

    fn __aexit__<'a>(
        slf: Bound<'a, Self>,
        _exc_type: &Bound<'a, PyAny>,
        _exc_value: &Bound<'a, PyAny>,
        _traceback: &Bound<'a, PyAny>,
    ) -> PyResult<Bound<'a, PyAny>> {
        slf.borrow().close(slf.py())
    }

    fn connect<'a>(&self, py: Python<'a>) -> PyResult<Bound<'a, PyAny>> {
        // Already connected in new(), this is a no-op for compatibility
        future_into_py::<_, ()>(py, async move { Ok(()) })
    }

    fn close<'a>(&self, py: Python<'a>) -> PyResult<Bound<'a, PyAny>> {
        // Datastore cleanup happens on drop, this is a no-op for compatibility
        future_into_py::<_, ()>(py, async move { Ok(()) })
    }

    fn execute<'a>(&self, py: Python<'a>, cbor_request: &[u8]) -> PyResult<Bound<'a, PyAny>> {
        // Convert the request to a vector
        let data = cbor_request.to_vec();
        // Clone the inner database
        let inner = self.inner.clone();
        // Execute the request asynchronously
        future_into_py(py, async move {
            // Decode CBOR request
            let req = cbor::req(data).map_err(|e| {
                PyErr::new::<PyValueError, _>(format!("Failed to decode CBOR request: {e}"))
            })?;
            // Extract the request ID
            let rid = req.id.clone().unwrap_or_else(|| Value::None);
            // Execute via RpcContext
            let res = RpcContext::execute(inner.as_ref(), req.version, req.method, req.params)
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
            // Return the response as Vec<u8>
            Ok::<Vec<u8>, PyErr>(out)
        })
    }
}

pub struct AsyncEmbeddedDBInner {
    kvs: Arc<Datastore>,
    lock: Arc<Semaphore>,
    session: ArcSwap<Session>,
}

impl RpcContext for AsyncEmbeddedDBInner {
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

impl RpcProtocolV1 for AsyncEmbeddedDBInner {}
impl RpcProtocolV2 for AsyncEmbeddedDBInner {}
