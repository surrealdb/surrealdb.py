//! Defines enums for routing messages.
use serde::{Serialize, Deserialize};


/// This generic enum is used to package messages for sending to and back from the runtime.
/// 
/// # Variants
/// * `Send(Option<T>)` - Packages a message to be sent to the runtime from the client
/// * `Receive(Option<X>)` - Packages a message to be sent to the client from the runtime
#[derive(Debug, PartialEq, Clone, Deserialize, Serialize)]
pub enum Message<T, X> {
    Send(Option<T>),
    Receive(Option<X>)
}


impl <T, X>Message<T, X> {

    /// Packages a message to be sent to the runtime from the client.
    /// 
    /// # Arguments
    /// * `send` - The message to be sent to the runtime.
    /// 
    /// # Returns
    /// * `Message<T, X>` - The packaged message.
    pub fn package_send(send: T) -> Message<T, X> {
        Message::Send(Some(send))
    }

    /// Packages a message to be sent to the client from the runtime.
    /// 
    /// # Arguments
    /// * `receive` - The message to be sent to the client.
    /// 
    /// # Returns
    /// * `Message<T, X>` - The packaged message.
    pub fn package_receive(receive: X) -> Message<T, X> {
        Message::Receive(Some(receive))
    }

    /// Unpacks the message sent from the client to the runtime in the runtime.
    /// 
    /// # Returns
    /// * `Result<T, String>` - The unpacked message.
    pub fn handle_send(self) -> Result<T, String> {
        match self {
            Message::Send(send) => {
                if let Some(send) = send {
                    return Ok(send)
                }
                return Err("no send message packaged".to_string())
            },
            Message::Receive(_) => Err("not a send message".to_string())
        }
    }

    /// Unpacks the message sent from the runtime to the client in the PyO3 function.
    /// 
    /// # Returns
    /// * `Result<X, String>` - The unpacked message.
    pub fn handle_recieve(self) -> Result<X, String> {
        match self {
            Message::Receive(receive) => {
                if let Some(receive) = receive {
                    return Ok(receive)
                }
                return Err("no receive message packaged".to_string())
            },
            Message::Send(_) => Err("not a receive message".to_string())
        }
    }
}
