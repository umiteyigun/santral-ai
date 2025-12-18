"use client";

import {
    LiveKitRoom,
    RoomAudioRenderer,
    ControlBar,
    AudioConference,
    LayoutContextProvider,
    RoomContext,
} from "@livekit/components-react";
import "@livekit/components-styles";
import { useEffect, useState, useContext, useRef, useCallback } from "react";
import { RemoteParticipant } from "livekit-client";

interface Message {
    type: string;
    user_text?: string;
    agent_text?: string;
    audio_base64?: string;
    timestamp?: string;
}

export default function Home() {
    const [token, setToken] = useState("");
    const [url, setUrl] = useState("");
    const [isConnecting, setIsConnecting] = useState(false);
    const [isConnected, setIsConnected] = useState(false);
    const [hasUserInteracted, setHasUserInteracted] = useState(false);
    const [micPermission, setMicPermission] = useState<"granted" | "denied" | "prompt" | null>(null);
    const [isStarting, setIsStarting] = useState(false);
    const [messages, setMessages] = useState<Message[]>([]);
    const [roomName, setRoomName] = useState("");

    const requestMicrophonePermission = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            setMicPermission("granted");
            // Stop the stream immediately, we just needed permission
            stream.getTracks().forEach(track => track.stop());
            return true;
        } catch (error: any) {
            console.error("Microphone permission error:", error);
            if (error.name === "NotAllowedError" || error.name === "PermissionDeniedError") {
                setMicPermission("denied");
            } else {
                setMicPermission("prompt");
            }
            return false;
        }
    };

    const handleConnect = async () => {
        // Request microphone permission first
        const permissionGranted = await requestMicrophonePermission();
        if (!permissionGranted) {
            return;
        }

        setIsStarting(true);
        setIsConnecting(true);

        try {
            // Start chat: create room, dispatch agent, get token
            const resp = await fetch("/api/start-chat?name=Kullanici", {
                method: 'POST'
            });
            const data = await resp.json();
            
            if (data.error) {
                console.error("Error starting chat:", data.error);
                alert("Sohbet başlatılamadı: " + data.error);
                setIsStarting(false);
                setIsConnecting(false);
                return;
            }

            console.log("Chat started:", data);
            if (data.token) {
                setToken(data.token);
                setUrl(data.serverUrl || "wss://localhost/livekit");
                setRoomName(data.roomName || "");
                setHasUserInteracted(true);
                setIsConnected(true);
            } else {
                console.error("No token in response");
                alert("Token alınamadı");
            }
        } catch (e) {
            console.error("Error starting chat:", e);
            alert("Sohbet başlatılırken hata oluştu");
        } finally {
            setIsStarting(false);
            setIsConnecting(false);
        }
    };

    if (isConnecting || isStarting) {
        return (
            <div className="loading-container">
                <div className="loading-spinner"></div>
                <p className="loading-text">
                    {isStarting ? "Oda oluşturuluyor ve agent çağrılıyor..." : "Sohbet bağlantısı kuruluyor..."}
                </p>
            </div>
        );
    }

    if (!hasUserInteracted || token === "" || url === "") {
        return (
            <div className="chat-container">
                <div className="chat-header">
                    <h1>🎤 Sesli Sohbet</h1>
                    <p>Ollama ile yapay zeka asistanı</p>
                    {micPermission === "denied" && (
                        <p style={{ color: "#ef4444", fontSize: "0.9rem", marginTop: "10px" }}>
                            ⚠️ Mikrofon izni reddedildi. Lütfen tarayıcı ayarlarından mikrofon iznini verin.
                        </p>
                    )}
                </div>
                <button 
                    className="start-button" 
                    onClick={handleConnect}
                    disabled={isStarting}
                >
                    {micPermission === "denied" ? "Tekrar Dene" : "Sohbete Başla"}
                </button>
            </div>
        );
    }

    return (
        <LayoutContextProvider>
            <LiveKitRoom
                video={false}
                audio={true}
                token={token}
                serverUrl={url}
                connect={isConnected}
                options={{
                    publishDefaults: {
                        audioPreset: {
                            maxBitrate: 128000, // Increased from 32k to 128k for better quality
                        },
                    },
                }}
                onConnected={() => {
                    console.log("✅ Connected to LiveKit");
                    setIsConnected(true);
                }}
                onDisconnected={() => {
                    console.log("Disconnected from LiveKit");
                    setIsConnected(false);
                }}
                onError={(error) => {
                    console.error("LiveKit error:", error);
                }}
            >
                <ChatContent messages={messages} setMessages={setMessages} roomName={roomName} />
            </LiveKitRoom>
        </LayoutContextProvider>
    );
}

