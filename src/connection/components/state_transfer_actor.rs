//! Defines everything needed to run a state transfer actor.
//! The `StateTransferActor` keeps a hashmap of keys and values. When the `StateTransferActor` is running it is essentially listening for incoming messages
//! which take the form of `StateTransferMessage<K, V>` where K is the key type and V is the value type. You can perform the following operations on the
//! `StateTransferActor`:
//! * Create a new key value pair
//! * Get a value from a key
//! * Delete a key value pair
//! It must be noted that when the Get operation is performed on the `StateTransferActor` the value is removed from the hashmap and returned to the caller.
//! The key is cached and the value is returned to the `StateTransferActor` when the `retrieve_value` method is called. This is to ensure that there is
//! only one value. If the `retrieve_value` method is not called by the `StateTransferActor` then the value is lost. This actor can be useful for sharing
//! state between multiple actors and threads where the state is not to be cloned. An example of this is a database connection pool where we don't want to
//! clone the connection but we want to share it between multiple actors and threads.
use std::cmp::Eq;
use std::fmt::Display;
use std::hash::Hash;
use core::fmt::Debug;
use std::collections::HashMap;

use tokio::sync::mpsc::{Receiver, Sender};
use tokio::sync::oneshot;


/// The message type that is sent to the `StateTransferActor`.
/// 
/// # Variants
/// * `Create` - Create a new key value pair using a key and value.
/// * `Get` - Get a value from a key using the `WrappedValue` struct to send the value back and fourth between client and `StateTransferActor`.
/// * `Delete` - Delete a key value pair using a key.
/// 
/// # Type Parameters
/// * `K` - The key type.
/// * `V` - The value type.
#[derive(Debug)]
pub enum StateTransferMessage<K, V> {
    Create(K, V),
    Get(K, oneshot::Sender<WrappedValue<V>>),
    Delete(K),
}


/// The wrapped value is used to send the value back and fourth between client and `StateTransferActor`.
/// 
/// # Fields
/// * `value` - The value that is wrapped and sent between the client and the `StateTransferActor`.
/// * `sender` - The sender that is used to send the value back to the `StateTransferActor` from the client.
/// 
/// # Type Parameters
/// * `V` - The value type.
#[derive(Debug)]
pub struct WrappedValue<V> {
    pub value: Option<V>,
    pub sender: Option<oneshot::Sender<V>>
}


/// Listens for incoming messages and performs operations on the state.
/// 
/// # Fields
/// * `rx` - The receiver that is used to listen for incoming messages.
/// * `state` - The hashmap that is used to store the state.
/// * `reciever` - The reciever that is used to listen for incoming `WrappedValue` from the client after it has sent out the `WrappedValue` to the client.
/// * `cached_key` - The key that is cached when the `WrappedValue` is in the client's possession.
/// 
/// # Type Parameters
/// * `K` - The key type.
/// * `V` - The value type.
pub struct StateTransferActor<K, V> 
where
    K: PartialEq + Eq + Hash + Debug,
    V: Debug
{
    pub rx: Receiver<StateTransferMessage<K, V>>,
    pub state: HashMap<K, Option<V>>,
    pub reciever: Option<oneshot::Receiver<V>>,
    pub cached_key: Option<K>,
}

impl<K, V> StateTransferActor<K, V> 
where
    K: PartialEq + Eq + Hash + Debug,
    V: Debug
{

    /// Creates a new `StateTransferActor` using a receiver.
    /// 
    /// # Arguments
    /// * `rx` - The receiver that is used to listen for incoming requests from clients.
    /// 
    /// # Returns
    /// A new `StateTransferActor` instance.
    pub fn new(rx: Receiver<StateTransferMessage<K, V>>) -> Self {
        Self {
            rx,
            state: HashMap::new(),
            reciever: None,
            cached_key: None,
        }
    }

    /// Removes the value from the hashmap to be yielded caching the key of the value in the process.
    /// 
    /// # Arguments
    /// * `key` - The key that is used to retrieve the value from the hashmap.
    /// 
    /// # Returns
    /// A `WrappedValue` instance that contains the value and a sender that is used to send the value back to the `StateTransferActor` from the client.
    pub fn yield_value(&mut self, key: K) -> WrappedValue<V> {
        let extracted_value: Option<V>;
        match self.state.remove(&key) {
            Some(value) => {
                extracted_value = value;
            }
            None => {
                extracted_value = None;
            }
        }
        let (sender, reciever) = oneshot::channel::<V>();
        self.reciever = Some(reciever);
        self.cached_key = Some(key);
        WrappedValue {
            value: extracted_value,
            sender: Some(sender)
        }
    }

    /// Accepts a value assigning it to the key that is cached.
    /// 
    /// # Arguments
    /// * `value` - The value that is to be assigned to the key that is cached.
    pub fn retrieve_value(&mut self, value: Option<V>) {
        let key = self.cached_key.take().unwrap();
        self.state.insert(key, value);
    }

}


