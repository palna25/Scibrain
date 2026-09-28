import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

const ResearchContext = createContext(null);

const RESOURCE_STORAGE_KEY = "scibrain_research_context";
const NOTEBOOK_STORAGE_KEY = "scibrain_notebook_id";
const CHAT_STORAGE_KEY = "scibrain_chat_id";

export function ResearchProvider({ children }) {
  const [selectedResourceIds, setSelectedResourceIds] = useState(() => {
    try {
      const stored = sessionStorage.getItem(RESOURCE_STORAGE_KEY);

      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });

  const [notebookId, setNotebookId] = useState(() => {
    return sessionStorage.getItem(NOTEBOOK_STORAGE_KEY) || null;
  });

  const [chatId, setChatId] = useState(() => {
    return sessionStorage.getItem(CHAT_STORAGE_KEY) || null;
  });

  /*
   * Persist selected resources for the current browser session.
   */
  useEffect(() => {
    sessionStorage.setItem(
      RESOURCE_STORAGE_KEY,
      JSON.stringify(selectedResourceIds)
    );
  }, [selectedResourceIds]);

  /*
   * Persist notebook ID.
   */
  useEffect(() => {
    if (notebookId) {
      sessionStorage.setItem(NOTEBOOK_STORAGE_KEY, notebookId);
    } else {
      sessionStorage.removeItem(NOTEBOOK_STORAGE_KEY);
    }
  }, [notebookId]);

  /*
   * Persist chat ID.
   */
  useEffect(() => {
    if (chatId) {
      sessionStorage.setItem(CHAT_STORAGE_KEY, chatId);
    } else {
      sessionStorage.removeItem(CHAT_STORAGE_KEY);
    }
  }, [chatId]);

  const toggleResource = (resourceId) => {
    const id = String(resourceId);

    setSelectedResourceIds((current) =>
      current.includes(id)
        ? current.filter((item) => item !== id)
        : [...current, id]
    );
  };

  const clearResources = () => {
    setSelectedResourceIds([]);
  };

  const value = useMemo(
    () => ({
      selectedResourceIds,
      setSelectedResourceIds,
      toggleResource,
      clearResources,

      notebookId,
      setNotebookId,

      chatId,
      setChatId,
    }),
    [
      selectedResourceIds,
      notebookId,
      chatId,
    ]
  );

  return (
    <ResearchContext.Provider value={value}>
      {children}
    </ResearchContext.Provider>
  );
}

export function useResearchContext() {
  const context = useContext(ResearchContext);

  if (!context) {
    throw new Error(
      "useResearchContext must be used inside ResearchProvider"
    );
  }

  return context;
}