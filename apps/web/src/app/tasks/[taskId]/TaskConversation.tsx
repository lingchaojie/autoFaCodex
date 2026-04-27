"use client";

import { useState } from "react";

const textareaId = "task-conversation-content";

type TaskConversationViewProps = {
  content: string;
  error: string | null;
  pending: boolean;
  onContentChange: (content: string) => void;
  onSendMessage: () => void;
};

export default function TaskConversation({ taskId }: { taskId: string }) {
  const [content, setContent] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const trimmedContent = content.trim();

  async function sendMessage() {
    if (!trimmedContent || pending) return;

    setPending(true);
    setError(null);

    try {
      const response = await fetch(`/api/tasks/${taskId}/messages`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ content })
      });

      if (!response.ok) {
        throw new Error("Failed to send message");
      }

      setContent("");
    } catch {
      setError("Could not send the message. Please try again.");
    } finally {
      setPending(false);
    }
  }

  return (
    <TaskConversationView
      content={content}
      error={error}
      pending={pending}
      onContentChange={setContent}
      onSendMessage={sendMessage}
    />
  );
}

export function TaskConversationView({
  content,
  error,
  pending,
  onContentChange,
  onSendMessage
}: TaskConversationViewProps) {
  return (
    <section className="grid gap-3 rounded border p-4">
      <h2 className="text-lg font-medium">Conversation</h2>
      <label className="sr-only" htmlFor={textareaId}>
        Repair request
      </label>
      <textarea
        id={textareaId}
        className="min-h-28 rounded border p-3"
        readOnly={pending}
        value={content}
        onChange={(event) => onContentChange(event.target.value)}
        placeholder="Describe what still looks wrong or what should be more editable."
      />
      {error ? (
        <p className="text-sm text-red-600" role="alert">
          {error}
        </p>
      ) : null}
      <button
        className="w-fit rounded bg-black px-4 py-2 text-white disabled:opacity-50"
        disabled={pending || !content.trim()}
        onClick={onSendMessage}
        type="button"
      >
        {pending ? "Sending..." : "Send repair request"}
      </button>
    </section>
  );
}
