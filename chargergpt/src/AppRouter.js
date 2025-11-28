import React, { useState, useEffect } from "react";
import App from "./App";

function Landing({ onEnter }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [theme, setTheme] = useState("theme-auto");

  useEffect(() => {
    try {
      const t = localStorage.getItem("chat-theme");
      if (t) setTheme(t);
    } catch {}
  }, []);

  const toggleTheme = () => {
    const seq = ["theme-dark", "theme-light"];
    const idx = seq.indexOf(theme);
    const next = seq[(idx + 1) % seq.length];
    setTheme(next);
    try {
      localStorage.setItem("chat-theme", next);
    } catch {}
  };

  const submit = (e) => {
    e.preventDefault();
    // No auth checks — simply navigate to the chat page
    onEnter("/chat");
  };

  return (
    <div className={`landing-root ${theme}`}>
      <div className="logo-container">
        <img src="/UAH_LOGO.png" alt="Logo" />
      </div>
      <div className="landing-card">
        <div className="landing-actions">
          <button
            className="icon-btn theme-toggle"
            aria-label="Toggle dark mode"
            onClick={toggleTheme}
          >
            <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
              <path d="M6.76 4.84l-1.8-1.79L3.17 4.84l1.79 1.79zM1 13h3v-2H1zm10 10h2v-3h-2zM4.22 19.78l1.79-1.79-1.8-1.79-1.79 1.79zM20 11V9h3v2zm-1.76-6.16l-1.79 1.79 1.8 1.79 1.79-1.79zM12 6a6 6 0 100 12 6 6 0 000-12z" />
            </svg>
          </button>
        </div>
        <h1 className="landing-title">Welcome to ChargerGPT</h1>
        <p className="landing-sub">Sign in to access campus help and directions</p>

        <form className="login-form" onSubmit={submit} aria-label="Login form">
          <div className="login-fields">
            <label className="login-label" htmlFor="username">Username:</label>
            <input
              id="username"
              className="login-input"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter username"
              autoComplete="username"
            />

            <label className="login-label" htmlFor="password">Password:</label>
            <input
              id="password"
              className="login-input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter password"
              autoComplete="current-password"
            />
          </div>
          <div className="button-row">
            <button className="login-btn" type="submit">Login</button>
            <button className="register-btn">Register</button>
          </div>
          <button className="guest-btn">Guest Access</button>
        </form>
      </div>
      <footer className="landing-footer">No account required for demo — this is UI only.</footer>
    </div>
  );
}

export default function AppRouter() {
  const [route, setRoute] = useState(window.location.pathname || "/");

  useEffect(() => {
    const onPop = () => setRoute(window.location.pathname || "/");
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const navigate = (path) => {
    if (path === window.location.pathname) {
      setRoute(path);
      return;
    }
    window.history.pushState({}, "", path);
    setRoute(path);
  };

  // If user goes to /chat render the App, otherwise show Landing
  if (route === "/chat") {
    return <App />;
  }

  return <Landing onEnter={navigate} />;
}