/// Performs the appropiate operation on the `StateTransferActor` based on the incoming message.
/// 
/// # Arguments
/// * `actor` - The `StateTransferActor` that is to be operated on.
/// * `message` - The message that is to be processed.
/// 
/// # Type Parameters
/// * `K` - The type of the key.
/// * `V` - The type of the value.
async fn process_incoming_message<K, V>(
    actor: &mut StateTransferActor<K, V>,
    message: StateTransferMessage<K, V>
)
where
    K: PartialEq + Eq + Hash + Debug,
    V: Debug
{
    match message {
        StateTransferMessage::Create(key, value) => {
            actor.state.insert(key, Some(value));
        }
        StateTransferMessage::Get(key, sender) => {
            let wrapped_value = actor.yield_value(key);
            let _ = sender.send(wrapped_value);
            let value = match actor.reciever.as_mut().unwrap().await {
                Ok(value) => Some(value),
                Err(_) => None,
            };
            actor.retrieve_value(value);
        }
        StateTransferMessage::Delete(key) => {
            actor.state.remove(&key);
        }
    };
}


/// Runs the `StateTransferActor` indefinitely so the `StateTransferActor` can listen to incoming messages and process them.
/// 
/// # Arguments
/// * `actor` - The `StateTransferActor` that is to be run.
/// 
/// # Type Parameters
/// * `K` - The type of the key.
/// * `V` - The type of the value.
pub async fn run_state_transfer_actor<K, V>(
    mut actor: StateTransferActor<K, V>
) 
where
    K: PartialEq + Eq + Hash + Debug,
    V: Debug
{
    loop {
        if let Some(message) = actor.rx.recv().await {
            process_incoming_message(&mut actor, message).await;
        }
    }
}


// ==================== Client Functions (interfaces) below ====================


/// Sends a message to the `StateTransferActor` to get a value from the state based off the key.
/// 
/// # Arguments
/// * `key` - The key that is used to retrieve the value from the state.
/// * `sender` - The sender that is used to send the message to the `StateTransferActor`.
/// * `tag` - The tag that is used to identify error messages.
/// 
/// # Type Parameters
/// * `V` - The type of the value.
/// * `K` - The type of the key.
/// * `S` - The type of the tag.
/// 
/// # Returns
/// * `Result` that contains either a `WrappedValue` instance or an error message.
pub async fn get_value<V, K, S: Display>(key: K, sender: Sender<StateTransferMessage<K, V>>, tag: S) -> Result<WrappedValue<V>, String> {
    let (response_sender, response_receiver) = oneshot::channel::<WrappedValue<V>>();
    let message = StateTransferMessage::Get(key, response_sender);

    sender.send(message).await.map_err(|e| format!("Error sending message to {} actor: {}", tag, e))?;
    let response = response_receiver.await.map_err(|e| format!("Error getting {}: {}", tag, e))?;
    if &response.value.is_none() == &true {
        return Err(format!("Error getting {}: {} is empty", tag, tag))
    };
    if &response.sender.is_none() == &true {
        return Err(format!("Error getting {}: {} is present but doesn't have a sender", tag, tag))
    };
    return Ok(response)
}


