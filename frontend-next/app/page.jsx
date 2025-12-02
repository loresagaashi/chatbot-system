"use client";

import { useEffect, useRef, useState } from "react";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api";

export default function HomePage() {
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);

  const [editingId, setEditingId] = useState(null);
  const [editingOriginalText, setEditingOriginalText] = useState("");

  const historyRef = useRef(null);

  async function handleCreateNewChat() {
    try {
      setError("");
      const res = await fetch(`${API_BASE_URL}/sessions/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({})
      });

      if (!res.ok) {
        const errText = await res.text();
        throw new Error(
          `Failed to create session: ${res.status} ${res.statusText} - ${errText}`
        );
      }

      const created = await res.json();
      setActiveSessionId(created.id);
      setSessions((prev) => [created, ...prev]);
      setHistory([]);
      setChatInput("");
    } catch (err) {
      setError(err.message || "Failed to create new chat");
    }
  }

  async function fetchSessions() {
    try {
      const res = await fetch(`${API_BASE_URL}/sessions/`);
      if (!res.ok) {
        throw new Error(`Failed to fetch sessions: ${res.status}`);
      }
      const data = await res.json();
      setSessions(data);
      if (!activeSessionId && data.length > 0) {
        const firstId = data[0].id;
        setActiveSessionId(firstId);
        fetchMessages(firstId);
      }
    } catch (err) {
      console.error(err);
    }
  }

  async function fetchMessages(sessionId = activeSessionId) {
    if (!sessionId) return;
    try {
      setLoading(true);
      setError("");
      const res = await fetch(
        `${API_BASE_URL}/messages/?session=${sessionId}`
      );
      if (!res.ok) {
        throw new Error(`Failed to fetch messages: ${res.status}`);
      }
      const data = await res.json();
      setHistory(data);
    } catch (err) {
      setError(err.message || "Failed to fetch messages");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchSessions();
  }, []);

  // Always keep the scroll at the bottom so you see the latest messages first.
  useEffect(() => {
    if (!historyRef.current) return;
    historyRef.current.scrollTop = historyRef.current.scrollHeight;
  }, [history]);

  function beginEditMessage(message) {
    if (!message || message.role !== "user" || typeof message.id !== "number") {
      return;
    }
    setEditingId(message.id);
    setEditingOriginalText(message.text);
    setChatInput(message.text);
  }

  function cancelEdit() {
    setEditingId(null);
    setEditingOriginalText("");
    setChatInput("");
  }

  async function handleDeleteMessage(id) {
    if (typeof id !== "number") return;
    const confirmed = window.confirm("Delete this message?");
    if (!confirmed) return;

    try {
      setError("");
      const res = await fetch(`${API_BASE_URL}/messages/${id}/`, {
        method: "DELETE"
      });

      if (!res.ok && res.status !== 204) {
        throw new Error(`Failed to delete message: ${res.status}`);
      }

      setHistory((prev) => prev.filter((m) => m.id !== id));
    } catch (err) {
      setError(err.message || "Failed to delete message");
    }
  }

  async function sendNewChatMessage() {
    if (!chatInput.trim()) return;

    try {
      setChatLoading(true);
      setError("");

      let sessionId = activeSessionId;

      // If there's no active session yet, create one now.
      if (!sessionId) {
        const sessionRes = await fetch(`${API_BASE_URL}/sessions/`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({})
        });
        if (!sessionRes.ok) {
          const errText = await sessionRes.text();
          throw new Error(
            `Failed to create session: ${sessionRes.status} ${sessionRes.statusText} - ${errText}`
          );
        }
        const created = await sessionRes.json();
        sessionId = created.id;
        setActiveSessionId(created.id);
        // Let this session appear in the history list.
        setSessions((prev) => [created, ...prev]);
      }

      const res = await fetch(`${API_BASE_URL}/chat/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ message: chatInput, session: sessionId })
      });

      if (!res.ok) {
        const errText = await res.text();
        throw new Error(
          `Chat request failed: ${res.status} ${res.statusText} - ${errText}`
        );
      }

      const data = await res.json();
      // Ask backend for the latest history for this session so we always
      // display the canonical conversation from the database.
      await fetchMessages(sessionId);
      setChatInput("");
    } catch (err) {
      setError(err.message || "Failed to send chat message");
    } finally {
      setChatLoading(false);
    }
  }

  async function saveEditedMessage() {
    if (!editingId || !chatInput.trim()) return;

    const newText = chatInput;

    try {
      setChatLoading(true);
      setError("");

      const res = await fetch(`${API_BASE_URL}/messages/${editingId}/`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ text: newText })
      });

      if (!res.ok) {
        const errText = await res.text();
        throw new Error(
          `Update failed: ${res.status} ${res.statusText} - ${errText}`
        );
      }

      const updated = await res.json();
      setHistory((prev) =>
        prev.map((m) => (m.id === updated.id ? updated : m))
      );

      // Ask the backend to generate a new assistant reply for this edited message.
      // The backend also removes all later messages so the conversation is
      // effectively restarted from this edited question.
      try {
        const regenRes = await fetch(
          `${API_BASE_URL}/messages/${updated.id}/regenerate/`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json"
            }
          }
        );

        if (regenRes.ok) {
          // After regeneration, reload the full history from the server so
          // we see the conversation from the beginning up to the new answer.
          await fetchMessages(updated.session);
        } else {
          const errText = await regenRes.text();
          console.error("Regenerate failed:", regenRes.status, errText);
        }
      } catch (e) {
        console.error("Regenerate request error:", e);
      }

      setEditingId(null);
      setEditingOriginalText("");
      setChatInput("");
    } catch (err) {
      setError(err.message || "Failed to update message");
    } finally {
      setChatLoading(false);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (editingId) {
      await saveEditedMessage();
    } else {
      await sendNewChatMessage();
    }
  }

  return (
    <main
      style={{
        minHeight: "100vh",
        display: "flex",
        fontFamily:
          "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
      }}
    >
      {/* Left sidebar: chat sessions history */}
      <aside
        style={{
          width: "260px",
          borderRight: "1px solid #e5e7eb",
          padding: "1rem 0.75rem",
          boxSizing: "border-box",
          backgroundColor: "#f9fafb"
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "0.5rem",
            marginBottom: "0.75rem"
          }}
        >
          <h2
            style={{
              fontSize: "1rem",
              margin: 0
            }}
          >
            History
          </h2>
          <button
            type="button"
            onClick={handleCreateNewChat}
            style={{
              borderRadius: "9999px",
              border: "1px solid #d4d4d8",
              backgroundColor: "white",
              padding: "0.2rem 0.6rem",
              fontSize: "0.75rem",
              cursor: "pointer",
              color: "#111827"
            }}
          >
            + New
          </button>
        </div>
        <div
          style={{
            fontSize: "0.8rem",
            color: "#6b7280",
            marginBottom: "0.75rem"
          }}
        >
          Select a previous chat, or start a new one by sending a message.
        </div>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "0.25rem",
            maxHeight: "calc(100vh - 5rem)",
            overflowY: "auto"
          }}
        >
          {sessions.map((s) => {
            const isActive = s.id === activeSessionId;
            const label = s.title || `Chat #${s.id}` || "Untitled chat";
            return (
              <button
                key={s.id}
                type="button"
                onClick={() => {
                  setActiveSessionId(s.id);
                  fetchMessages(s.id);
                }}
                style={{
                  textAlign: "left",
                  padding: "0.5rem 0.6rem",
                  borderRadius: "0.5rem",
                  border: "none",
                  backgroundColor: isActive ? "#e5e7eb" : "transparent",
                  cursor: "pointer",
                  fontSize: "0.85rem",
                  color: "#111827"
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: "0.4rem"
                  }}
                >
                  <div>
                    <div
                      style={{
                        fontWeight: isActive ? 600 : 500,
                        marginBottom: "0.1rem"
                      }}
                    >
                      {label}
                    </div>
                    {s.created && (
                      <div
                        style={{
                          fontSize: "0.7rem",
                          color: "#6b7280"
                        }}
                      >
                        {new Date(s.created).toLocaleString()}
                      </div>
                    )}
                  </div>
                  <span
                    onClick={(e) => {
                      e.stopPropagation();
                      const confirmed = window.confirm(
                        "Delete this chat and its messages?"
                      );
                      if (!confirmed) return;
                      (async () => {
                        try {
                          const delRes = await fetch(
                            `${API_BASE_URL}/sessions/${s.id}/`,
                            { method: "DELETE" }
                          );
                          if (!delRes.ok && delRes.status !== 204) {
                            const errText = await delRes.text();
                            throw new Error(
                              `Failed to delete session: ${delRes.status} ${delRes.statusText} - ${errText}`
                            );
                          }
                          setSessions((prev) =>
                            prev.filter((sess) => sess.id !== s.id)
                          );
                          if (activeSessionId === s.id) {
                            setActiveSessionId(null);
                            setHistory([]);
                          }
                        } catch (err) {
                          console.error(err);
                          setError(
                            err.message || "Failed to delete chat session"
                          );
                        }
                      })();
                    }}
                    style={{
                      fontSize: "0.9rem",
                      opacity: 0.8,
                      cursor: "pointer"
                    }}
                  >
                    ✕
                  </span>
                </div>
              </button>
            );
          })}
          {sessions.length === 0 && (
            <div style={{ fontSize: "0.8rem", color: "#9ca3af" }}>
              No previous chats yet.
            </div>
          )}
        </div>
      </aside>

      {/* Right side: chat window */}
      <section
        style={{
          flex: 1,
          maxWidth: "960px",
          margin: "0 auto",
          padding: "1.5rem 1rem 6rem",
          boxSizing: "border-box"
        }}
      >
        <h1 style={{ marginBottom: "1rem" }}>Chat with Your Assistant</h1>
        <p style={{ color: "#555", marginBottom: "1.5rem", fontSize: "0.9rem" }}>
          Active chat ID:{" "}
          <code>{activeSessionId ?? "creating…"}</code>
        </p>

        <div>
          <h2 style={{ marginBottom: "0.75rem" }}>Chat history</h2>
          {error && (
            <div
              style={{
                backgroundColor: "#fee2e2",
                color: "#b91c1c",
                padding: "0.75rem 1rem",
                borderRadius: "0.5rem",
                marginBottom: "1rem"
              }}
            >
              {error}
            </div>
          )}
          <div
            ref={historyRef}
            style={{
              padding: "1rem",
              borderRadius: "0.75rem",
              backgroundColor: "white",
              border: "1px solid #e5e7eb",
              height: "60vh",
              maxHeight: "520px",
              overflowY: "auto",
              display: "flex",
              flexDirection: "column",
              gap: "0.5rem"
            }}
          >
            {loading && <p style={{ color: "#6b7280" }}>Loading history…</p>}
            {!loading && history.length === 0 && (
              <p style={{ color: "#6b7280" }}>
                No messages yet. Start the conversation!
              </p>
            )}
            {history.map((m) => (
              <div
                key={m.id}
                style={{
                  alignSelf: m.role === "user" ? "flex-end" : "flex-start",
                  maxWidth: "80%",
                  padding: "0.5rem 0.75rem",
                  borderRadius: "0.75rem",
                  backgroundColor: m.role === "user" ? "#2563eb" : "#e5e7eb",
                  color: m.role === "user" ? "white" : "#111827",
                  whiteSpace: "pre-wrap"
                }}
              >
                <div
                  style={{
                    fontSize: "0.7rem",
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                    opacity: 0.8,
                    marginBottom: "0.15rem"
                  }}
                >
                  {m.role === "user" ? "You" : "Assistant"}
                </div>
                <div>{m.text}</div>
                {m.created && (
                  <div
                    style={{
                      marginTop: "0.2rem",
                      fontSize: "0.7rem",
                      opacity: 0.7,
                      textAlign: m.role === "user" ? "right" : "left"
                    }}
                  >
                    {new Date(m.created).toLocaleTimeString()}
                  </div>
                )}
                {m.role === "user" && typeof m.id === "number" && (
                  <div
                    style={{
                      marginTop: "0.25rem",
                      display: "flex",
                      gap: "0.5rem",
                      fontSize: "0.75rem",
                      opacity: 0.85,
                      justifyContent: "flex-end"
                    }}
                  >
                    <button
                      type="button"
                      onClick={() => beginEditMessage(m)}
                      style={{
                        border: "none",
                        background: "transparent",
                        color: "inherit",
                        cursor: "pointer",
                        textDecoration: "underline"
                      }}
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDeleteMessage(m.id)}
                      style={{
                        border: "none",
                        background: "transparent",
                        color: "inherit",
                        cursor: "pointer",
                        textDecoration: "underline"
                      }}
                    >
                      Delete
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Fixed input bar at the bottom of the screen */}
        <div
          style={{
            position: "fixed",
            left: 0,
            right: 0,
            bottom: 0,
            borderTop: "1px solid #e5e7eb",
            backgroundColor: "#f9fafb"
          }}
        >
          <div
            style={{
              maxWidth: "960px",
              margin: "0 auto",
              padding: "0.75rem 1rem"
            }}
          >
            <form
              onSubmit={handleSubmit}
              style={{
                display: "flex",
                gap: "0.75rem",
                alignItems: "flex-end"
              }}
            >
            <textarea
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              placeholder="Type a message..."
              rows={2}
              style={{
                flex: 1,
                padding: "0.6rem 0.75rem",
                borderRadius: "0.75rem",
                border: "1px solid #d4d4d8",
                resize: "none",
                fontFamily: "inherit",
                fontSize: "0.95rem"
              }}
            />
            {editingId && (
              <div
                style={{
                  position: "absolute",
                  bottom: "100%",
                  left: 0,
                  right: 0,
                  marginBottom: "0.25rem",
                  fontSize: "0.8rem",
                  color: "#4b5563"
                }}
              >
                Editing your message{" "}
                <span style={{ opacity: 0.7 }}>
                  (press Cancel to stop editing)
                </span>
              </div>
            )}
            <button
              type="submit"
              disabled={chatLoading}
              style={{
                padding: "0.6rem 1.1rem",
                borderRadius: "9999px",
                border: "none",
                backgroundColor: chatLoading ? "#9ca3af" : "#16a34a",
                color: "white",
                cursor: chatLoading ? "not-allowed" : "pointer",
                whiteSpace: "nowrap",
                fontWeight: 500
              }}
            >
              {chatLoading
                ? "Saving…"
                : editingId
                ? "Save"
                : "Send"}
            </button>
            {editingId && (
              <button
                type="button"
                onClick={cancelEdit}
                style={{
                  padding: "0.6rem 0.9rem",
                  borderRadius: "9999px",
                  border: "1px solid #d4d4d8",
                  backgroundColor: "white",
                  color: "#111827",
                  cursor: "pointer",
                  whiteSpace: "nowrap",
                  fontWeight: 500
                }}
              >
                Cancel
              </button>
            )}
          </form>
        </div>
        </div>
      </section>
    </main>
  );
}


