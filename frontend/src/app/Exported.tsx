// "Saved to C:\...\file.docx · Show in folder" after an export (14i).

import { errorMessage, getApi } from "../bridge/bridge";
import { useState } from "react";

export function Exported({ what, path }: { what: string; path: string }) {
  const [error, setError] = useState<string | null>(null);
  const show = () =>
    getApi()
      .then((api) => api.show_in_folder(path))
      .catch((e) => setError(errorMessage(e)));
  return (
    <p className="hint exported" role="status">
      {what} saved to <span className="path-inline">{path}</span>{" "}
      <button type="button" className="link-button" onClick={() => void show()}>
        Show in folder
      </button>
      {error && <span className="error"> {error}</span>}
    </p>
  );
}
