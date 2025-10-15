import React, { useState, useEffect, useMemo } from "react";
import "./App.css";
import { getMapImageUrl } from "./aws/s3Helper";

const AWS = window.AWS;

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [savedSessionIDs, setSavedSessionIDs] = useState([]); // stores up to 3 session IDs
  const [activeSession, setActiveSession] = useState(null); // 🔹 NEW: track which session is currently displayed

  const REGION = window._env_?.REGION;
  const IDPOOL = window._env_?.IDENTITY_POOL_ID;
  const BOT_ID = window._env_?.BOT_ID;
  const BOT_ALIAS = window._env_?.BOT_ALIAS_ID;
  const LOCALE = window._env_?.LOCALE_ID || "en_US";

  const sessionId = useMemo(() => "user-" + Date.now(), []);

  // Configure AWS
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
    }, 25);
  };

  // --- Send message to Lex bot ---
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
          // 🔹 Expect backend JSON: {"response":"...", "sessionID":"..."}
          if (data.messages && data.messages.length) {
            let botReply = "";
            let returnedSessionID = null;

            try {
              const content = data.messages.map((m) => m.content).join(" ");
              const parsed = JSON.parse(content);

              if (parsed.response) {
                botReply = parsed.response;
                returnedSessionID = parsed.sessionID;
              } else {
                botReply = content;
              }
            } catch {
              botReply = data.messages.map((m) => m.content).join(" ");
            }

            appendTypingMessage("Bot: " + botReply, "bot");

            // 🔹 Maintain rolling session list
            const effectiveSessionID = returnedSessionID || sessionId;
            setSavedSessionIDs((prev) => {
              const updated = [effectiveSessionID, ...prev];
              if (updated.length > 3) updated.pop();
              return updated;
            });
            setActiveSession(effectiveSessionID);
          }

          // Optional: map rendering
          const location = data.sessionState?.sessionAttributes?.location;
          if (location) {
            try {
              const url = await getMapImageUrl(location);
              if (url) {
                setMessages((prev) => [
                  ...prev,
                  { txt: url, cls: "bot-map", type: "image", location },
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

  // --- Helper: Display restored chat messages ---
  const displayRestoredChat = async (conversation) => {
    if (!conversation || !conversation.length) {
      appendMessage("No messages found in this chat.", "bot");
      return;
    }

    // Wipe current messages before restoring
    setMessages([]);

    for (const entry of conversation) {
      const userMsg = entry.M.userMessage?.S;
      const botMsg = entry.M.botMessage?.S;

      // Display each message with slight delay for realism
      if (userMsg) {
        await new Promise((res) => {
          appendTypingMessage("You: " + userMsg, "user");
          setTimeout(res, 100);
        });
      }
      if (botMsg) {
        await new Promise((res) => {
          appendTypingMessage("Bot: " + botMsg, "bot");
          setTimeout(res, 150);
        });
      }
    }
  };

  // --- Restore from DynamoDB Lambda ---
  const restoreChats = async (targetSessionId) => {
    if (!targetSessionId) {
      appendMessage("No saved session found for this slot.", "bot");
      return;
    }

    try {
      const lambda = new AWS.Lambda();
      const params = {
        FunctionName: "restoreChats",
        Payload: JSON.stringify({ sessionId: targetSessionId }),
      };

      const result = await lambda.invoke(params).promise();
      const payload = JSON.parse(result.Payload);
      const conversation = payload.conversation?.L || [];

      setActiveSession(targetSessionId);

      // 🔹 NEW: animate restored messages in order
      await displayRestoredChat(conversation);
    } catch (err) {
      console.error("Error restoring chat:", err);
      appendMessage("Error restoring chat: " + err.message, "bot");
    }
  };

  return (
    <div
      id="chat"
      style={{
        padding: "30px",
        maxWidth: "900px",
        margin: "50px auto",
        display: "flex",
        gap: "20px",
      }}
    >
      {/* Sidebar for Chat Tabs */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "10px",
          width: "150px",
          backgroundColor: "#f9f9f9",
          padding: "10px",
          borderRadius: "10px",
          boxShadow: "0 2px 6px rgba(0,0,0,0.1)",
        }}
      >
        <h4 style={{ textAlign: "center", marginBottom: "10px" }}>Saved Chats</h4>

        {["Chat 1", "Chat 2", "Chat 3"].map((label, idx) => (
          <button
            key={label}
            onClick={() => restoreChats(savedSessionIDs[idx])}
            disabled={!savedSessionIDs[idx]}
            style={{
              padding: "10px",
              borderRadius: "8px",
              border: "1px solid #ccc",
              backgroundColor:
                activeSession === savedSessionIDs[idx]
                  ? "#0056b3"
                  : savedSessionIDs[idx]
                  ? "#007bff"
                  : "#ddd",
              color: savedSessionIDs[idx] ? "#fff" : "#666",
              cursor: savedSessionIDs[idx] ? "pointer" : "not-allowed",
              fontWeight: "bold",
              transition: "0.2s",
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Main Chat Area */}
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          backgroundColor: "#fefefe",
          borderRadius: "10px",
          boxShadow: "0 4px 10px rgba(0,0,0,0.1)",
          padding: "20px",
        }}
      >
        <div
          id="messages"
          style={{
            border: "1px solid #ccc",
            borderRadius: "10px",
            padding: "15px",
            height: "500px",
            width: "100%",
            overflowY: "auto",
            marginBottom: "15px",
            backgroundColor: "#fafafa",
          }}
        >
          {messages.map((m, i) =>
            m.type === "image" ? (
              <div key={i} className={m.cls} style={{ textAlign: "center", margin: "15px 0" }}>
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
            ) : (
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
            )
          )}

          {isTyping && (
            <div className="typing-indicator">
              <span></span>
              <span></span>
              <span></span>
            </div>
          )}
        </div>

        {/* Input */}
        <form onSubmit={handleSend} style={{ display: "flex", width: "100%" }}>
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
    </div>
  );
}
