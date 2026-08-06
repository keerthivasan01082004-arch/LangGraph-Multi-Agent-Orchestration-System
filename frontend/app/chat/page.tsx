import { ChatWindow } from "@/components/ChatWindow";

export default function ChatPage() {
  return (
    <main className="mx-auto flex h-screen max-w-4xl flex-col px-4 py-6">
      <h1 className="mb-4 text-lg font-semibold text-white">Conductor research chat</h1>
      <ChatWindow />
    </main>
  );
}