function ChatContent({ messages, setMessages, roomName }: { messages: Message[], setMessages: (msgs: Message[] | ((prev: Message[]) => Message[])) => void, roomName: string }) {
    const room = useContext(RoomContext);
    
    // Poll for messages from HTTP endpoint
    useEffect(() => {
        if (!roomName) {
            console.log("⚠️ No roomName, skipping polling");
            return;
        }
        
        console.log("🔄 Starting polling for room:", roomName);
        
        const pollInterval = setInterval(async () => {
            try {
                const resp = await fetch(`/api/agent-message?room=${encodeURIComponent(roomName)}`);
                if (!resp.ok) {
                    console.error("❌ Polling response not OK:", resp.status, resp.statusText);
                    return;
                }
                const data = await resp.json();
                console.log("📡 Polling response:", { messageCount: data.messages?.length || 0, hasMessages: !!data.messages });
                if (data.messages && data.messages.length > 0) {
                    console.log("📬 Received messages via HTTP:", data.messages.length);
                    data.messages.forEach((msg: Message) => {
                        console.log("✅ Adding message from HTTP:", {
                            type: msg.type,
                            hasUserText: !!msg.user_text,
                            hasAgentText: !!msg.agent_text,
                            hasAudio: !!msg.audio_base64,
                            audioLength: msg.audio_base64?.length || 0
                        });
                        setMessages(prev => {
                            // Check if message already exists (avoid duplicates)
                            const exists = prev.some(m => 
                                m.timestamp === msg.timestamp && 
                                m.agent_text === msg.agent_text
                            );
                            if (exists) {
                                console.log("⚠️ Message already exists, skipping");
                                return prev;
                            }
                            return [...prev, msg];
                        });
                    });
                }
            } catch (e) {
                console.error("❌ Error polling messages:", e);
            }
        }, 500); // Poll every 500ms for faster response
        
        return () => {
            console.log("🛑 Stopping polling");
            clearInterval(pollInterval);
        };
    }, [roomName, setMessages]);
    
    useEffect(() => {
        if (!room) {
            console.log("⚠️ Room not available yet");
            return;
        }
        
        console.log("✅ Room available, setting up data channel listener");
        
        const handleDataReceived = (payload: Uint8Array, participant?: RemoteParticipant, kind?: any, topic?: string) => {
            console.log("📨 Data received:", { 
                topic, 
                participant: participant?.identity, 
                payloadLength: payload.length,
                kind,
                hasPayload: !!payload
            });
            
            // Try to parse regardless of topic first to see what we're getting
            try {
                const decoded = new TextDecoder().decode(payload);
                console.log("📝 Decoded payload:", decoded.substring(0, 100));
                
                if (topic === "agent-messages" || decoded.includes("agent_response")) {
                    const message: Message = JSON.parse(decoded);
                    console.log("✅ Received agent message:", message);
                    console.log("📊 Message details:", {
                        type: message.type,
                        hasUserText: !!message.user_text,
                        hasAgentText: !!message.agent_text,
                        hasAudio: !!message.audio_base64,
                        audioLength: message.audio_base64?.length || 0
                    });
                    setMessages(prev => {
                        console.log(`📬 Adding message to list. Current count: ${prev.length}, New count: ${prev.length + 1}`);
                        return [...prev, message];
                    });
                } else {
                    console.log("⚠️ Ignoring data with topic:", topic);
                }
            } catch (e) {
                console.error("❌ Error parsing message:", e, "Raw payload:", payload);
            }
        };
        
        // Also listen for data channel events
        const handleDataChannel = (channel: RTCDataChannel) => {
            console.log("📡 Data channel opened:", channel.label);
            channel.onmessage = (event) => {
                console.log("📨 Data channel message received:", event.data);
                try {
                    const message: Message = typeof event.data === 'string' 
                        ? JSON.parse(event.data)
                        : JSON.parse(new TextDecoder().decode(event.data));
                    console.log("✅ Data channel message:", message);
                    setMessages(prev => [...prev, message]);
                } catch (e) {
                    console.error("❌ Error parsing data channel message:", e);
                }
            };
        };
        
        // Listen for dataReceived event
        room.on("dataReceived", handleDataReceived);
        
        // Also try to listen on all participants for data
        // Listen for new participants (just for logging)
        const handleParticipantConnected = (participant: RemoteParticipant) => {
            console.log("👤 Participant connected:", participant.identity);
        };
        
        room.on("participantConnected", handleParticipantConnected);
        
        // Check if room has data channels
        console.log("🔍 Room state:", {
            name: room.name,
            participants: room.participants.size,
            localParticipant: room.localParticipant?.identity,
            participantIdentities: Array.from(room.participants.values()).map(p => p.identity)
        });
        
        return () => {
            room.off("dataReceived", handleDataReceived);
            room.off("participantConnected", handleParticipantConnected);
        };
    }, [room, setMessages]);
    
    return (
        <div className="chat-container">
            <div className="chat-header">
                <h1>🎤 Sesli Sohbet</h1>
                <p>
                    <span className={`status-dot connected`}></span>
                    Bağlı
                </p>
            </div>
            
            {/* Messages display */}
            <div className="messages-container" style={{
                flex: 1,
                overflowY: 'auto',
                padding: '20px',
                maxHeight: '400px',
                borderBottom: '1px solid #e0e0e0',
                backgroundColor: '#fafafa'
            }}>
                {(() => {
                    console.log("🔄 Rendering messages. Count:", messages.length, "Messages:", messages);
                    return messages.length === 0 ? (
                        <p style={{ color: '#999', textAlign: 'center', padding: '20px' }}>
                            Henüz mesaj yok. Konuşmaya başlayın...
                        </p>
                    ) : (
                        messages.map((msg, idx) => {
                            console.log(`📝 Rendering message ${idx}:`, msg);
                            return <MessageBubble key={idx} message={msg} />;
                        })
                    );
                })()}
            </div>
            
            <AudioConference />
            <RoomAudioRenderer />
            <ControlBar />
        </div>
    );
}

