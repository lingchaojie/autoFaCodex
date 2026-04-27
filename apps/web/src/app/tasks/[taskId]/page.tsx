import TaskConversation from "./TaskConversation";

export default async function TaskPage({ params }: { params: Promise<{ taskId: string }> }) {
  const { taskId } = await params;

  return (
    <main className="mx-auto grid max-w-6xl gap-6 p-8">
      <header>
        <h1 className="text-2xl font-semibold">PDF to PPT Task</h1>
        <p className="text-sm text-gray-600">{taskId}</p>
      </header>
      <section className="grid gap-3 rounded border p-4">
        <h2 className="text-lg font-medium">Artifacts and Validator Report</h2>
        <p className="text-sm text-gray-600">
          Generated files, validator findings, and report details will appear here after the
          workflow writes review artifacts.
        </p>
      </section>
      <TaskConversation taskId={taskId} />
    </main>
  );
}
