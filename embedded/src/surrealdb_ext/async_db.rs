use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3_async_runtimes::tokio::future_into_py;
use std::sync::Arc;
use surrealdb_core::dbs::Session;
use surrealdb_core::kvs::Datastore;
use surrealdb_core::rpc::format::cbor;
use surrealdb_core::rpc::{DbResponse, DbResult, RpcProtocol, Request};
use surrealdb_types::{HashMap, Value as PublicValue};
use tokio::sync::RwLock;
use uuid::Uuid;

#[pyclass]
pub struct AsyncEmbeddedDB {
    inner: Arc<AsyncEmbeddedDBInner>,
}

#[pymethods]
impl AsyncEmbeddedDB {
    #[new]
    fn new(url: String) -> PyResult<Self> {
        let endpoint = if url.starts_with("mem://") {
            "memory".to_string()
        } else if url.starts_with("memory") {
            "memory".to_string()
        } else if url.starts_with("surrealkv+versioned://") {
            url
        } else if url.starts_with("surrealkv://") {
            url
        } else if url.starts_with("file://") {
            url.replace("file://", "surrealkv://").to_string()
        } else {
            return Err(PyErr::new::<PyValueError, _>(format!(
                "Unsupported URL scheme: {url}. Use 'mem://', 'memory', 'file://', 'surrealkv://', or 'surrealkv+versioned://'"
            )));
        };
        let runtime = tokio::runtime::Builder::new_multi_thread()
            .enable_all()
            .build()
            .map_err(|e| {
                PyErr::new::<PyRuntimeError, _>(format!("Failed to create runtime: {e}"))
            })?;
        let kvs = runtime.block_on(async {
            Datastore::new(&endpoint).await.map_err(|e| {
                PyErr::new::<PyRuntimeError, _>(format!("Failed to create datastore: {e}"))
            })
        })?;
        let sessions: HashMap<Option<Uuid>, Arc<RwLock<Session>>> = HashMap::new();
        let sess = Session::default().with_rt(false);
        sessions.insert(None, Arc::new(RwLock::new(sess)));
        Ok(AsyncEmbeddedDB {
            inner: Arc::new(AsyncEmbeddedDBInner {
                kvs: Arc::new(kvs),
                sessions,
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
        future_into_py::<_, ()>(py, async move { Ok(()) })
    }

    fn close<'a>(&self, py: Python<'a>) -> PyResult<Bound<'a, PyAny>> {
        future_into_py::<_, ()>(py, async move { Ok(()) })
    }

    fn execute<'a>(&self, py: Python<'a>, cbor_request: &[u8]) -> PyResult<Bound<'a, PyAny>> {
        let data = cbor_request.to_vec();
        let inner = self.inner.clone();
        future_into_py(py, async move {
            let value = cbor::decode(&data).map_err(|e| {
                PyErr::new::<PyValueError, _>(format!("Failed to decode CBOR request: {e}"))
            })?;
            let obj = match value {
                PublicValue::Object(o) => o,
                _ => {
                    return Err(PyErr::new::<PyValueError, _>(
                        "Expected CBOR object for request",
                    ))
                }
            };
            let req = Request::from_object(obj).map_err(|e| {
                PyErr::new::<PyValueError, _>(format!("Failed to parse request: {e}"))
            })?;
            let rid = req.id.clone();
            let session_id = req.session_id.map(Uuid::from);
            let txn = req.txn.map(Uuid::from);
            let response = match RpcProtocol::execute(
                inner.as_ref(),
                txn,
                session_id,
                req.method,
                req.params,
            )
            .await
            {
                Ok(result) => DbResponse::success(rid, session_id, result),
                Err(error) => DbResponse::failure(rid, session_id, error),
            };
            let response_value: PublicValue =
                surrealdb_types::SurrealValue::into_value(response);
            let out = cbor::encode(response_value).map_err(|e| {
                PyErr::new::<PyValueError, _>(format!("Failed to encode CBOR response: {e}"))
            })?;
            Ok::<Vec<u8>, PyErr>(out)
        })
    }
}

pub struct AsyncEmbeddedDBInner {
    kvs: Arc<Datastore>,
    sessions: HashMap<Option<Uuid>, Arc<RwLock<Session>>>,
}

impl RpcProtocol for AsyncEmbeddedDBInner {
    fn kvs(&self) -> &Datastore {
        &self.kvs
    }

    fn version_data(&self) -> DbResult {
        DbResult::Other(PublicValue::String(
            format!("surrealdb-{}", env!("CARGO_PKG_VERSION")).into(),
        ))
    }

    fn session_map(&self) -> &HashMap<Option<Uuid>, Arc<RwLock<Session>>> {
        &self.sessions
    }

    const LQ_SUPPORT: bool = false;

    fn handle_live(
        &self,
        _lqid: &Uuid,
        _session_id: Option<Uuid>,
    ) -> impl std::future::Future<Output = ()> + Send {
        async {}
    }

    fn handle_kill(&self, _lqid: &Uuid) -> impl std::future::Future<Output = ()> + Send {
        async {}
    }

    fn cleanup_lqs(
        &self,
        _session_id: Option<&Uuid>,
    ) -> impl std::future::Future<Output = ()> + Send {
        async {}
    }

    fn cleanup_all_lqs(&self) -> impl std::future::Future<Output = ()> + Send {
        async {}
    }
}
