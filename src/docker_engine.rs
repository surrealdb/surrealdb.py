//! defines the test functions for creating and destroying a SurrealDB instance in docker. 
use bollard::container::Config;
use bollard::Docker;

use std::collections::HashMap;
use bollard::models::HostConfig;
use bollard::models::PortBinding;
use once_cell::sync::Lazy;
use std::sync::{Arc, Mutex};


/// The global docker engine instance. This is a Singleton to ensure that one instance of SurrealDB is running at a time.
pub static DOCKER_ENGINE: Lazy<Arc<Mutex<DockerEngine>>> = Lazy::new(|| Arc::new(Mutex::new(DockerEngine { id: None })));


/// The interface for handling a SurrealDB instance in docker.
/// 
/// # Fields
/// * `id` - The container id of the SurrealDB instance
pub struct DockerEngine {
    pub id: Option<String>
}



pub async fn start(engine: &mut DockerEngine) {
    let id = start_database().await;
    engine.id = Some(id);
}

pub async fn shutdown(engine: &mut DockerEngine) {
    let id = engine.id.as_ref().unwrap().clone();
    shutdown_database(&id).await;
}


/// Creates a SurrealDB instance in docker and returns the container id.
/// 
/// # Returns
/// * `String` - The container id of the SurrealDB instance
async fn start_database() -> String {
    let docker = Docker::connect_with_socket_defaults().unwrap();

    let mut port_bindings = HashMap::new();
    port_bindings.insert(
        String::from("8000/tcp"),
        Some(vec![PortBinding {
            host_ip: Some(String::from("127.0.0.1")),
            host_port: Some(String::from("8001")),
        }]),
    );
    let host_config = HostConfig {
        port_bindings: Some(port_bindings),
        ..Default::default()
    };

    let mut exposed_ports = HashMap::new();
    let empty = HashMap::<(), ()>::new();
    exposed_ports.insert("8000/tcp", empty);

    let image_config = Config {
        image: Some("surrealdb/surrealdb"),
        tty: Some(true),
        attach_stdin: Some(true),
        attach_stdout: Some(true),
        attach_stderr: Some(true),
        open_stdin: Some(true),
        env: Some(vec!["SURREAL_USER=root", "SURREAL_PASS=root", "SURREAL_LOG=trace"]),
        cmd: Some(vec!["start"]),
        exposed_ports: Some(exposed_ports),
        host_config: Some(host_config),
        ..Default::default()
    };
    let id: String = docker.create_container::<&str, &str>(None, image_config).await.unwrap().id;
    docker.start_container::<String>(&id, None).await.unwrap();
    return id
}


/// Shuts down a SurrealDB instance in docker.
/// 
/// # Arguments
/// * `id` - The container id of the SurrealDB instance
/// 
/// # Returns
/// None 
async fn shutdown_database(id: &str) {
    let docker = Docker::connect_with_socket_defaults().unwrap();
    docker.stop_container(id, None).await.unwrap();
    docker.remove_container(id, None).await.unwrap();
}
