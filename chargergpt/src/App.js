import React, { useState, useEffect, useMemo } from "react";
import "./App.css";
import { getMapImageUrl } from "./aws/s3Helper";

const AWS = window.AWS;

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [mapUrl, setMapUrl] = useState(null);
  const [mapLocation, setMapLocation] = useState(null);

  const REGION = window._env_?.REGION;
  const IDPOOL = window._env_?.IDENTITY_POOL_ID;
  const BOT_ID = window._env_?.BOT_ID;
  const BOT_ALIAS = window._env_?.BOT_ALIAS_ID;
  const LOCALE = window._env_?.LOCALE_ID || "en_US";

  const sessionId = useMemo(() => "user-" + Date.now(), []);

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
    const interval = setInterval(() => {
      i++;
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = { ...baseMessage, txt: fullText.slice(0, i) };
        return updated;
      });
      if (i === fullText.length) {
        clearInterval(interval);
        setIsTyping(false);
      }
    }, 30);
  };

  const handleSend = (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const text = input;
    setInput("");
    appendMessage("You: " + text, "user");
    setIsTyping(true);

    AWS.config.credentials.get((err) => {
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

      lexruntime.recognizeText(params, async function (err, data) {
        if (err) {
          console.error(err);
          appendTypingMessage("Error: " + err.message, "bot");
        } else {
          if (data.messages && data.messages.length) {
            const botReply = "Bot: " + data.messages.map((m) => m.content).join(" ");
            appendTypingMessage(botReply, "bot");
          }

          // ✅ Look for location sessionAttribute from Lex
          const location = data.sessionState?.sessionAttributes?.location;
          if (location) {
            setMapLocation(location);
            const url = await getMapImageUrl(location);
            setMapUrl(url);
          }
        }
      });
    });
  };

  return (
    <div id="chat" style={{ padding: "20px", maxWidth: "500px", margin: "0 auto" }}>
      <div
        id="messages"
        style={{
          border: "1px solid #ccc",
          borderRadius: "5px",
          padding: "10px",
          height: "300px",
          overflowY: "auto",
          marginBottom: "10px",
        }}
      >
        {messages.map((m, i) => (
          <div key={i} className={m.cls}>{m.txt}</div>
        ))}
        {isTyping && <div className="typing-indicator"><span></span><span></span><span></span></div>}
      </div>

      <form onSubmit={handleSend}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask something..."
          style={{
            width: "100%",
            padding: "10px",
            borderRadius: "5px",
            border: "1px solid #ccc",
          }}
        />
      </form>

      {/* 🗺️ Map Section */}
      {mapUrl && (
        <div style={{ marginTop: "20px", textAlign: "center" }}>
          <h4>{mapLocation} Map</h4>
          <img src={mapUrl} alt={`${mapLocation} map`} style={{ width: "100%", maxWidth: "400px", borderRadius: "8px" }} />
        </div>
      )}
    </div>
  );
}
