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
pub enum StateTransferMessage<K, V> {
    Create(K, V),
    Get(K, Sender<WrappedValue<V>>),
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
    V: Eq + Debug
{
    pub rx: Receiver<StateTransferMessage<K, V>>,
    pub state: HashMap<K, Option<V>>,
    pub reciever: Option<oneshot::Receiver<V>>,
    pub cached_key: Option<K>,
}

impl<K: PartialEq, V: Eq> StateTransferActor<K, V> 
where
    K: PartialEq + Eq + Hash + Debug, 
    V: Eq + Debug
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
    V: Eq + Debug 
{
    match message {
        StateTransferMessage::Create(key, value) => {
            actor.state.insert(key, Some(value));
        }
        StateTransferMessage::Get(key, sender) => {
            let wrapped_value = actor.yield_value(key);
            let _ = sender.send(wrapped_value).await;
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
    V: Eq + Debug
{
    loop {
        if let Some(message) = actor.rx.recv().await {
            process_incoming_message(&mut actor, message).await;
        }
    }
}


#[cfg(test)]
mod tests {
    use super::*;
    use tokio::runtime::{Builder, Runtime};
    use tokio::sync::mpsc::channel;

    type Key = String;
    type Value = i32;
    type Message = StateTransferMessage<Key, Value>;


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
        let runtime = Builder::new_current_thread()
        .enable_all()
        .build()
        .expect("Failed to create Tokio runtime.");

        // define the channels for the actor
        let (_, rx) = channel::<Message>(10);
        let (message_tx, mut message_rx) = channel::<WrappedValue<Value>>(10);

        // define the actor and it's state
        let mut actor = StateTransferActor::new(rx);
        actor.state.insert("test".to_string(), Some(1));
        actor.state.insert("test_two".to_string(), Some(2));

        // define the message to be processed by the actor
        let message = StateTransferMessage::Get("test".to_string(), message_tx.clone());

        // spawn async task of processing the message
        let incoming_message_handle = runtime.spawn(async move {
            let _ = process_incoming_message(&mut actor, message).await;
            return actor
        });
        // spawn async task of getting value from the state actor and returning it
        let outcome_handle = runtime.spawn(async move {
            let outcome = message_rx.recv().await.unwrap();
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
    fn test_process_incoming_message_insert() {
        let runtime = Builder::new_current_thread()
        .enable_all()
        .build()
        .expect("Failed to create Tokio runtime.");

        // define the channels for the actor
        let (_, rx) = channel::<Message>(10);

        // define the actor and it's state
        let mut actor = StateTransferActor::new(rx);
        actor.state.insert("test".to_string(), Some(1));
        actor.state.insert("test_two".to_string(), Some(2));

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
        let runtime = Builder::new_current_thread()
        .enable_all()
        .build()
        .expect("Failed to create Tokio runtime.");

        // define the channels for the actor
        let (_, rx) = channel::<Message>(10);

        // define the actor and it's state
        let mut actor = StateTransferActor::new(rx);
        actor.state.insert("test".to_string(), Some(1));
        actor.state.insert("test_two".to_string(), Some(2));

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
}
