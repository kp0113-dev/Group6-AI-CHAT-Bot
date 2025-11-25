import React, { useState, useEffect } from "react";
import App from "./App";

function Landing({ onEnter }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const submit = (e) => {
    e.preventDefault();
    // No auth checks — simply navigate to the chat page
    onEnter("/chat");
  };

  return (
    <div className="landing-root">
      <div className="landing-card">
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
