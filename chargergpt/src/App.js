import React, { useState, useEffect, useMemo } from "react";
import "./App.css";
import { getMapImageUrl } from "./aws/s3Helper";

const AWS = window.AWS;

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [sessionIDs, setSessionIDs] = useState([null, null, null]);

  const REGION = window._env_?.REGION;
  const IDPOOL = window._env_?.IDENTITY_POOL_ID;
  const BOT_ID = window._env_?.BOT_ID;
  const BOT_ALIAS = window._env_?.BOT_ALIAS_ID;
  const LOCALE = window._env_?.LOCALE_ID || "en_US";

  const sessionId = useMemo(() => "user-" + Date.now(), []);

  // Configure AWS credentials on mount
  useEffect(() => {
    if (!AWS) return;
    AWS.config.region = REGION;
    AWS.config.credentials = new AWS.CognitoIdentityCredentials({
      IdentityPoolId: IDPOOL,
    });
  }, [REGION, IDPOOL]);

  const appendMessage = (txt, cls) => {
    setMessages((prev) => [...prev, { txt, cls }]);
  };

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

      if (i === fullText.length) {
        clearInterval(interval);
        setIsTyping(false);
      }
    }, 30);
  };

  // Send message to Lex
  const handleSend = (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const text = input;
    setInput("");
    appendMessage("You: " + text, "user");
    setIsTyping(true);

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

      lexruntime.recognizeText(params, async (err, data) => {
        if (err) {
          console.error(err);
          appendTypingMessage("Error: " + err.message, "bot");
        } else {
          if (data.messages && data.messages.length) {
            const botReply = data.messages.map((m) => m.content).join(" ");
            appendTypingMessage("Bot: " + botReply, "bot");
          }

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

  // -------------------------------
  // Lambda invocation functions
  // -------------------------------

  const invokeLambda = (functionName, payload) =>
    new Promise((resolve, reject) => {
      const lambda = new AWS.Lambda();
      lambda.invoke(
        {
          FunctionName: functionName,
          Payload: JSON.stringify(payload),
        },
        (err, data) => {
          if (err) return reject(err);
          try {
            const parsed = JSON.parse(data.Payload);
            resolve(parsed);
          } catch (parseErr) {
            reject(parseErr);
          }
        }
      );
    });

  // Retrieve the 3 most recent session IDs
  const handleRefresh = async () => {
    try {
      const data = await invokeLambda("retrieveSessionIDs-prod", {});
      setSessionIDs(data.sessionIds || [null, null, null]);
    } catch (err) {
      console.error("Failed to retrieve session IDs:", err);
    }
  };

  // Restore a chat by sessionID
  const handleRestoreChat = async (index) => {
    const targetSessionId = sessionIDs[index];
    if (!targetSessionId) return;

    try {
      const data = await invokeLambda("restoreChats-prod", { sessionId: targetSessionId });
      if (data.conversation) {
        setMessages([]); // Clear current chat
        data.conversation.forEach((msg) => {
          if (msg.M.userMessage) appendMessage("You: " + msg.M.userMessage.S, "user");
          if (msg.M.botMessage) appendMessage("Bot: " + msg.M.botMessage.S, "bot");
        });
      }
    } catch (err) {
      console.error("Failed to restore chat:", err);
    }
  };

  // -------------------------------
  // JSX rendering
  // -------------------------------
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
      {/* Sidebar buttons */}
      <div style={{ marginBottom: "15px", display: "flex", gap: "10px" }}>
        <button onClick={handleRefresh}>Refresh</button>
        <button onClick={() => handleRestoreChat(0)}>Chat 1</button>
        <button onClick={() => handleRestoreChat(1)}>Chat 2</button>
        <button onClick={() => handleRestoreChat(2)}>Chat 3</button>
      </div>

      {/* Chat messages */}
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
        {messages.map((m, i) => {
          if (m.type === "image") {
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
          return (
            <div
              key={i}
              className={m.cls}
              style={{ margin: "8px 0", whiteSpace: "pre-wrap", lineHeight: "1.4" }}
            >
              {m.txt}
            </div>
          );
        })}

        {isTyping && (
          <div className="typing-indicator">
            <span></span>
            <span></span>
            <span></span>
          </div>
        )}
      </div>

      {/* Input form */}
      <form
        onSubmit={handleSend}
        style={{ display: "flex", width: "700px" }}
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
