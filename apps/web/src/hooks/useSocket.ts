import { useEffect, useRef, useCallback } from 'react';

export const useSocket = (roomId: string, onMessage: (data: any) => void) => {
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!roomId) return;

    // Note: Port 8787 is used by the backend script
    const ws = new WebSocket(`ws://localhost:8787/ws/${roomId}`);
    socketRef.current = ws;

    ws.onopen = () => {
      console.log('Connected to WebSocket room:', roomId);
    };

    ws.onmessage = (event) => {
      try {
        const data = event.data;
        onMessage(data);
      } catch (e) {
        console.error("Socket message error", e);
      }
    };

    ws.onclose = () => {
      console.log('Disconnected from WebSocket');
    };

    return () => {
      ws.close();
    };
  }, [roomId, onMessage]);

  const sendMessage = useCallback((message: string | object) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      const payload = typeof message === 'string' ? message : JSON.stringify(message);
      socketRef.current.send(payload);
    }
  }, []);

  return { sendMessage };
};