/// Returns the value taken from the `StateTransferActor` back to the `StateTransferActor`.
/// 
/// # Arguments
/// * `value_message` - The `WrappedValue` instance that contains the value and the sender that is used to send the value back to the `StateTransferActor`.
/// * `tag` - The tag that is used to identify error messages.
/// 
/// # Type Parameters
/// * `V` - The type of the value.
/// * `S` - The type of the tag.
/// 
/// # Returns
/// * `Result` that contains either `()` if successful or an error message.
pub async fn return_value<V, S: Display>(value_message: WrappedValue<V>, tag: S) -> Result<(), String> {
    if &value_message.value.is_none() == &true {
        return Err(format!("trying to return empty {} to {} actor", tag, tag))
    };
    if &value_message.sender.is_none() == &true {
        return Err(format!("trying to return {} to {} actor without a sender", tag, tag))
    };
    let _ = value_message.sender.unwrap().send(value_message.value.unwrap());
    return Ok(())
}


#[cfg(test)]
mod tests {
    use super::*;
    use tokio::runtime::{Builder, Runtime};
    use tokio::sync::mpsc::channel;
    use std::fmt::Formatter;

    pub type Key = String;
    pub type Value = i32;
    pub type Message = StateTransferMessage<Key, Value>;

    /// Creates a test instance of a `StateTransferActor` with a `Sender` that is used to send messages to the `StateTransferActor`.
    /// to be used interally and externally in other testing modules.
    /// 
    /// # Returns
    /// * A tuple that contains a `StateTransferActor` instance and a `Sender` instance.
    pub fn create_test_transfer_state_actor() -> (StateTransferActor<Key, Value>, Sender<Message>) {
        let (tx, rx) = channel::<Message>(10);
        let mut actor = StateTransferActor::new(rx);
        actor.state.insert("test".to_string(), Some(1));
        actor.state.insert("test_two".to_string(), Some(2));
        return (actor, tx)
    }

    fn create_test_runtime() -> Runtime {
        Builder::new_current_thread()
        .enable_all()
        .build()
        .expect("Failed to create Tokio runtime.")
    }

    struct TestTag;

    impl Display for TestTag {
        fn fmt(&self, f: &mut Formatter<'_>) -> std::fmt::Result {
            write!(f, "TEST_ACTOR")
        }
    }


    #[test]
    fn test_yield_and_retrieve_value() {
        let (_, rx) = channel::<Message>(10);
        let mut actor = StateTransferActor::new(rx);

        actor.state.insert("test".to_string(), Some(1));
        actor.state.insert("test_two".to_string(), Some(2));
        assert_eq!(&actor.state.get(&"test".to_string()), &Some(&Some(1)));

        // extract present value from state
        let wrapped_value = actor.yield_value("test".to_string());

        assert_eq!(&wrapped_value.value, &Some(1));
        assert_eq!(&actor.cached_key, &Some("test".to_string()));
        assert_eq!(&actor.state.get(&"test".to_string()), &None);

        // retrieve value to state
        actor.retrieve_value(Some(1));

        assert_eq!(&actor.state.get(&"test".to_string()), &Some(&Some(1)));
        assert_eq!(&actor.cached_key, &None);

        // extract non-present value from state
        let wrapped_value = actor.yield_value("test_three".to_string());

        assert_eq!(&wrapped_value.value, &None);
    }

    #[test]
    fn test_process_incoming_message_get() {
        let runtime = create_test_runtime();

        // define the channels for the actor
        let (mut actor, _) = create_test_transfer_state_actor();
        let (message_tx, message_rx) = oneshot::channel::<WrappedValue<Value>>();

        // define the message to be processed by the actor
        let message = StateTransferMessage::Get("test".to_string(), message_tx);

        // spawn async task of processing the message
        let incoming_message_handle = runtime.spawn(async move {
            let _ = process_incoming_message(&mut actor, message).await;
            return actor
        });
        // spawn async task of getting value from the state actor and returning it
        let outcome_handle = runtime.spawn(async move {
            let outcome = message_rx.await.unwrap();
            // assert correct value is extracted from the state actor
            assert_eq!(outcome.value, Some(1));
            let _ = outcome.sender.unwrap().send(outcome.value.unwrap());
        });

        // block runtime until both tasks are completed
        let message_outcome = runtime.block_on(incoming_message_handle);
        let _ = runtime.block_on(outcome_handle);

        // assert that value is back in the state actor
        assert_eq!(
            message_outcome.unwrap().state.get(&"test".to_string()).unwrap().unwrap(), 
            1
        );
    }

