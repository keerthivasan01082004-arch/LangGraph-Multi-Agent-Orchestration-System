"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

import useAccessToken from "@/lib/auth-hook";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  metadata: Record<string, unknown>;
};

export function ChatWindow() {
  const token = useAccessToken();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [activeAgent, setActiveAgent] = useState<string | null>(null);
  const [matching, setMatching] = useState(false);
  const conversationRef = useRef<string | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, activeAgent]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!draft.trim() || !token) return;
    const content = draft;
    setDraft("");
    setMatching(true);
    setMessages((m) => [...m, { id: crypto.randomUUID(), role: "user", content, metadata: {} }]);

    try {
      const conv = await fetch(`${API_URL}/conversations`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` }
      });
      conversationRef.current = (await conv.json()).id;
    } catch {
      // Fallback to placeholder while backend is offline in dev.
    }

    try {
      const resp = await fetch(
        `${API_URL}/conversations/${conversationRef.current ?? "0"}/messages/stream?content=${encodeURIComponent(content)}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      const reader = resp.body?.getReader();
      if (!reader) return;
      const decoder = new TextDecoder();
      let answer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        for (const block of decoder.decode(value, { stream: true }).split("\n\n")) {
          if (!block.startsWith("data: ")) continue;
          const event = JSON.parse(block.slice(6));
          if (event.type === "agent.started") {
            setActiveAgent(event.agent);
          } else if (event.type === "token") {
            answer += event.delta;
            setMessages((m) => {
              const copy = [...m];
              if (copy[copy.length - 1]?.role === "assistant") {
                copy[copy.length - 1] = { ...copy[copy.length - 1], content: answer };
              } else {
                copy.push({ id: crypto.randomUUID(), role: "assistant", content: answer, metadata: {} });
              }
              return copy;
            });
          }
        }
      }
    } finally {
      setMatching(false);
      setActiveAgent(null);
    }
  }

  return (
    <div className="flex h-full flex-col gap-4">
      <div className="flex-1 space-y-4 overflow-y-auto pr-2">
        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}
        {matching && <MatchingBadge agent={activeAgent} />}
        <div ref={bottomRef} />
      </div>
      <form onSubmit={onSubmit} className="flex gap-3">
        <input
          className="flex-1 rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-slate-100 placeholder-slate-500"
          placeholder="Ask a deep research question…"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          disabled={!token}
        />
        <button
          type="submit"
          disabled={!token || !draft.trim()}
          className="rounded-lg bg-indigo-600 px-5 py-2 font-medium text-white hover:bg-indigo-500 disabled:opacity-40"
        >
          Send
        </button>
      </form>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] whitespace-pre-wrap rounded-2xl px-4 py-2 text-sm leading-relaxed ${
          isUser ? "bg-indigo-600 text-white" : "bg-slate-800 text-slate-100"
        }`}
      >
        {message.content}
      </div>
    </div>
  );
}

function MatchingBadge({ agent }: { agent: string | null }) {
  const label = agent ? `${agent} agent working…` : "Orchestrating…";
  return (
    <div className="flex items-center gap-2 text-sm text-slate-400">
      <span className="h-2 w-2 animate-pulse rounded-full bg-indigo-400" />
      {label}
    </div>
  );
}