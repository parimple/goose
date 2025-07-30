use thiserror::Error;
use serde::{Deserialize, Serialize};

use crate::message::{Message, MessageContent};
use std::result::Result;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Conversation {
    messages: Vec<Message>,
}

#[derive(Error, Debug)]
#[error("invalid conversation: {reason}")]
pub struct InvalidConversation {
    reason: String,
    conversation: Conversation,
}

impl Conversation {
    pub fn new<I>(messages: I) -> Result<Self, InvalidConversation>
    where
        I: IntoIterator<Item = Message>,
    {
        Self::new_unvalidated(messages).validate()
    }

    pub fn new_unvalidated<I>(messages: I) -> Self
    where
        I: IntoIterator<Item = Message>,
    {
        Self {
            messages: messages.into_iter().collect(),
        }
    }

    pub fn messages(&self) -> &Vec<Message> {
        &self.messages
    }

    pub fn push_message(&mut self, message: Message) {
        if let Some(last) = self
            .messages
            .last_mut()
            .filter(|m| m.id.is_some() && m.id == message.id)
        {
            match (last.content.last_mut(), message.content.last()) {
                (Some(MessageContent::Text(ref mut last)), Some(MessageContent::Text(new)))
                    if message.content.len() == 1 =>
                {
                    last.text.push_str(&new.text);
                }
                (_, _) => {
                    last.content.extend(message.content);
                }
            }
        } else {
            self.messages.push(message);
        }
    }

    pub fn last(&self) -> Option<&Message> {
        self.messages.last()
    }

    pub fn first(&self) -> Option<&Message> {
        self.messages.first()
    }

    pub fn len(&self) -> usize {
        self.messages.len()
    }

    pub fn is_empty(&self) -> bool {
        self.messages.is_empty()
    }

    pub fn push(&mut self, message: Message) {
        self.push_message(message);
    }

    pub fn extend<I>(&mut self, iter: I)
    where
        I: IntoIterator<Item = Message>,
    {
        for message in iter {
            self.push_message(message);
        }
    }

    pub fn iter(&self) -> std::slice::Iter<Message> {
        self.messages.iter()
    }

    pub fn pop(&mut self) -> Option<Message> {
        self.messages.pop()
    }

    pub fn truncate(&mut self, len: usize) {
        self.messages.truncate(len);
    }

    pub fn clear(&mut self) {
        self.messages.clear();
    }

    fn validate(self) -> Result<Self, InvalidConversation> {
        Ok(self)
    }
}