function MessageBubble({ message }: { message: Message }) {
    const [isPlaying, setIsPlaying] = useState(false);
    const audioRef = useRef<HTMLAudioElement | null>(null);
    const hasAutoPlayed = useRef(false);

    const handlePlayAudio = useCallback(() => {
        if (message.audio_base64 && !isPlaying) {
            try {
                console.log("🎵 Starting audio playback...");
                // Convert base64 to blob and create audio URL
                const audioData = Uint8Array.from(atob(message.audio_base64), c => c.charCodeAt(0));
                console.log("📦 Audio data size:", audioData.length, "bytes");
                const blob = new Blob([audioData], { type: 'audio/wav' });
                const audioUrl = URL.createObjectURL(blob);
                console.log("🔗 Audio URL created:", audioUrl.substring(0, 50) + "...");
                
                const audio = new Audio(audioUrl);
                audioRef.current = audio;
                setIsPlaying(true);
                
                audio.onloadeddata = () => {
                    console.log("✅ Audio loaded, duration:", audio.duration);
                };
                
                audio.onended = () => {
                    console.log("✅ Audio playback ended");
                    setIsPlaying(false);
                    URL.revokeObjectURL(audioUrl);
                };
                
                audio.onerror = (e) => {
                    console.error("❌ Audio playback error:", e, audio.error);
                    setIsPlaying(false);
                    URL.revokeObjectURL(audioUrl);
                };
                
                audio.play().then(() => {
                    console.log("✅ Audio play() succeeded");
                }).catch((error) => {
                    console.error("❌ Audio play() failed:", error);
                    setIsPlaying(false);
                    URL.revokeObjectURL(audioUrl);
                });
            } catch (error) {
                console.error("❌ Error in handlePlayAudio:", error);
                setIsPlaying(false);
            }
        } else if (audioRef.current) {
            audioRef.current.pause();
            setIsPlaying(false);
        }
    }, [message.audio_base64, isPlaying]);

    // Previously we auto-played all messages with audio here.
    // Autoplay is now disabled so that only LiveKit ses kanalından gelen ses duyulsun
    // ve web UI'deki player sadece kullanıcı isteyince çalsın.
    useEffect(() => {
        hasAutoPlayed.current = false;
    }, [message.audio_base64]);

    return (
        <div style={{
            marginBottom: '15px',
            padding: '12px',
            backgroundColor: '#f5f5f5',
            borderRadius: '8px',
            border: '1px solid #e0e0e0'
        }}>
            {message.user_text && (
                <div style={{ marginBottom: '8px' }}>
                    <strong style={{ color: '#666' }}>Sen:</strong>
                    <p style={{ margin: '4px 0', color: '#333' }}>{message.user_text}</p>
                </div>
            )}
            {message.agent_text && (
                <div style={{ marginBottom: '8px' }}>
                    <strong style={{ color: '#2563eb' }}>Asistan:</strong>
                    <p style={{ margin: '4px 0', color: '#333' }}>{message.agent_text}</p>
                </div>
            )}
            {message.audio_base64 && (
                <button
                    onClick={handlePlayAudio}
                    style={{
                        padding: '8px 16px',
                        backgroundColor: isPlaying ? '#ef4444' : '#2563eb',
                        color: 'white',
                        border: 'none',
                        borderRadius: '6px',
                        cursor: 'pointer',
                        fontSize: '14px',
                        fontWeight: '500'
                    }}
                >
                    {isPlaying ? '⏸️ Durdur' : '▶️ Oynat'}
                </button>
            )}
        </div>
    );
}

