import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';

const STORAGE_KEY = 'test_chat_active_id';

const TestChatContext = createContext({
    activeTestChatId: null,
    setActiveTestChatId: () => {},
    toggleTestChat: () => {},
    isTestChatOpen: false,
});

export const useTestChat = () => useContext(TestChatContext);

const readStoredId = () => {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return null;
        const parsed = parseInt(raw, 10);
        return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
    } catch {
        return null;
    }
};

export const TestChatProvider = ({ children }) => {
    const [activeTestChatId, setActiveTestChatIdState] = useState(() => readStoredId());

    const setActiveTestChatId = useCallback((id) => {
        const next = (id === null || id === undefined) ? null : (Number.isFinite(id) ? Number(id) : null);
        setActiveTestChatIdState(next);
        try {
            if (next) {
                localStorage.setItem(STORAGE_KEY, String(next));
            } else {
                localStorage.removeItem(STORAGE_KEY);
            }
        } catch {
            // localStorage may be unavailable (private mode, quota); fail silently
        }
    }, []);

    const toggleTestChat = useCallback((chatbotId) => {
        setActiveTestChatIdState(prev => {
            const next = prev === chatbotId ? null : chatbotId;
            try {
                if (next) {
                    localStorage.setItem(STORAGE_KEY, String(next));
                } else {
                    localStorage.removeItem(STORAGE_KEY);
                }
            } catch {
                // ignore
            }
            return next;
        });
    }, []);

    // Cross-tab sync: if the user toggles a test chat in another tab, mirror it.
    useEffect(() => {
        const onStorage = (e) => {
            if (e.key === STORAGE_KEY) {
                setActiveTestChatIdState(readStoredId());
            }
        };
        window.addEventListener('storage', onStorage);
        return () => window.removeEventListener('storage', onStorage);
    }, []);

    return (
        <TestChatContext.Provider
            value={{
                activeTestChatId,
                setActiveTestChatId,
                toggleTestChat,
                isTestChatOpen: activeTestChatId !== null,
            }}
        >
            {children}
        </TestChatContext.Provider>
    );
};
