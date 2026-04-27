import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { runInNewContext } from "node:vm";
import { createElement, type ComponentType } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, test, vi } from "vitest";
import * as ts from "typescript";

const noop = vi.fn();
const require = createRequire(import.meta.url);

type TaskConversationViewProps = {
  content: string;
  error: string | null;
  pending: boolean;
  onContentChange: (content: string) => void;
  onSendMessage: () => void;
};

function loadTaskConversationView() {
  const sourcePath = join(dirname(fileURLToPath(import.meta.url)), "TaskConversation.tsx");
  const source = readFileSync(sourcePath, "utf8");
  const transpiled = ts.transpileModule(source, {
    compilerOptions: {
      esModuleInterop: true,
      jsx: ts.JsxEmit.ReactJSX,
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020
    }
  });
  const compiledModule = {
    exports: {} as { TaskConversationView?: ComponentType<TaskConversationViewProps> }
  };

  runInNewContext(transpiled.outputText, {
    exports: compiledModule.exports,
    module: compiledModule,
    require
  });

  expect(compiledModule.exports.TaskConversationView).toBeTypeOf("function");
  return compiledModule.exports.TaskConversationView;
}

describe("TaskConversationView", () => {
  test("labels the message textarea and makes it read-only while a send is pending", () => {
    const TaskConversationView = loadTaskConversationView();
    const markup = renderToStaticMarkup(
      createElement(TaskConversationView, {
        content: "Please revise slide 2.",
        error: null,
        pending: true,
        onContentChange: noop,
        onSendMessage: noop
      })
    );

    expect(markup).toContain(
      '<label class="sr-only" for="task-conversation-content">Repair request</label>'
    );
    expect(markup).toMatch(/<textarea[^>]*id="task-conversation-content"[^>]*readOnly/);
  });

  test("announces send errors", () => {
    const TaskConversationView = loadTaskConversationView();
    const markup = renderToStaticMarkup(
      createElement(TaskConversationView, {
        content: "Please revise slide 2.",
        error: "Could not send the message. Please try again.",
        pending: false,
        onContentChange: noop,
        onSendMessage: noop
      })
    );

    expect(markup).toContain(
      '<p class="text-sm text-red-600" role="alert">Could not send the message. Please try again.</p>'
    );
  });
});
