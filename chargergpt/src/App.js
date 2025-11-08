import React, { useState, useEffect, useRef } from "react";
import "./App.css";
import { getMapImageUrl } from "./aws/s3Helper";

const AWS = window.AWS;

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [sessionIDs, setSessionIDs] = useState([null, null, null]);
  const [sessionTimes, setSessionTimes] = useState([null, null, null]); // 🆕 store times
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [theme, setTheme] = useState("theme-auto");
  const messagesRef = useRef(null);
  const inputRef = useRef(null);

  const REGION = window._env_?.REGION;
  const IDPOOL = window._env_?.IDENTITY_POOL_ID;
  const BOT_ID = window._env_?.BOT_ID;
  const BOT_ALIAS = window._env_?.BOT_ALIAS_ID;
  const LOCALE = window._env_?.LOCALE_ID || "en_US";

  const [currentSessionId, setCurrentSessionId] = useState("user-" + Date.now());
  const canSend = (input || "").trim().length > 0;

  // Configure AWS credentials on mount
  useEffect(() => {
    if (!AWS) return;
    AWS.config.region = REGION;
    AWS.config.credentials = new AWS.CognitoIdentityCredentials({
      IdentityPoolId: IDPOOL,
    });
  }, [REGION, IDPOOL]);

  useEffect(() => {
    if (messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight;
    }
  }, [messages, isTyping]);

  useEffect(() => {
    try {
      const t = localStorage.getItem("chat-theme");
      if (t) setTheme(t);
    } catch {}
  }, []);

  useEffect(() => {
    setMessages((prev) => [...prev, { txt: "New chat started", cls: "system", ts: Date.now() }]);
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem("chat-theme", theme);
    } catch {}
  }, [theme]);

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = "auto";
      inputRef.current.style.height = inputRef.current.scrollHeight + "px";
    }
  }, [input]);

  const appendMessage = (txt, cls) => {
    setMessages((prev) => [...prev, { txt, cls, ts: Date.now() }]);
  };

  const appendTypingMessage = (fullText, cls) => {
    let i = 0;
    const baseMessage = { txt: "", cls, ts: Date.now() };
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
  const sendCurrent = () => {
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
        sessionId: currentSessionId,
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
                    ts: Date.now(),
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

  const handleSend = (e) => {
    e.preventDefault();
    sendCurrent();
  };

  const stripPrefixes = (s) => s.replace(/^You:\s*/i, "").replace(/^Bot:\s*/i, "");
  const escapeHtml = (s) => s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
  const renderRichText = (s) => {
    let t = stripPrefixes(s);
    t = escapeHtml(t);
    t = t.replace(/```([\s\S]*?)```/g, (m, code) => `<pre><code>${code}</code></pre>`);
    t = t.replace(/`([^`]+)`/g, '<code>$1</code>');
    t = t.replace(/(https?:\/\/[\w\-._~:?#@!$&'()*+,;=%/]+)(?![^<]*>)/g, '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>');
    return { __html: t };
  };
  const authorOf = (m) => {
    if (m.cls === "system") return "system";
    if (m.type === "image") return "bot";
    return m.cls && m.cls.includes("user") ? "user" : "bot";
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
      setSessionTimes(data.times || [null, null, null]); // 🆕 store times
    } catch (err) {
      console.error("Failed to retrieve session IDs:", err);
    }
  };

  // 🆕 Auto-refresh on mount
  useEffect(() => {
    handleRefresh();
  }, []);

  // Restore chat
  const handleRestoreChat = async (index) => {
    const targetSessionId = sessionIDs[index];
    if (!targetSessionId) return;

    try {
      // set Lex session to the selected chat
      setCurrentSessionId(targetSessionId);
      console.log("Switched to session:", targetSessionId);
  
      // Restore from DynamoDB (optional if you want history shown)
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

  // Reset chat
  const handleResetChat = async () => {
    setMessages([]);
    setMessages((prev) => [
      ...prev,
      { txt: "New chat started", cls: "system", ts: Date.now() },
    ]);
    const newId = "user-" + Date.now();
    setCurrentSessionId(newId);
    console.log("New session started:", newId);
  };

  // Helper to format timestamps nicely 🆕
  const formatTime = (t) => {
    if (!t) return "No chat";
    try {
      const date = new Date(t);
      return date.toLocaleString([], {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return t;
    }
  };

  // JSX
  return (
    <div className={`chat-root ${theme}`} data-sidebar={sidebarOpen ? "open" : "closed"}>
      <header className="chat-header" role="banner">
        <button
          className="icon-btn sidebar-toggle"
          aria-label="Toggle sidebar"
          aria-expanded={sidebarOpen}
          onClick={() => setSidebarOpen((v) => !v)}
        >
          <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
            <path d="M3 6h18v2H3zm0 5h18v2H3zm0 5h18v2H3z" />
          </svg>
        </button>
        <div className="title-group">
          <button
            className="app-title-bnt"
            onClick={handleResetChat}
            aria-label="Start a new chat"
          >
            <h1 className="app-title">ChargerGPT</h1>
            <div className="subtitle">UAH Assistant</div>
          </button>
        </div>
        <div className="header-actions">
          <button
            className="icon-btn theme-toggle"
            aria-label="Toggle dark mode"
            onClick={() => {
              setTheme((t) => {
                const seq = ["theme-auto", "theme-dark", "theme-light"];
                const idx = seq.indexOf(t);
                return seq[(idx + 1) % seq.length];
              });
            }}
          >
            <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
              <path d="M6.76 4.84l-1.8-1.79L3.17 4.84l1.79 1.79zM1 13h3v-2H1zm10 10h2v-3h-2zM4.22 19.78l1.79-1.79-1.8-1.79-1.79 1.79zM20 11V9h3v2zm-1.76-6.16l-1.79 1.79 1.8 1.79 1.79-1.79zM12 6a6 6 0 100 12 6 6 0 000-12z" />
            </svg>
          </button>
        </div>
      </header>

      <main className="chat-main" role="main">
        <aside className="chat-sidebar" aria-label="Recent chats">
          <div className="sidebar-header">
            <h2>Recent chats</h2>
            <button className="text-btn" onClick={handleRefresh}>
              Refresh
            </button>
          </div>
          <nav className="sidebar-list" role="navigation">
            <button className="sidebar-item" onClick={() => handleRestoreChat(0)}>
              <span className="dot"></span>
              <span className="label">{formatTime(sessionTimes[0])}</span>
            </button>
            <button className="sidebar-item" onClick={() => handleRestoreChat(1)}>
              <span className="dot"></span>
              <span className="label">{formatTime(sessionTimes[1])}</span>
            </button>
            <button className="sidebar-item" onClick={() => handleRestoreChat(2)}>
              <span className="dot"></span>
              <span className="label">{formatTime(sessionTimes[2])}</span>
            </button>
          </nav>
        </aside>

        <div className="chat-content">
        <section ref={messagesRef} className="chat-messages" role="log" aria-live="polite" aria-relevant="additions text">
          {messages.map((m, i) => {
            const author = authorOf(m);
            const prevAuthor = i > 0 ? authorOf(messages[i - 1]) : null;
            const grouped = prevAuthor === author && author !== "system";
            if (m.type === "image") {
              return (
                <div key={i} className="message image bot">
                  <div className={`flex items-start gap-2 ${grouped ? "mt-0" : "mt-2"}`}>
                    {!grouped && (
                      <div className="w-8 h-8 rounded-full bg-[var(--surface-2)] border border-[var(--border)] flex items-center justify-center text-xs font-semibold">B</div>
                    )}
                    <div className="bubble">
                      <img src={m.txt} alt={(m.location ? m.location + " map" : "attachment")} />
                      {m.location ? <div className="caption">{m.location} Map</div> : null}
                    </div>
                  </div>
                  {m.ts ? <div className="timestamp">{new Date(m.ts).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})}</div> : null}
                </div>
              );
            }
            if (m.cls === "system") {
              return (
                <div key={i} className="message system">
                  <div className="bubble">{m.txt}</div>
                  {m.ts ? <div className="timestamp text-[var(--muted)] text-xs mt-1">{new Date(m.ts).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})}</div> : null}
                </div>
              );
            }
            const isUser = author === "user";
            return (
              <div key={i} className={`message ${isUser ? "user" : "bot"}`}>
                <div className={`flex items-start gap-2 ${isUser ? "justify-end" : ""} ${grouped ? "mt-0" : "mt-2"}`}>
                  {isUser ? (
                    <>
                      <div className="bubble">{stripPrefixes(m.txt)}</div>
                      {!grouped && <div className="w-8 h-8 rounded-full bg-[var(--surface-2)] border border-[var(--border)] flex items-center justify-center text-xs font-semibold">U</div>}
                    </>
                  ) : (
                    <>
                      {!grouped && <div className="w-8 h-8 rounded-full bg-[var(--surface-2)] border border-[var(--border)] flex items-center justify-center text-xs font-semibold">B</div>}
                      <div className="bubble" dangerouslySetInnerHTML={renderRichText(m.txt)} />
                    </>
                  )}
                </div>
                {m.ts ? <div className="timestamp text-[var(--muted)] text-xs mt-1">{new Date(m.ts).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})}</div> : null}
              </div>
            );
          })}

          {isTyping && (
            <div className="typing-indicator" aria-label="Assistant is typing" aria-live="polite">
              <span></span><span></span><span></span>
            </div>
          )}
        </section>
        <form className="chat-composer" onSubmit={handleSend} aria-label="Send a message">
          <textarea
            name="message"
            placeholder="Message ChargerGPT…"
            aria-label="Message input"
            rows={1}
            autoComplete="off"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            ref={inputRef}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendCurrent(); } }}
          />
          <button type="submit" className="send-btn" aria-label="Send message" disabled={!canSend}>
            Send
            <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M2 21l21-9L2 3v7l15 2-15 2z"/></svg>
          </button>
        </form>
        </div>
      </main>
    </div>
  );
}
