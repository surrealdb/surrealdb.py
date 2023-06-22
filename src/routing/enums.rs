use serde::{Serialize, Deserialize};


#[derive(Debug, PartialEq, Clone, Deserialize, Serialize)]
pub enum Message<T, X> {
    Send(Option<T>),
    Receive(Option<X>)
}


impl <T, X>Message<T, X> {

    pub fn package_send(send: T) -> Message<T, X> {
        Message::Send(Some(send))
    }
    pub fn package_receive(receive: X) -> Message<T, X> {
        Message::Receive(Some(receive))
    }
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
