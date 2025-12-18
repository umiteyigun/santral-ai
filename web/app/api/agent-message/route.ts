import { NextRequest, NextResponse } from 'next/server';

// Store messages in memory (in production, use Redis or database)
const messages: Map<string, any[]> = new Map();

export async function POST(req: NextRequest) {
    try {
        const body = await req.json();
        const { roomName, message } = body;

        if (!roomName || !message) {
            return NextResponse.json(
                { error: 'Missing roomName or message' },
                { status: 400 }
            );
        }

        // Store message for the room
        if (!messages.has(roomName)) {
            messages.set(roomName, []);
        }
        messages.get(roomName)!.push({
            ...message,
            timestamp: new Date().toISOString()
        });

        console.log(`📬 POST /api/agent-message: Stored message for room ${roomName}:`, {
            type: message.type,
            hasUserText: !!message.user_text,
            hasAgentText: !!message.agent_text,
            hasAudio: !!message.audio_base64,
            audioLength: message.audio_base64?.length || 0
        });

        return NextResponse.json({ success: true });
    } catch (error: any) {
        console.error('Error storing message:', error);
        return NextResponse.json(
            { error: error.message },
            { status: 500 }
        );
    }
}

export async function GET(req: NextRequest) {
    const roomName = req.nextUrl.searchParams.get('room');
    
    if (!roomName) {
        console.log("❌ GET /api/agent-message: Missing room parameter");
        return NextResponse.json(
            { error: 'Missing room parameter' },
            { status: 400 }
        );
    }

    const roomMessages = messages.get(roomName) || [];
    console.log(`📥 GET /api/agent-message?room=${roomName}: Returning ${roomMessages.length} messages`);
    
    // Clear messages after reading (one-time delivery)
    if (roomMessages.length > 0) {
        messages.delete(roomName);
    }

    return NextResponse.json({ messages: roomMessages });
}

