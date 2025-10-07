import React, { useState, useEffect, useMemo } from "react";
import "./App.css";
import { getMapImageUrl } from "./aws/s3Helper";

const AWS = window.AWS;

export default function App() {
  // State variables for chat messages, user input, and typing animation
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);

  // Environment variables injected at runtime
  const REGION = window._env_?.REGION;
  const IDPOOL = window._env_?.IDENTITY_POOL_ID;
  const BOT_ID = window._env_?.BOT_ID;
  const BOT_ALIAS = window._env_?.BOT_ALIAS_ID;
  const LOCALE = window._env_?.LOCALE_ID || "en_US";

  // Generate a unique session ID for each user session
  const sessionId = useMemo(() => "user-" + Date.now(), []);

  // Configure AWS credentials on mount
  useEffect(() => {
    if (!AWS) return;
    AWS.config.region = REGION;
    AWS.config.credentials = new AWS.CognitoIdentityCredentials({
      IdentityPoolId: IDPOOL,
    });
  }, [REGION, IDPOOL]);

  // Helper to append a new message to chat
  const appendMessage = (txt, cls) => {
    setMessages((prev) => [...prev, { txt, cls }]);
  };

  // Displays a message one character at a time (typing effect)
  const appendTypingMessage = (fullText, cls) => {
    let i = 0;
    const baseMessage = { txt: "", cls };
    setMessages((prev) => [...prev, baseMessage]);
    setIsTyping(true);

    const interval = setInterval(() => {
      i++;
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          ...baseMessage,
          txt: fullText.slice(0, i),
        };
        return updated;
      });

      // Stop typing animation once message is complete
      if (i === fullText.length) {
        clearInterval(interval);
        setIsTyping(false);
      }
    }, 30);
  };

  // Handles sending user messages to Lex
  const handleSend = (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const text = input;
    setInput("");
    appendMessage("You: " + text, "user");
    setIsTyping(true);

    // Retrieve temporary AWS credentials before making Lex call
    AWS.config.credentials.get(async (err) => {
      if (err) {
        appendTypingMessage("Error: " + err.message, "bot");
        setIsTyping(false);
        return;
      }

      const lexruntime = new AWS.LexRuntimeV2();
      const params = {
        botId: BOT_ID,
        botAliasId: BOT_ALIAS,
        localeId: LOCALE,
        sessionId,
        text,
      };

      // Send text input to Lex bot
      lexruntime.recognizeText(params, async (err, data) => {
        if (err) {
          console.error(err);
          appendTypingMessage("Error: " + err.message, "bot");
        } else {
          // Append Lex response messages
          if (data.messages && data.messages.length) {
            const botReply = data.messages.map((m) => m.content).join(" ");
            appendTypingMessage("Bot: " + botReply, "bot");
          }

          // If Lex returns a 'location' attribute, show a map image
          const location = data.sessionState?.sessionAttributes?.location;
          if (location) {
            try {
              const url = await getMapImageUrl(location);
              if (url) {
                setMessages((prev) => [
                  ...prev,
                  {
                    txt: url,
                    cls: "bot-map",
                    type: "image",
                    location,
                  },
                ]);
              }
            } catch (err) {
              console.error("Error fetching map:", err);
            } finally {
              setIsTyping(false);
            }
          }
        }
      });
    });
  };

  return (
    <div
      id="chat"
      style={{
        padding: "30px",
        maxWidth: "750px",
        margin: "50px auto",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        backgroundColor: "#fefefe",
        borderRadius: "10px",
        boxShadow: "0 4px 10px rgba(0,0,0,0.1)",
      }}
    >
      {/* Chat message display area */}
      <div
        id="messages"
        style={{
          border: "1px solid #ccc",
          borderRadius: "10px",
          padding: "15px",
          height: "500px",
          width: "700px",
          overflowY: "auto",
          marginBottom: "15px",
          backgroundColor: "#fafafa",
        }}
      >
        {/* Render each message (text or image) */}
        {messages.map((m, i) => {
          if (m.type === "image") {
            // Map image message
            return (
              <div
                key={i}
                className={m.cls}
                style={{ textAlign: "center", margin: "15px 0" }}
              >
                <h4 style={{ marginBottom: "8px" }}>{m.location} Map</h4>
                <img
                  src={m.txt}
                  alt={`${m.location} map`}
                  style={{
                    width: "100%",
                    maxWidth: "500px",
                    borderRadius: "10px",
                    boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
                  }}
                />
              </div>
            );
          }
          // Regular text message
          return (
            <div
              key={i}
              className={m.cls}
              style={{
                margin: "8px 0",
                whiteSpace: "pre-wrap",
                lineHeight: "1.4",
              }}
            >
              {m.txt}
            </div>
          );
        })}

        {/* Typing indicator animation */}
        {isTyping && (
          <div className="typing-indicator">
            <span></span>
            <span></span>
            <span></span>
          </div>
        )}
      </div>

      {/* Input form for sending new messages */}
      <form
        onSubmit={handleSend}
        style={{
          display: "flex",
          width: "700px",
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask something..."
          style={{
            flex: 1,
            padding: "12px",
            borderRadius: "10px",
            border: "1px solid #ccc",
            fontSize: "16px",
            outline: "none",
            boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
          }}
        />
      </form>
    </div>
  );
}
