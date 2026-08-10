use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3_async_runtimes::tokio::future_into_py;
use std::sync::Arc;
use std::sync::Mutex;
use surrealdb_core::dbs::Session;
use surrealdb_core::kvs::Datastore;
use surrealdb_core::rpc::format::cbor;
use surrealdb_core::rpc::{DbResponse, DbResult, RpcProtocol, Request};
use surrealdb_types::{HashMap, Value as PublicValue};
use tokio::sync::RwLock;
use uuid::Uuid;

#[pyclass]
pub struct AsyncEmbeddedDB {
    inner: Mutex<Option<Arc<AsyncEmbeddedDBInner>>>,
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
        let runtime = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| {
                PyErr::new::<PyRuntimeError, _>(format!("Failed to create runtime: {e}"))
            })?;
        let kvs = runtime.block_on(async {
            let ds = Datastore::new(&endpoint).await.map_err(|e| {
                PyErr::new::<PyRuntimeError, _>(format!("Failed to create datastore: {e}"))
            })?;
            ds.bootstrap().await.map_err(|e| {
                PyErr::new::<PyRuntimeError, _>(format!("Failed to bootstrap datastore: {e}"))
            })?;
            Ok::<Datastore, PyErr>(ds)
        })?;
        // The embedded engine exposes a single implicit session: `attach`,
        // `detach` and client-side transactions all raise
        // `UnsupportedFeatureError` on the Python side, so requests never carry
        // a session id. `RpcProtocol` keys its session map by a concrete
        // `Uuid`, so mint one here and route every unnamed request to it - that
        // keeps `use`/`signin` state on the connection, as it was when the map
        // was keyed by `Option<Uuid>` and this session lived under `None`.
        let session_id = Uuid::new_v4();
        let sessions: HashMap<Uuid, Arc<RwLock<Session>>> = HashMap::new();
        let mut sess = Session::default().with_rt(false);
        sess.id = Some(session_id);
        sessions.insert(session_id, Arc::new(RwLock::new(sess)));
        Ok(AsyncEmbeddedDB {
            inner: Mutex::new(Some(Arc::new(AsyncEmbeddedDBInner {
                kvs: Arc::new(kvs),
                sessions,
                session_id,
            }))),
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
        let kvs = {
            let mut guard = self.inner.lock().map_err(|e| {
                PyErr::new::<PyRuntimeError, _>(format!("Lock poisoned: {e}"))
            })?;
            guard.take().map(|inner| inner.kvs.clone())
        };
        future_into_py::<_, ()>(py, async move {
            if let Some(kvs) = kvs {
                let _ = kvs.shutdown().await;
            }
            Ok(())
        })
    }

    fn execute<'a>(&self, py: Python<'a>, cbor_request: &[u8]) -> PyResult<Bound<'a, PyAny>> {
        let data = cbor_request.to_vec();
        let inner = {
            let guard = self.inner.lock().map_err(|e| {
                PyErr::new::<PyRuntimeError, _>(format!("Lock poisoned: {e}"))
            })?;
            guard.as_ref().ok_or_else(|| {
                PyErr::new::<PyRuntimeError, _>("Database connection is closed")
            })?.clone()
        };
        future_into_py(py, async move {
            // Bound request nesting with the same knob the server feeds its
            // parsers (`SURREAL_MAX_OBJECT_PARSING_DEPTH`, default 100).
            let recursion_limit = inner.kvs.config().max_object_parsing_depth as usize;
            let value = cbor::decode(&data, recursion_limit).map_err(|e| {
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
            let client_session = req.session_id.map(Uuid::from);
            let session = client_session.unwrap_or(inner.session_id);
            let txn = req.txn.map(Uuid::from);
            let response = match RpcProtocol::execute(
                inner.as_ref(),
                txn,
                session,
                client_session,
                req.method,
                req.params,
            )
            .await
            {
                Ok(result) => DbResponse::success(rid, client_session, result),
                Err(error) => DbResponse::failure(rid, client_session, error),
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
    sessions: HashMap<Uuid, Arc<RwLock<Session>>>,
    /// The implicit session every unnamed request runs under.
    session_id: Uuid,
}

impl RpcProtocol for AsyncEmbeddedDBInner {
    fn kvs(&self) -> &Datastore {
        &self.kvs
    }

    fn kvs_arc(&self) -> Arc<Datastore> {
        Arc::clone(&self.kvs)
    }

    fn version_data(&self) -> DbResult {
        // The engine that is linked, not this wrapper crate. `CARGO_PKG_VERSION`
        // here would be surrealdb-embedded's own version, which says nothing
        // about the database being run and disagrees with what the same call
        // returns over HTTP or WebSocket. `env::VERSION` is baked into
        // surrealdb-core when it is compiled, so it cannot drift from the
        // engine actually inside the wheel.
        DbResult::Other(PublicValue::String(format!(
            "surrealdb-{}",
            surrealdb_core::env::VERSION
        )))
    }

    fn session_map(&self) -> &HashMap<Uuid, Arc<RwLock<Session>>> {
        &self.sessions
    }

    const LQ_SUPPORT: bool = false;

    fn handle_live(
        &self,
        _lqid: &Uuid,
        _session_id: Uuid,
        _namespace: Option<String>,
        _database: Option<String>,
    ) -> impl std::future::Future<Output = ()> + Send {
        async {}
    }

    fn handle_kill(&self, _lqid: &Uuid) -> impl std::future::Future<Output = ()> + Send {
        async {}
    }

    fn cleanup_lqs(&self, _session_id: &Uuid) -> impl std::future::Future<Output = ()> + Send {
        async {}
    }

    fn cleanup_all_lqs(&self) -> impl std::future::Future<Output = ()> + Send {
        async {}
    }
}
