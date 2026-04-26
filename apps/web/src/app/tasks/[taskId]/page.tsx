export default async function TaskPage({ params }: { params: Promise<{ taskId: string }> }) {
  const { taskId } = await params;

  return (
    <main className="mx-auto max-w-5xl p-8">
      <h1 className="text-2xl font-semibold">PDF to PPT Task</h1>
      <p className="text-sm text-gray-600">{taskId}</p>
      <section className="mt-6">
        <h2 className="text-lg font-medium">Status</h2>
        <p className="text-sm text-gray-600">
          Task records and artifact review will appear here as the workflow implementation is added.
        </p>
      </section>
    </main>
  );
}
