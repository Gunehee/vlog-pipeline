import React, { useEffect, useState, useCallback } from "react";
import Library from "./Library.jsx";
import Studio from "./Studio.jsx";

function parseHash() {
  const m = window.location.hash.match(/^#\/run\/(.+)$/);
  return m ? decodeURIComponent(m[1]) : null;
}

export default function App() {
  const [runName, setRunName] = useState(parseHash());

  useEffect(() => {
    const onHash = () => setRunName(parseHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const openRun = useCallback((name) => {
    window.location.hash = `#/run/${encodeURIComponent(name)}`;
  }, []);
  const goLibrary = useCallback(() => {
    window.location.hash = "";
  }, []);

  return runName ? (
    <Studio key={runName} runName={runName} onBack={goLibrary} />
  ) : (
    <Library onOpen={openRun} />
  );
}