    #[test]
    fn test_get_message_running_actor() {
        let runtime = create_test_runtime();

        // define the channels for the actor
        let (actor, tx) = create_test_transfer_state_actor();
        let (message_tx, message_rx) = oneshot::channel::<WrappedValue<Value>>();

        let message = StateTransferMessage::Get("test".to_string(), message_tx);

        let _run_actor_handle = runtime.spawn(async move {
            let _ = run_state_transfer_actor(actor).await;
        });

        // below is how you send a message to the running actor 
        let incoming_message_handle = runtime.spawn(async move {
            let _ = tx.send(message).await;
            let response: WrappedValue<i32> = message_rx.await.unwrap();
            assert_eq!(&response.value, &Some(1));
            let _ = response.sender.unwrap().send(response.value.unwrap());
        });
        let _ = runtime.block_on(incoming_message_handle);
    }

    #[test]
    fn test_process_incoming_message_insert() {
        let runtime = create_test_runtime();

        let (mut actor, _) = create_test_transfer_state_actor();

        // define the message to be processed by the actor
        let message = StateTransferMessage::Create("test_three".to_string(), 3);

        // spawn async task of processing the message
        let incoming_message_handle = runtime.spawn(async move {
            let _ = process_incoming_message(&mut actor, message).await;
            return actor
        });

        // block runtime until the create message is processed
        let message_outcome = runtime.block_on(incoming_message_handle);

        // assert that value is back in the state actor
        assert_eq!(
            message_outcome.unwrap().state.get(&"test_three".to_string()).unwrap().unwrap(), 
            3
        );
    }

    #[test]
    fn test_process_incoming_message_delete() {
        let runtime = create_test_runtime();

        let (mut actor, _) = create_test_transfer_state_actor();

        // define the message to be processed by the actor
        let message = StateTransferMessage::Delete("test".to_string());

        // spawn async task of processing the message
        let incoming_message_handle = runtime.spawn(async move {
            let _ = process_incoming_message(&mut actor, message).await;
            return actor
        });

        // block runtime until the delete message is processed
        let message_outcome = runtime.block_on(incoming_message_handle);

        // assert that value is back in the state actor
        match message_outcome.unwrap().state.get(&"test".to_string()) {
            Some(_) => panic!("Value not deleted from state"),
            None => (),
        }
    }

    #[test]
    fn test_get_value() {
        let runtime = create_test_runtime();
        let (actor, tx) = create_test_transfer_state_actor();

        let _run_actor_handle = runtime.spawn(async move {
            let _ = run_state_transfer_actor(actor).await;
        });

        let tx_clone = tx.clone();
        let incoming_message_handle = runtime.spawn(async move {
            let value = get_value::<Value, Key, TestTag>("test".to_string(), tx_clone, TestTag).await;
            value.unwrap().value
        });
        let returned_value = runtime.block_on(incoming_message_handle).unwrap();
        assert_eq!(returned_value, Some(1));

        // should fail as connection has been removed before
        let tx_clone = tx.clone();
        let incoming_message_handle = runtime.spawn(async move {
            get_value::<Value, Key, TestTag>("test".to_string(), tx_clone, TestTag).await
        });
        let returned_value = runtime.block_on(incoming_message_handle);
        match returned_value.unwrap() {
            Ok(_) => panic!("Value should not be returned"),
            Err(e) => assert_eq!(e, "Error getting TEST_ACTOR: TEST_ACTOR is empty".to_string()),
        }
    }

    #[test]
    fn test_return_value() {
        let runtime = create_test_runtime();
        let (actor, tx) = create_test_transfer_state_actor();

        let _run_actor_handle = runtime.spawn(async move {
            let _ = run_state_transfer_actor(actor).await;
        });

        let tx_clone = tx.clone();
        let incoming_message_handle = runtime.spawn(async move {
            let value = get_value::<Value, Key, TestTag>("test".to_string(), tx_clone, TestTag).await;
            value.unwrap()
        });
        let returned_value = runtime.block_on(incoming_message_handle).unwrap();

        let outgoing_message_handle = runtime.spawn(async move {
            return_value::<Value, TestTag>(returned_value, TestTag).await
        });
        let outcome = runtime.block_on(outgoing_message_handle);
        assert_eq!(outcome.unwrap(), Ok(()));
    }
}
